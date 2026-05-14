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

# (content omitted for brevity in this patch; file preserved from original repo)
