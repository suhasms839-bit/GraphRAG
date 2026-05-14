import chromadb
import os

persist_path = "./chroma_db/user_48"
print(f"Checking {persist_path}...")
if os.path.exists(persist_path):
    print("Path exists.")
else:
    print("Path does NOT exist.")

try:
    client = chromadb.PersistentClient(path=persist_path)
    print("Client created.")
    colls = client.list_collections()
    print(f"Collections: {colls}")
    if colls:
        # Check first collection
        col = client.get_collection(colls[0].name)
        print(f"Count in {colls[0].name}: {col.count()}")
        print(f"Peek: {col.peek(1)}")
except Exception as e:
    print(f"Error: {e}")
