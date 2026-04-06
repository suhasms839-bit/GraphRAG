import os
import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd
from typing import List, Dict

# Add project root
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.core.logging import logger

# Use sentence-transformers for semantic similarity
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

TEST_DATA = [
    {
        "question": "What are the main advantages of mesh topology?",
        "ground_truth": "Mesh topology offers several key advantages: no traffic problems due to dedicated links, robustness (one link failure doesn't disable the system), security and privacy (data sent along dedicated lines), and easy fault identification through point-to-point connectivity.",
        "contexts": [
            "Advantages of Mesh Topology: - No traffic problems: Since there are dedicated links, each connection can carry its own data load, eliminating traffic congestion issues common in shared links. - Robustness: If one link becomes unusable, it does not disable the entire system. - Security and Privacy: Data is sent along a dedicated line, so only the intended recipient sees it. - Easy fault identification: Point-to-point connectivity makes it easy to find where a fault lies."
        ]
    },
    {
        "question": "Why is star topology considered more expensive than mesh topology?",
        "ground_truth": "Star topology is less expensive than mesh topology because each device needs only one link and one I/O port to connect to the central hub, whereas mesh topology requires every device to be connected to every other device, resulting in extremely high cabling and hardware costs.",
        "contexts": [
            "Advantages of Star Topology: - Less expensive than mesh: Each device needs only one link and one I/O port to connect it to any number of others.",
            "Disadvantages of Mesh Topology: - High amount of cabling: Since every node is connected to every other node, the amount of cabling required is extremely high. - Expensive: The cost of hardware (cables and ports) is very high."
        ]
    },
    {
        "question": "What happens if the central hub fails in a star topology?",
        "ground_truth": "If the central hub fails in a star topology, the entire network becomes inoperable since all devices depend on the hub for communication and data routing.",
        "contexts": [
            "Disadvantages of Star Topology: - Single point of failure: If the central hub goes down, the entire network is dead. - Dependency: The performance of the network depends heavily on the central hub."
        ]
    },
    {
        "question": "How does bus topology handle signal transmission and what are its main disadvantages?",
        "ground_truth": "In bus topology, one long cable acts as a backbone linking all devices. Nodes connect via drop lines and taps. Main disadvantages include difficult reconfiguration, signal reflection causing quality degradation, and single point of failure where a break in the bus cable stops all transmission.",
        "contexts": [
            "Bus Topology: A bus topology is multipoint. One long cable acts as a backbone to link all the devices in a network. Nodes are connected to the bus cable by drop lines and taps.",
            "Disadvantages of Bus Topology: - Difficult reconfiguration: It can be difficult to add new devices if the backbone cable is not long enough. - Signal reflection: Signal reflection at the taps can cause degradation in quality. - Single point of failure: A fault or break in the bus cable stops all transmission, even between devices on the same side of the problem."
        ]
    },
    {
        "question": "What are the advantages and disadvantages of ring topology?",
        "ground_truth": "Ring topology advantages include easy installation and reconfiguration (only two connections to move), and fault isolation through alarm systems. The main disadvantage is unidirectional traffic where a break in the ring can disable the entire network.",
        "contexts": [
            "Advantages of Ring Topology: - Easy to install and reconfigure: Each device is linked to only its immediate neighbors. To add or delete a device requires moving only two connections. - Fault isolation: Generally, in a ring, a signal is circulating at all times. If one device does not receive a signal within a specified period, it can issue an alarm.",
            "Disadvantages of Ring Topology: - Unidirectional traffic: A break in the ring (such as a disabled station) can disable the entire network."
        ]
    },
    {
        "question": "Which topology is most reliable and why?",
        "ground_truth": "Mesh topology is the most reliable because every device has dedicated point-to-point links to every other device, so if one link fails, the system continues to function through alternative paths.",
        "contexts": [
            "Mesh Topology: In a mesh topology, every device is connected to every other device in a network through a dedicated point-to-point link.",
            "Advantages of Mesh Topology: - Robustness: If one link becomes unusable, it does not disable the entire system."
        ]
    },
    {
        "question": "Compare the cabling requirements of mesh, star, and bus topologies.",
        "ground_truth": "Mesh topology requires the highest amount of cabling since every node connects to every other node. Star topology uses moderate cabling with each device connecting only to a central hub. Bus topology uses the least cabling with one backbone cable and short drop lines to devices.",
        "contexts": [
            "Disadvantages of Mesh Topology: - High amount of cabling: Since every node is connected to every other node, the amount of cabling required is extremely high.",
            "Advantages of Star Topology: - Less expensive than mesh: Each device needs only one link and one I/O port to connect it to any number of others.",
            "Advantages of Bus Topology: - Less cabling: It uses less cabling than mesh or star topologies."
        ]
    },
    {
        "question": "What factors should be considered when choosing a network topology?",
        "ground_truth": "When choosing a topology, factors like cost, flexibility, and reliability must be considered. Mesh offers highest reliability but is most expensive. Star provides good balance of cost and reliability. Bus is rarely used today except in small networks. Ring is used for high-speed networks requiring deterministic performance.",
        "contexts": [
            "Comparison Summary: When choosing a topology, factors like cost, flexibility, and reliability must be considered. Mesh is the most reliable but most expensive. Star is the most common in modern LANs due to its balance of cost and reliability. Bus is rarely used today except in very small or legacy networks. Ring is used in some high-speed networks where deterministic performance is required."
        ]
    }
]


