import asyncio
import json
import os
import sys
from typing import List, Dict, Any

# Ensure we can import from the app
sys.path.append(os.getcwd())

from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.agents.orchestrator import AgenticOrchestrator
from app.domain.evaluation.metrics import RAGEvaluator

async def run_ragas_evaluation():
    print("--- [RAGAS EVALUATION] Starting Quality Assessment ---")
    
    # 1. Setup
    # Path for User 48 who has stored data
    user_id = 48
    manager = VectorStoreManager(user_id=user_id)
    orchestrator = AgenticOrchestrator(manager)
    evaluator = RAGEvaluator()
    
    # Test dataset
    test_cases = [
        {
            "question": "What is the ABCDE method and how are its priority levels defined?",
            "topic": "Time Management"
        },
        {
            "question": "What are the advantages and disadvantages of Mesh Topology?",
            "topic": "Computer Networks"
        },
        {
            "question": "If the central hub fails in a Star Topology, what happens to the network?",
            "topic": "Computer Networks"
        }
    ]
    
    results = []
    
    for case in test_cases:
        print(f"\nEvaluating: {case['question']}")
        
        # 2. Generate Answer using the Agentic Pipeline
        try:
            # We use the actual orchestrator logic (Fix 5)
            response = await orchestrator.run(case['question'], case['topic'])
            
            # Handle the dictionary response properly
            if isinstance(response, dict):
                answer = response.get("answer", "")
            else:
                answer = str(response)
            
            # Extract retrieved context for faithfulness/recall
            # Fix: retriever.retrieve returns a dictionary {'hits': [...], 'confidence': ...}
            retrieval_resp = await orchestrator.retriever.retrieve(case['question'], topic_title=case['topic'], k=5)
            hits = retrieval_resp.get("hits", [])
            context = "\n\n".join([h.get('content', '') for h in hits])
            
            # 3. Score using RAGEvaluator (LLM-as-a-judge)
            # Add delay to avoid rate limits
            await asyncio.sleep(2)
            faithfulness = await evaluator.evaluate_faithfulness(answer, context)
            await asyncio.sleep(2)
            recall = await evaluator.evaluate_context_recall(context, "N/A (Heuristic)")
            await asyncio.sleep(2)
            correctness = await evaluator.evaluate_answer_correctness(answer, case['question'])
            
            case_result = {
                "question": case['question'],
                "faithfulness": faithfulness,
                "context_recall": recall,
                "answer_correctness": correctness
            }
            results.append(case_result)
            
            print(f"  > Faithfulness: {faithfulness}")
            print(f"  > Context Recall: {recall}")
            print(f"  > Answer Correctness: {correctness}")
            
        except Exception as e:
            print(f"  ! Error evaluating case: {e}")

    # 4. Final Report
    if results:
        avg_faith = sum(r['faithfulness'] for r in results) / len(results)
        avg_recall = sum(r['context_recall'] for r in results) / len(results)
        avg_correct = sum(r['answer_correctness'] for r in results) / len(results)
        
        print("\n" + "="*40)
        print("AVERAGE SCORES:")
        print(f"Faithfulness:       {avg_faith:.2f}")
        print(f"Context Recall:     {avg_recall:.2f}")
        print(f"Answer Correctness: {avg_correct:.2f}")
        print("="*40)

if __name__ == "__main__":
    asyncio.run(run_ragas_evaluation())
