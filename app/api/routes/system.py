from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.models import Document
from app.core.logging import logger

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status(db: Session = Depends(get_db)):
    """Return a minimal system status including graph readiness.

    This endpoint is intentionally lightweight and unauthenticated so the
    frontend can display a read-only badge about graph availability.
    """
    try:
        total = db.query(Document).count()
        ingested_count = db.query(Document).filter(Document.ingested == True).count()
        graph_ready_count = db.query(Document).filter(Document.graph_ready == True).count()

        if graph_ready_count > 0:
            graph_status = "active"
        elif ingested_count > 0:
            graph_status = "indexing"
        else:
            graph_status = "off"

        return {
            "status": "ok",
            "total_documents": total,
            "ingested_documents": ingested_count,
            "graph_ready_documents": graph_ready_count,
            "graph_status": graph_status,
        }
    except Exception as e:
        logger.exception("Failed to compute system status")
        return {"status": "error", "error": str(e), "graph_status": "off"}
