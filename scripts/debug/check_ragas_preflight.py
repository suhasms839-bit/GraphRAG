import sys
import traceback
sys.path.insert(0, '.')

from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.graph.graph_querying import get_neo4j_driver


def run_checks():
    try:
        mgr = VectorStoreManager(user_id=48)
        print(f"[INFO] Persist dir: {mgr.persist_directory}")
        vs = mgr.get_vectorstore()
        if not vs:
            print('[ERROR] Chroma vectorstore returned None')
        else:
            print('[OK] Chroma vectorstore initialized')
            try:
                docs = vs.similarity_search('test query', k=1)
                print(f'[OK] similarity_search returned {len(docs)} results')
            except Exception as e:
                print(f'[WARN] similarity_search failed: {e}')

        driver = get_neo4j_driver()
        if not driver:
            print('[WARN] Neo4j driver unavailable')
        else:
            print('[OK] Neo4j driver acquired')
            try:
                with driver.session() as session:
                    res = session.run('RETURN 1 AS ok')
                    row = res.single()
                    print(f'[OK] Neo4j test query result: {row["ok"]}')
            except Exception as e:
                print(f'[ERROR] Neo4j test query failed: {e}')

    except Exception:
        traceback.print_exc()
        sys.exit(2)

if __name__ == '__main__':
    run_checks()
