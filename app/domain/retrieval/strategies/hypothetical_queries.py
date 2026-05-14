from typing import List, Optional
from app.domain.generation.llm_gateway import call_gemini_text
from app.core.logging import logger

class HypotheticalQueryGenerator:
    @staticmethod
    def generate(question: str, topic_title: Optional[str] = None) -> List[str]:
        """
        Generates a hypothetical answer (HyDE style) to the user's question.
        This synthetic content is often better for vector matching than the raw question.
        """
        topic_context = f" in the context of {topic_title}" if topic_title else ""
        prompt = f"""You are a technical expert. Provide a concise, 2-sentence hypothetical answer to the following question{topic_context}. 
This answer will be used to retrieve relevant documents from a vector database.

Question: {question}

Hypothetical Answer:"""

        try:
            # We use a very low temperature for stability and fast tokens
            hypothetical_answer = call_gemini_text(prompt, max_tokens=150, temperature=0.0)
            if hypothetical_answer and "LLM Error" not in hypothetical_answer:
                return [hypothetical_answer.strip()]
        except Exception as e:
            logger.error(f"Hypothetical query generation failed: {e}")
        
        return []
