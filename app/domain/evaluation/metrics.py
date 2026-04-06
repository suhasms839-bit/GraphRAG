import asyncio
from typing import List, Dict, Any
from app.domain.generation.llm_gateway import call_gemini_text

class RAGEvaluator:
    """
    Evaluates RAG performance using LLM-as-a-judge for Faithfulness, 
    Context Recall, and Answer Correctness.
    """

    async def evaluate_faithfulness(self, answer: str, context: str) -> float:
        """Checks if the answer is derived ONLY from the context."""
        prompt = f"""
        You are a Fact-Checker. Evaluate if the following answer is faithful to the provided context.
        Does the answer contain information NOT present in the context?
        
        Context: {context}
        Answer: {answer}
        
        Return ONLY a score between 0.0 and 1.0, where 1.0 is perfectly faithful.
        Score:
        """
        try:
            score_str = await asyncio.to_thread(call_gemini_text, prompt)
            print(f"DEBUG EVAL: Faithfulness Score: {score_str}")
            return float(score_str.strip())
        except Exception:
            return 0.5

    async def evaluate_context_recall(self, context: str, ground_truth_cypher: str) -> float:
        """Checks if the retrieved context contains the expected entities/relationships."""
        prompt = f"""
        You are a Data Auditor. Evaluate if the retrieved context contains the information 
        that would be returned by this Cypher query: {ground_truth_cypher}
        
        Retrieved Context: {context}
        
        Return ONLY a score between 0.0 and 1.0, where 1.0 means all expected data is present.
        Score:
        """
        try:
            score_str = await asyncio.to_thread(call_gemini_text, prompt)
            print(f"DEBUG EVAL: Recall Score: {score_str}")
            return float(score_str.strip())
        except Exception:
            return 0.5

    async def evaluate_answer_correctness(self, answer: str, question: str) -> float:
        """Checks if the answer accurately and fully addresses the question."""
        prompt = f"""
        You are a Technical Mentor. Evaluate if the following answer correctly and fully 
        addresses the student's question.
        
        Question: {question}
        Answer: {answer}
        
        Return ONLY a score between 0.0 and 1.0, where 1.0 is perfectly correct.
        Score:
        """
        try:
            score_str = await asyncio.to_thread(call_gemini_text, prompt)
            print(f"DEBUG EVAL: Correctness Score: {score_str}")
            return float(score_str.strip())
        except Exception:
            return 0.5
