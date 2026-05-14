import json
import logging
from typing import Dict, List, Optional
from app.infrastructure.vectorstore.manager import VectorStoreManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CourseBuilder:
    def __init__(self, vectorstore_manager: VectorStoreManager):
        self.manager = vectorstore_manager

    def build_syllabus(self, output_file: str = "syllabus.json") -> Dict:
        # In a real scenario, this would extract topics from the vector store
        # For now, we return a simple structure
        return {"course_name": "Generated Course Syllabus", "topics": []}

    def query_course_content(self, query: str, k: int = 5) -> List[Dict]:
        docs = self.manager.similarity_search(query, k=k)
        return [{"content": d.page_content, "metadata": d.metadata} for d in docs]
