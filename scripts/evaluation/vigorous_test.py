import asyncio
import time
import json
from typing import List, Dict, Any
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.generation.answer_engine import answer_with_rag
from app.domain.learning.course_builder import CourseBuilder
from app.core.logging import logger

async def run_vigorous_test():
    logger.info("Starting Vigorous RAG System Test...")
    start_time = time.time()
    
    manager = VectorStoreManager()
    builder = CourseBuilder(manager)
    
    test_cases = [
        {
            "name": "Direct Technical Question",
            "question": "What are the advantages of star topology?",
            "topic": "Computer Networks"
        },
        {
            "name": "Comparative Multi-hop Question",
            "question": "Compare mesh and bus topology in terms of cost and reliability.",
            "topic": "Computer Networks"
        },
        {
            "name": "Vague Concept Question (Testing HyDE/Rewriting)",
            "question": "Tell me about the backbone cable issue.",
            "topic": "Computer Networks"
        },
        {
            "name": "Graph-Heavy Question (Testing Text2Cypher)",
            "question": "Which topology uses a central hub and is less expensive than mesh?",
            "topic": "Computer Networks"
        }
    ]
    
    report = {
        "summary": {
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "avg_latency": 0
        },
        "details": []
    }
    
    total_latency = 0
    
    for case in test_cases:
        logger.info(f"Running test case: {case['name']}")
        case_start = time.time()
        
        try:
            answer, citations = await answer_with_rag(
                builder=builder,
                topic_title=case["topic"],
                question=case["question"]
            )
            
            latency = time.time() - case_start
            total_latency += latency
            
            # Basic validation
            is_valid = len(answer) > 50 and len(citations) > 0
            if is_valid:
                report["summary"]["passed"] += 1
            else:
                report["summary"]["failed"] += 1
                
            report["details"].append({
                "name": case["name"],
                "question": case["question"],
                "latency": round(latency, 2),
                "answer_preview": answer[:100] + "...",
                "citation_count": len(citations),
                "status": "PASS" if is_valid else "FAIL"
            })
            
        except Exception as e:
            logger.error(f"Test case {case['name']} failed with error: {e}")
            report["summary"]["failed"] += 1
            report["details"].append({
                "name": case["name"],
                "status": "ERROR",
                "error": str(e)
            })

    report["summary"]["avg_latency"] = round(total_latency / len(test_cases), 2)
    report["summary"]["total_time"] = round(time.time() - start_time, 2)
    
    print("\n" + "="*50)
    print("VIGOROUS TEST REPORT")
    print("="*50)
    print(json.dumps(report, indent=2))
    print("="*50)
    
    with open("test_report.json", "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_vigorous_test())
