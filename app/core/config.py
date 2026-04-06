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

    # Retrieval thresholds
    STRONG_CONTEXT_THRESHOLD: float = float(os.getenv("STRONG_CONTEXT_THRESHOLD", "0.7"))
    WEAK_CONTEXT_THRESHOLD: float = float(os.getenv("WEAK_CONTEXT_THRESHOLD", "0.4"))
    
    # Neo4j
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    # Optional additional Neo4j fields
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "")
    # Wait before first Neo4j connection attempt (seconds)
    AURA_WAIT_SECONDS: int = int(os.getenv("AURA_WAIT_SECONDS", "60"))

    class Config:
        case_sensitive = True
        # Allow loading environment variables from a .env file in the project root
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow extra environment variables (so .env can contain provider-specific keys)
        extra = "allow"

settings = Settings()
