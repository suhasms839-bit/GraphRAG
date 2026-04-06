import os, sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.core.database import SessionLocal
from app.core.models import Document, DocumentChunk

m = VectorStoreManager(user_id=49)
print('manager.persist_directory=', m.persist_directory)
store = m.get_vectorstore()
print('vectorstore object:', type(store), store)

res = m.similarity_search('bus topology', k=5)
print('similarity_search returned count:', len(res))

# Manual DB check
db = SessionLocal()
docs = db.query(Document).filter(Document.user_id == 49).all()
print('DB documents count:', len(docs))
for d in docs:
    fp = d.file_path or d.filename
    abs_fp = os.path.abspath(fp) if fp else None
    print('file:', fp, ' -> ', abs_fp, 'exists=', os.path.exists(abs_fp) if abs_fp else None)
    if abs_fp and os.path.exists(abs_fp):
        with open(abs_fp, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        contains = 'bus topology' in text.lower()
        print(' contains "bus topology"?:', contains)
        if contains:
            print(' preview:', text[:200])

# Manual chunk rows
chunks = db.query(DocumentChunk).join(Document).filter(Document.user_id == 49).all()
print('DB chunk rows count:', len(chunks))

