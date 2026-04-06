import os, sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.database import SessionLocal
from app.core.models import Document, DocumentChunk

session = SessionLocal()
try:
    docs = session.query(Document).filter(Document.user_id == 49).all()
    print(f"Documents for user 49: {len(docs)}")
    for d in docs:
        print(f" - id={d.id}, filename={d.filename}, path={d.file_path}")
    chunks = session.query(DocumentChunk).join(Document).filter(Document.user_id == 49).all()
    print(f"DocumentChunks for user 49: {len(chunks)}")
    for c in chunks[:10]:
        print(f" - chunk id={c.id}, doc_id={c.document_id}, index={c.chunk_index}, text_preview={c.chunk_text[:80]!r}")
    # Check file existence for each document
    import os
    for d in docs:
        fp = d.file_path or d.filename
        abs_fp = os.path.abspath(fp) if fp else None
        print(f"File exists? {fp} -> {abs_fp} : {os.path.exists(abs_fp) if abs_fp else 'N/A'}")
finally:
    session.close()
