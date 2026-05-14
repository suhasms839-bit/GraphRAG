import asyncio
import json
from app.domain.evaluation.benchmark import RAGBenchmark

async def main():
    print("--- Starting Vigorous RAG Benchmark Test ---")
    benchmark = RAGBenchmark()
    
    # Run the full benchmark
    # This will execute real RAG flows and use LLM-as-a-judge for scoring
    report = await benchmark.run_full_benchmark()
    
    print("\n--- Aggregate Scores ---")
    print(json.dumps(report["aggregate_scores"], indent=2))
    
    print("\n--- Detailed Results ---")
    for res in report["detailed_results"]:
        print(f"ID: {res['id']} | Type: {res['type']} | Status: {res['status']}")
        print(f"  Query: {res['query']}")
        print(f"  Metrics: {res['metrics']}")
        print("-" * 30)

if __name__ == "__main__":
    asyncio.run(main())
