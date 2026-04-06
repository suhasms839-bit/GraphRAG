import asyncio
import json
import os
from pathlib import Path
from typing import List, Dict, Any
import sys

# Ensure project root is on sys.path so `app` package imports work
sys.path.append(str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

# Project imports
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.generation.llm_gateway import call_gemini_text
from app.core.logging import logger

# Evaluation dataset (same as earlier)
TEST_DATA = [
    {"question": "What are the main advantages of mesh topology?",
     "ground_truth": "Mesh topology offers several key advantages: no traffic problems due to dedicated links, robustness (one link failure doesn't disable the system), security and privacy (data sent along dedicated lines), and easy fault identification through point-to-point connectivity.",
     "contexts": [
         "Advantages of Mesh Topology: - No traffic problems: Since there are dedicated links, each connection can carry its own data load, eliminating traffic congestion issues common in shared links. - Robustness: If one link becomes unusable, it does not disable the entire system. - Security and Privacy: Data is sent along a dedicated line, so only the intended recipient sees it. - Easy fault identification: Point-to-point connectivity makes it easy to find where a fault lies."
     ]},
    {"question": "Why is star topology considered more expensive than mesh topology?",
     "ground_truth": "Star topology is less expensive than mesh topology because each device needs only one link and one I/O port to connect to the central hub, whereas mesh topology requires every device to be connected to every other device, resulting in extremely high cabling and hardware costs.",
     "contexts": [
         "Advantages of Star Topology: - Less expensive than mesh: Each device needs only one link and one I/O port to connect it to any number of others.",
         "Disadvantages of Mesh Topology: - High amount of cabling: Since every node is connected to every other node, the amount of cabling required is extremely high. - Expensive: The cost of hardware (cables and ports) is very high."
     ]},
    {"question": "What happens if the central hub fails in a star topology?",
     "ground_truth": "If the central hub fails in a star topology, the entire network becomes inoperable since all devices depend on the hub for communication and data routing.",
     "contexts": [
         "Disadvantages of Star Topology: - Single point of failure: If the central hub goes down, the entire network is dead. - Dependency: The performance of the network depends heavily on the central hub."
     ]},
    {"question": "How does bus topology handle signal transmission and what are its main disadvantages?",
     "ground_truth": "In bus topology, one long cable acts as a backbone linking all devices. Nodes connect via drop lines and taps. Main disadvantages include difficult reconfiguration, signal reflection causing quality degradation, and single point of failure where a break in the bus cable stops all transmission.",
     "contexts": [
         "Bus Topology: A bus topology is multipoint. One long cable acts as a backbone to link all the devices in a network. Nodes are connected to the bus cable by drop lines and taps.",
         "Disadvantages of Bus Topology: - Difficult reconfiguration: It can be difficult to add new devices if the backbone cable is not long enough. - Signal reflection: Signal reflection at the taps can cause degradation in quality. - Single point of failure: A fault or break in the bus cable stops all transmission, even between devices on the same side of the problem."
     ]},
]

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def normalize_text(t: str) -> str:
    return " ".join([w.strip(".,:;()[]\n\t\r").lower() for w in t.split() if w.strip()])


def token_overlap(a: str, b: str) -> float:
    a_tokens = set(normalize_text(a).split())
    b_tokens = set(normalize_text(b).split())
    if not a_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens)


async def run_evaluation():
    logger.info("Starting Gemini-backed RAG evaluation...")

    manager = VectorStoreManager()
    data_dir = "./data"
    docs = manager.load_documents(data_dir)
    if not docs:
        logger.error("No documents found under ./data; aborting evaluation.")
        return

    manager.create_vector_store(docs)

    embed = SentenceTransformer(EMBED_MODEL)

    results = []

    for item in TEST_DATA:
        q = item["question"]
        gt = item["ground_truth"]
        refs = item.get("contexts", [])

        retrieved = manager.similarity_search(q, k=5)
        retrieved_texts = [d.page_content for d in retrieved]

        context_str = "\n\n".join([f"Context {i+1}:\n{t}" for i, t in enumerate(retrieved_texts)])

        prompt = f"""You are a precise assistant. Answer the question using ONLY the provided CONTEXT.\nIf the context is insufficient, start with 'Based on general knowledge:' and then answer.\n\nCONTEXT:\n{context_str}\n\nQUESTION:\n{q}\n\nAnswer concisely:"""

        # Call Gemini
        llm_response = call_gemini_text(prompt, temperature=0.0, max_tokens=400)
        if not llm_response or llm_response.startswith("LLM Error:") or "GEMINI_API_KEY not configured" in llm_response:
            logger.warning(f"Gemini call failed for question: {q}; falling back to retrieved contexts as answer. Error: {llm_response}")
            answer = "\n\n".join(retrieved_texts[:3]) if retrieved_texts else ""
            gemini_ok = False
        else:
            answer = llm_response.strip()
            gemini_ok = True

        # Metrics
        # Context recall: fraction of reference contexts covered by retrieved texts
        matched_refs = 0
        for ref in refs:
            for r in retrieved_texts:
                if token_overlap(ref, r) >= 0.4:
                    matched_refs += 1
                    break
        context_recall = matched_refs / len(refs) if refs else 0.0

        # Faithfulness: fraction of answer tokens present in union of retrieved texts
        answer_tokens = set(normalize_text(answer).split())
        retrieved_union = set()
        for r in retrieved_texts:
            retrieved_union.update(normalize_text(r).split())
        faithfulness = len(answer_tokens & retrieved_union) / len(answer_tokens) if answer_tokens else 0.0

        # Answer correctness (semantic similarity between answer and ground truth)
        try:
            emb_ans = embed.encode([answer])[0]
            emb_gt = embed.encode([gt])[0]
            ans_corr = float(np.dot(emb_ans, emb_gt) / (np.linalg.norm(emb_ans) * np.linalg.norm(emb_gt)))
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            ans_corr = 0.0

        results.append({
            "question": q,
            "answer": answer,
            "gemini_ok": gemini_ok,
            "context_recall": context_recall,
            "faithfulness": faithfulness,
            "answer_correctness": ans_corr,
            "retrieved_count": len(retrieved_texts),
            "retrieved_contexts": retrieved_texts,
            "ground_truth": gt
        })

    # Aggregates
    df = pd.DataFrame(results)
    avg_context_recall = df["context_recall"].mean()
    avg_faithfulness = df["faithfulness"].mean()
    avg_answer_correctness = df["answer_correctness"].mean()

    out_dir = Path("./evaluation_results_gemini")
    out_dir.mkdir(exist_ok=True)

    with open(out_dir / "gemini_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    df.to_csv(out_dir / "gemini_results_summary.csv", index=False)

    summary = {
        "avg_context_recall": float(avg_context_recall),
        "avg_faithfulness": float(avg_faithfulness),
        "avg_answer_correctness": float(avg_answer_correctness)
    }

    with open(out_dir / "gemini_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\nGemini-backed RAG Evaluation Summary:\n")
    print(json.dumps(summary, indent=2))
    logger.info(f"Detailed results saved to {out_dir}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
