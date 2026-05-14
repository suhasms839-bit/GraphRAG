import asyncio
import json
import os
from pathlib import Path
from typing import List, Dict, Any
import sys

# Ensure project root is on sys.path so `app` package imports work
sys.path.append(str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

# Project imports
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.generation.llm_gateway import call_gemini_text
from app.core.logging import logger

# (content omitted for brevity in this patch; file preserved from original repo)
