import psycopg2
from app.core.config import settings
from app.core.logging import logger

def get_db_connection():
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

def initialize_database(schema_path: str = "schema.sql"):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            with open(schema_path, "r") as f:
                cur.execute(f.read())
        conn.commit()
        logger.info("Database initialized successfully.")
    finally:
        conn.close()
