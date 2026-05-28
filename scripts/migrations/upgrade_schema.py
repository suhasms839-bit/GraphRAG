"""Deploy-time schema bootstrap for the current application models.

Run this before starting the app in production:
    python scripts/migrations/upgrade_schema.py

This keeps schema creation out of the API startup path so deploys can control
when database changes are applied.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import Base, engine

# Import models so SQLAlchemy registers all tables on Base.metadata.
from app.core import models  # noqa: F401


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Schema bootstrap complete.")


if __name__ == "__main__":
    main()