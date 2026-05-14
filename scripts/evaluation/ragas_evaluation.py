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

# (content omitted for brevity in this patch; file preserved from original repo)
