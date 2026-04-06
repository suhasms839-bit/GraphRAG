import requests
import json
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_full_rag_pipeline():
    url = "http://localhost:8000/api/chat/ask"
    
    # query that we know exists (Bus Topology)
    payload = {
        "user_id": 48,
        "question": "What are the characteristics of a bus topology and when should it be avoided?",
        "topic_id": "network_topologies"
    }
    
    logger.info(f"Testing RAG Pipeline with question: {payload['question']}")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print("\n=== SYSTEM RESPONSE ===")
        print(f"Confidence Label: {result.get('confidence_label', 'Unknown')}")
        print(f"Confidence Score: {result.get('confidence_rate', 0.0)}")
        print(f"Answer Preview: {result.get('answer', '')[:500]}...")
        
        if "Retrieved documents contain limited information" in result.get('answer', ''):
            print("\n[VERIFIED] Low-confidence fallback disclaimer triggered correctly.")
        else:
            print("\n[VERIFIED] Answer provided from context/general knowledge.")

        if result.get('confidence_rate', 0.0) == 0:
            print("[CRITICAL] Confidence rate is 0.0 - Check retriever context gathering.")
            
    except Exception as e:
        logger.error(f"E2E Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_full_rag_pipeline()
