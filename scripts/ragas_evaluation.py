import asyncio
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    context_recall,
    faithfulness,
    answer_correctness,
    context_precision,
    answer_relevancy
)

# Add the project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.generation.answer_engine import answer_with_rag
from app.domain.learning.course_builder import CourseBuilder
from app.core.logging import logger

# Test dataset based on computer networks topology content
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

async def generate_answers(test_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate answers using the RAG system for evaluation."""
    logger.info("Setting up RAG system for evaluation...")

    # Initialize the RAG system
    manager = VectorStoreManager()
    data_dir = "./data"
    documents = manager.load_documents(data_dir)

    if not documents:
        logger.error("No documents found for evaluation")
        return []

    logger.info(f"Indexing {len(documents)} documents for evaluation...")
    manager.create_vector_store(documents)

    builder = CourseBuilder(manager)

    results = []
    for i, item in enumerate(test_data):
        logger.info(f"Processing question {i+1}/{len(test_data)}: {item['question'][:50]}...")

        try:
            # Generate answer using RAG
            answer, citations = await answer_with_rag(
                builder=builder,
                topic_title="Computer Networks",
                question=item['question'],
                k=5
            )

            # Get retrieved contexts for evaluation
            retriever = manager  # Using manager directly for context retrieval
            docs = retriever.similarity_search(item['question'], k=5)
            retrieved_contexts = [doc.page_content for doc in docs]

            results.append({
                "question": item["question"],
                "answer": answer,
                "contexts": retrieved_contexts,
                "ground_truth": item["ground_truth"],
                "reference_contexts": item["contexts"]
            })

        except Exception as e:
            logger.error(f"Error processing question {i+1}: {e}")
            results.append({
                "question": item["question"],
                "answer": f"Error: {str(e)}",
                "contexts": [],
                "ground_truth": item["ground_truth"],
                "reference_contexts": item["contexts"]
            })

    return results

def create_evaluation_dataset(results: List[Dict[str, Any]]) -> Dataset:
    """Create a HuggingFace Dataset for RAGAS evaluation."""
    data_dict = {
        "question": [r["question"] for r in results],
        "answer": [r["answer"] for r in results],
        "contexts": [r["contexts"] for r in results],
        "ground_truth": [r["ground_truth"] for r in results]
    }

    return Dataset.from_dict(data_dict)

def run_ragas_evaluation(dataset: Dataset) -> Dict[str, Any]:
    """Run RAGAS evaluation with multiple metrics."""
    logger.info("Running RAGAS evaluation...")

    # Define metrics to evaluate
    metrics = [
        context_recall,      # How much relevant information from retrieved context is used
        faithfulness,        # Factual consistency with retrieved context
        answer_correctness,  # Accuracy compared to ground truth
        context_precision,   # Precision of retrieved contexts
        answer_relevancy     # Relevance of answer to question
    ]

    # Run evaluation
    evaluation_results = evaluate(dataset, metrics=metrics)

    return evaluation_results

def generate_detailed_report(results: Dict[str, Any], raw_data: List[Dict[str, Any]]) -> str:
    """Generate a comprehensive evaluation report."""
    report = []
    report.append("=" * 80)
    report.append("RAGAS EVALUATION REPORT - COMPUTER NETWORKS TOPOLOGY")
    report.append("=" * 80)
    report.append("")

    # Overall metrics
    report.append("📊 OVERALL METRICS:")
    report.append("-" * 40)
    for metric_name, score in results.items():
        if isinstance(score, (int, float)):
            report.append(f"{metric_name}: {score:.4f}")
    report.append("")

    # Individual question analysis
    report.append("🔍 INDIVIDUAL QUESTION ANALYSIS:")
    report.append("-" * 40)

    for i, item in enumerate(raw_data):
        report.append(f"\nQuestion {i+1}: {item['question']}")
        report.append(f"Answer: {item['answer'][:200]}{'...' if len(item['answer']) > 200 else ''}")
        report.append(f"Ground Truth: {item['ground_truth'][:200]}{'...' if len(item['ground_truth']) > 200 else ''}")
        report.append(f"Retrieved Contexts: {len(item['contexts'])} chunks")
        report.append("")

    # Performance analysis
    report.append("📈 PERFORMANCE ANALYSIS:")
    report.append("-" * 40)

    # Calculate additional statistics
    answer_lengths = [len(item['answer']) for item in raw_data]
    context_counts = [len(item['contexts']) for item in raw_data]

    report.append(f"Average Answer Length: {np.mean(answer_lengths):.1f} characters")
    report.append(f"Average Contexts Retrieved: {np.mean(context_counts):.1f}")
    report.append(f"Min Contexts Retrieved: {min(context_counts)}")
    report.append(f"Max Contexts Retrieved: {max(context_counts)}")
    report.append("")

    # Recommendations
    report.append("💡 RECOMMENDATIONS:")
    report.append("-" * 40)

    context_recall_score = results.get('context_recall', 0)
    faithfulness_score = results.get('faithfulness', 0)
    answer_correctness_score = results.get('answer_correctness', 0)

    if context_recall_score < 0.7:
        report.append("• Improve context retrieval - consider better chunking or embedding strategies")
    if faithfulness_score < 0.8:
        report.append("• Enhance answer generation to better utilize retrieved context")
    if answer_correctness_score < 0.7:
        report.append("• Review ground truth answers and question formulation")

    if all(score > 0.8 for score in [context_recall_score, faithfulness_score, answer_correctness_score]):
        report.append("• System performing well! Consider advanced optimizations.")

    report.append("")
    report.append("=" * 80)

    return "\n".join(report)

async def main():
    """Main evaluation function."""
    logger.info("Starting comprehensive RAGAS evaluation...")

    try:
        # Generate answers using the RAG system
        logger.info("Generating answers with RAG system...")
        raw_results = await generate_answers(TEST_DATA)

        if not raw_results:
            logger.error("No results generated. Exiting.")
            return

        # Create evaluation dataset
        logger.info("Creating evaluation dataset...")
        eval_dataset = create_evaluation_dataset(raw_results)

        # Run RAGAS evaluation
        logger.info("Running RAGAS evaluation...")
        evaluation_results = run_ragas_evaluation(eval_dataset)

        # Generate detailed report
        logger.info("Generating evaluation report...")
        report = generate_detailed_report(dict(evaluation_results), raw_results)

        # Save results
        output_dir = "./evaluation_results"
        os.makedirs(output_dir, exist_ok=True)

        # Save detailed report
        with open(f"{output_dir}/ragas_evaluation_report.txt", "w", encoding="utf-8") as f:
            f.write(report)

        # Save raw results as JSON
        import json
        with open(f"{output_dir}/evaluation_raw_results.json", "w", encoding="utf-8") as f:
            json.dump(raw_results, f, indent=2, ensure_ascii=False)

        # Save metrics as CSV
        metrics_df = pd.DataFrame([dict(evaluation_results)])
        metrics_df.to_csv(f"{output_dir}/evaluation_metrics.csv", index=False)

        # Print report to console
        print("\n" + report)

        logger.info(f"Evaluation complete! Results saved to {output_dir}/")

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())