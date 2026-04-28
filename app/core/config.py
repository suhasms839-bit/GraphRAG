import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "GraphRAG Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rag")
    
    # Vector Store
    CHROMA_PERSIST_DIR: str = os.getenv("VECTORSTORE_PERSIST_DIRECTORY", "./chroma_db")
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # LLM
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    # Ollama Configuration
    USE_OLLAMA: bool = os.getenv("USE_OLLAMA", "true").strip().lower() in {"1", "true", "yes", "y"}
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))

    # Retrieval thresholds
    STRONG_CONTEXT_THRESHOLD: float = float(os.getenv("STRONG_CONTEXT_THRESHOLD", "0.7"))
    WEAK_CONTEXT_THRESHOLD: float = float(os.getenv("WEAK_CONTEXT_THRESHOLD", "0.4"))
    # LLM reranker controls
    RERANKER_ENABLED: bool = os.getenv("RERANKER_ENABLED", "true").strip().lower() in {"1", "true", "yes", "y"}
    RE_RANKER_TIMEOUT: float = float(os.getenv("RE_RANKER_TIMEOUT", "0.5"))
    # Graph seed scoring
    SEED_SCORE_THRESHOLD: float = float(os.getenv("SEED_SCORE_THRESHOLD", "0.6"))
    
    # Neo4j
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    # Optional additional Neo4j fields
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "")
    # Wait before first Neo4j connection attempt (seconds)
    AURA_WAIT_SECONDS: int = int(os.getenv("AURA_WAIT_SECONDS", "60"))
    # Graph path traversal limits
    MAX_GRAPH_PATH_DEPTH: int = int(os.getenv("MAX_GRAPH_PATH_DEPTH", "2"))
    MAX_GRAPH_PATHS_PER_SEED: int = int(os.getenv("MAX_GRAPH_PATHS_PER_SEED", "5"))
    # Minimum graph trust to consider graph signal (0-1)
    GRAPH_MIN_TRUST: float = float(os.getenv("GRAPH_MIN_TRUST", "0.3"))
    # Context limits
    MAX_CONTEXT_TOKENS: int = int(os.getenv("MAX_CONTEXT_TOKENS", "1200"))
    CONTEXT_CHUNK_MIN_WORDS: int = int(os.getenv("CONTEXT_CHUNK_MIN_WORDS", "40"))
    MAX_CONTEXT_CHUNKS: int = int(os.getenv("MAX_CONTEXT_CHUNKS", "5"))
    # Chroma / per-user scaling guardrails
    CHROMA_MAX_CHUNKS_PER_USER: int = int(os.getenv("CHROMA_MAX_CHUNKS_PER_USER", "20000"))
    CHROMA_MAX_CHUNKS_PER_INGEST: int = int(os.getenv("CHROMA_MAX_CHUNKS_PER_INGEST", "2000"))
    # Whether to persist community summaries into the global vectorstore
    CHROMA_PERSIST_COMMUNITY_SUMMARIES: bool = os.getenv("CHROMA_PERSIST_COMMUNITY_SUMMARIES", "true").strip().lower() in {"1","true","yes","y"}
    # Telemetry toggles
    TELEMETRY_ENABLED: bool = os.getenv("TELEMETRY_ENABLED", "true").strip().lower() in {"1","true","yes","y"}

    class Config:
        case_sensitive = True
        # Allow loading environment variables from a .env file in the project root
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow extra environment variables (so .env can contain provider-specific keys)
        extra = "allow"

settings = Settings()
