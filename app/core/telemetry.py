import json
from typing import Any, Dict, Optional
from app.core.database import SessionLocal
from app.core.models import Telemetry
from app.core.config import settings
from app.core.logging import logger


def record_event(event_type: str, payload: Dict[str, Any], user_id: Optional[int] = None, document_id: Optional[int] = None) -> bool:
    """Persist a telemetry event to the DB if telemetry is enabled.

    Returns True on success, False otherwise.
    """
    if not getattr(settings, "TELEMETRY_ENABLED", True):
        return False

    try:
        db = SessionLocal()
        t = Telemetry(
            user_id=user_id,
            document_id=document_id,
            event_type=event_type,
            payload=json.dumps(payload)
        )
        db.add(t)
        db.commit()
        db.close()
        return True
    except Exception as e:
        logger.exception(f"Failed to record telemetry event {event_type}: {e}")
        try:
            db.close()
        except Exception:
            pass
        return False