def normalize_text(t: str) -> str:
    return " ".join([w.strip(".,:;()[]\n\t\r").lower() for w in t.split() if w.strip()])


def token_overlap(a: str, b: str) -> float:
    a_tokens = set(normalize_text(a).split())
    b_tokens = set(normalize_text(b).split())
    if not a_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens)


def evaluate_locally(test_data: List[Dict]):
    logger.info("Starting local RAG evaluation...")

    # Load vectorstore manager
    manager = VectorStoreManager()

    # Load embedding model
    embed = SentenceTransformer(MODEL_NAME)

    per_item_results = []

    for item in test_data:
        q = item["question"]
        gt = item["ground_truth"]
        refs = item.get("contexts", [])

        # Retrieve
        retrieved = manager.similarity_search(q, k=5)
        retrieved_texts = [d.page_content for d in retrieved]

        # Build a retrieval-based answer (concatenate top-3 retrieved)
        answer = "\n\n".join(retrieved_texts[:3]) if retrieved_texts else ""

        # Context recall: fraction of reference contexts covered by retrieved
        matched_refs = 0
        for ref in refs:
            for r in retrieved_texts:
                if token_overlap(ref, r) >= 0.4:
                    matched_refs += 1
                    break
        context_recall = matched_refs / len(refs) if refs else 0.0

        # Context precision: fraction of retrieved contexts that match any reference
        matched_retrieved = 0
        for r in retrieved_texts:
            for ref in refs:
                if token_overlap(ref, r) >= 0.4:
                    matched_retrieved += 1
                    break
        context_precision = matched_retrieved / len(retrieved_texts) if retrieved_texts else 0.0

        # Answer correctness (proxy): cosine similarity between answer and ground truth
        if answer.strip() and gt.strip():
            emb_ans = embed.encode([answer])[0]
            emb_gt = embed.encode([gt])[0]
            cos_sim = float(np.dot(emb_ans, emb_gt) / (np.linalg.norm(emb_ans) * np.linalg.norm(emb_gt)))
        else:
            cos_sim = 0.0

        # Faithfulness proxy: fraction of tokens in answer that appear in retrieved contexts
        answer_tokens = set(normalize_text(answer).split())
        retrieved_union = set()
        for r in retrieved_texts:
            retrieved_union.update(normalize_text(r).split())
        faithfulness_proxy = len(answer_tokens & retrieved_union) / len(answer_tokens) if answer_tokens else 0.0

        # Corrections needed (proxy): portion of ground truth tokens missing from answer
        gt_tokens = set(normalize_text(gt).split())
        missing_tokens = gt_tokens - set(normalize_text(answer).split())
        correction_ratio = len(missing_tokens) / len(gt_tokens) if gt_tokens else 0.0

        per_item_results.append({
            "question": q,
            "retrieved_count": len(retrieved_texts),
            "context_recall": context_recall,
            "context_precision": context_precision,
            "answer_similarity": cos_sim,
            "faithfulness_proxy": faithfulness_proxy,
            "correction_ratio": correction_ratio,
            "answer": answer,
            "retrieved_contexts": retrieved_texts,
            "ground_truth": gt
        })

    return per_item_results


if __name__ == "__main__":
    results = evaluate_locally(TEST_DATA)

    out_dir = Path("./evaluation_results_local")
    out_dir.mkdir(exist_ok=True)

    # Save raw JSON
    with open(out_dir / "local_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Save CSV summary
    df = pd.DataFrame(results)
    df.to_csv(out_dir / "local_results_summary.csv", index=False)

    # Print summary
    avg_context_recall = df["context_recall"].mean()
    avg_context_precision = df["context_precision"].mean()
    avg_answer_similarity = df["answer_similarity"].mean()
    avg_faithfulness = df["faithfulness_proxy"].mean()
    avg_correction = df["correction_ratio"].mean()

    summary = (
        f"Local RAG Evaluation Summary:\n"
        f"Avg Context Recall: {avg_context_recall:.3f}\n"
        f"Avg Context Precision: {avg_context_precision:.3f}\n"
        f"Avg Answer Similarity (proxy): {avg_answer_similarity:.3f}\n"
        f"Avg Faithfulness Proxy: {avg_faithfulness:.3f}\n"
        f"Avg Correction Ratio: {avg_correction:.3f}\n"
    )

    print(summary)
    logger.info("Local evaluation complete. Results saved to ./evaluation_results_local/")
