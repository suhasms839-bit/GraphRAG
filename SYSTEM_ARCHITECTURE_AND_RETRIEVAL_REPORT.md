# System Architecture and Retrieval/Augmentation Report

Date: 2026-04-26
Scope: Current implementation in this repository

## 1) Executive summary

This system is a full-stack GraphRAG learning platform with:
- React frontend (auth, chat, document upload, conversation history)
- Node/Express host process that starts Python backend and proxies API calls
- FastAPI backend with JWT auth, SQLAlchemy persistence, document ingestion, hybrid retrieval, graph augmentation, and Gemini-based generation
- Chroma vector store for per-user semantic retrieval
- Optional Neo4j graph layer for graph seed expansion and graph-path augmentation

The active, route-based production path is:
- Frontend -> /api/*
- Express proxy -> FastAPI app at app.api.server
- FastAPI routes in app/api/routes/*
- AgenticOrchestrator for response generation
- HybridRetriever + Graph querying + Gemini synthesis

## 2) Runtime topology

## 2.1 UI and gateway

- Frontend app shell and session gate: frontend/src/App.tsx
- Main user interactions (chat/documents/conversations): frontend/src/pages/DashboardPage.tsx
- Login/signup pages:
  - frontend/src/pages/LoginPage.tsx
  - frontend/src/pages/SignupPage.tsx

Frontend calls relative API paths (/api/auth/*, /api/chat/*, /api/documents/*), and sends JWT via Authorization: Bearer <token>.

- Node server starts Python backend and proxies /api: backend/server.ts
  - Starts python -m app.api.server on port 3001
  - Proxies /api to http://localhost:3001/api
  - Serves Vite middleware in development

## 2.2 Backend API entrypoint

Primary backend entrypoint: app/api/server.py

Responsibilities:
- Creates DB tables via SQLAlchemy metadata
- Applies schema patching for legacy users/documents columns
- Adds CORS middleware
- Includes routers:
  - app/api/routes/auth.py
  - app/api/routes/documents.py
  - app/api/routes/chat.py
- Exposes /health

Note: There is also backend/app/api/server.py, which appears to be a separate/older diagnostic-style app. The Node gateway currently starts app.api.server, not backend.app.api.server.

## 2.3 Storage layers

1. Relational DB (SQLAlchemy): app/core/database.py, app/core/models.py
- Defaults to sqlite:///./graphrag.db if DATABASE_URL absent
- Stores users, documents, chunks table, conversations, messages

2. Vector DB (Chroma): app/infrastructure/vectorstore/manager.py
- Persist directory from CHROMA_PERSIST_DIR (default ./chroma_db)
- User-scoped persistence under ./chroma_db/user_<id>
- Embedding model default: sentence-transformers/all-MiniLM-L6-v2

3. Graph DB (Neo4j, optional): app/domain/graph/graph_querying.py
- Connection from NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD
- If unavailable, graph retrieval gracefully returns empty

4. File storage
- Raw uploads at ./uploads/<user_id>/<user_id>_<filename>
- Text sidecar extraction for supported file types

## 3) API and conversation workflow

## 3.1 Authentication workflow

- Signup/login/me routes: app/api/routes/auth.py
- JWT generation/verification: app/core/security.py
- Frontend stores token in localStorage key authToken

## 3.2 Document upload workflow

Route: POST /api/documents/upload (app/api/routes/documents.py)

Steps:
1. Validate auth token and current user.
2. Validate MIME/extension allowlist.
3. Save binary file under user upload directory.
4. Extract text for indexing:
   - PDF via PyMuPDF (fitz)
   - TXT/CSV via utf-8 read
   - Unsupported types yield empty text
5. Persist document metadata row in DB.
6. If text exists, run VectorIngestionPipeline.ingest(...).
7. Persist ingestion status into documents.ingested/chunk_count/ingest_log.

Delete/list endpoints:
- GET /api/documents/list
- DELETE /api/documents/{document_id}

## 3.3 Chat workflow

Route: POST /api/chat/message (app/api/routes/chat.py)

Steps:
1. Auth + user resolution.
2. Resolve or create conversation.
3. Store user message.
4. Build compact history context (up to last 8 prior messages).
5. Build enriched question with history preamble.
6. Initialize user-scoped VectorStoreManager.
7. Run AgenticOrchestrator.run(question, topic_title).
8. Clean answer text; compute confidence label.
9. Save assistant message and return ChatResponse.

Debug endpoint:
- GET /api/chat/debug/retrieval?q=...
- Returns mode, confidence, scores, chunks, reranked details.

Conversation endpoints:
- GET /api/chat/conversations
- GET /api/chat/conversations/{id}
- DELETE /api/chat/conversations/{id}

## 4) Exact retrieval pipeline

Core file: app/domain/retrieval/hybrid_search.py
Class: HybridRetriever

Given query Q and k:

1. Query expansion (parallel)
- QueryRewriter.rewrite(Q): app/domain/retrieval/strategies/query_rewriting.py
  - Includes original Q
  - Deterministic keyword variant
  - Optional LLM rewrite variants (capped)
- HyDE generation: app/domain/retrieval/strategies/hypothetical_queries.py
  - LLM generates short hypothetical answer for better embedding match

2. Parallel vector retrieval
- For each expanded query variant, similarity_search via VectorStoreManager
- Deduplicate hits by content hash

3. Graph seed discovery (parallel and timeout-protected)
- query_graph_smart(Q, limit=3) in a thread
- wait_for timeout ~2.0s; fallback to empty graph seeds on timeout/error

4. Lexical reranking
- BM25 rank over collected hits: app/domain/retrieval/bm25.py

5. Fusion
- Reciprocal Rank Fusion across vector and BM25 order:
  - app/domain/retrieval/reranker.py
  - score = 1/(60 + vector_rank) + 1/(60 + bm25_rank)

6. Precision reranker (LLM-based, latency-guarded)
- PrecisionReranker.rerank(...): app/domain/retrieval/strategies/reranker.py
- LLM returns ranked_ids JSON
- Hard timeout from settings.RE_RANKER_TIMEOUT (default 0.5s in code path)
- On timeout/failure, fallback to fused top-k and mark reranker_skipped

7. Parent context enrichment
- For top hits, if parent_id exists, fetch related parent chunks from vector store

8. Per-hit scoring and graph contribution

For each final hit:
- vec_score from vector rank position
- bm25_score from BM25 rank position
- graph_score based on overlap(hit, graph_seed) * seed_score * path_decay
- graph signals disabled when:
  - related documents are not graph_ready in DB, or
  - reranker elapsed beyond timeout budget
- graph_score must pass GRAPH_MIN_TRUST threshold

Adaptive weight selection:
- If graph confidence high: heavier graph weight
- If very short query: heavier BM25 weight
- Else default blend

Combined raw:
- combined_raw = w_vec*vec_score + w_bm25*bm25_score + w_graph*graph_score
- clipped to [0,1]

Normalization:
- z-score + sigmoid normalization across candidate raw scores
- fallback rank-normalization when variance tiny

Confidence:
- top_score = max(normalized_scores)
- avg_top3 = mean(top 3 normalized)
- confidence = 0.6*top_score + 0.4*avg_top3

Mode classification:
- strong if top_score >= STRONG_CONTEXT_THRESHOLD (default 0.7)
- hybrid if top_score >= WEAK_CONTEXT_THRESHOLD (default 0.4) or confidence >= 0.5
- else fallback

Returned payload includes:
- hits, confidence, confidence_reason, detailed_hits, scores, mode, top_score, graph_used, reranker_skipped

## 5) Exact augmentation path

Augmentation happens at multiple levels:

## 5.1 Retrieval-time augmentation

1. Query augmentation
- Rewrites + HyDE synthetic query before search

2. Multi-source evidence augmentation
- Vector evidence + BM25 lexical signal + graph seeds

3. Parent-context augmentation
- Expands narrow chunks with parent context window

## 5.2 Graph augmentation

File: app/domain/graph/graph_querying.py

query_graph_smart performs:
- Text2Cypher generation from NL question (app/domain/graph/strategies/query_builder.py)
- Safe-check for read-only Cypher (rejects DELETE/REMOVE/SET)
- Fallback to terminology-map keyword query when no Cypher
- Optional Steiner-style shortestPath bridging between anchor chunk IDs from vector hits
- Seed scoring with overlap and length heuristics
- Returns graph snippets used as augmentation signals

## 5.3 Ingestion-time augmentation

File: app/domain/graph/graph_rag/vector_ingest.py

Pipeline:
1. Clean text (headers/footers/duplicates/whitespace)
2. Chunk with RecursiveCharacterTextSplitter (size 300, overlap 50)
3. Enrich metadata:
   - chunk_id, source, document_id, user_id, topic, subtopic, created_at
4. Write chunks to user-scoped Chroma collection
5. Async graph sync via graph_sync.upsert_entities_and_links
6. Mark document graph_ready true if sync succeeds

Graph sync details: app/domain/graph/graph_rag/graph_sync.py
- Upserts Chunk nodes
- Extracts candidate entities with heuristics
- Upserts Entity nodes and aliases
- Creates (Chunk)-[:MENTIONS]->(Entity)

## 5.4 Generation-time augmentation (orchestration)

Primary generator path: app/domain/agents/orchestrator.py

Flow in AgenticOrchestrator.run:
1. Force retrieval first via HybridRetriever.retrieve
2. If no hits, return general-knowledge fallback response
3. Build context_text from retrieved evidence
4. Construct structured system instruction requiring JSON schema output
5. Attempt direct Gemini synthesis first (fast path)
6. If needed, run short agentic loop with tool calling (max 2 iterations)
   - Tools: local_search, global_search, verify_answer
   - local_search re-runs hybrid retrieval and graph querying
   - global_search performs map-reduce over community summaries
7. Parse structured JSON answer when possible
8. Fallback best-effort answer from top excerpts if loop fails or rate-limited

LLM transport: app/domain/generation/llm_gateway.py
- call_gemini_text for text calls
- call_gemini_with_tools for tool-calling mode (v1beta endpoint)
- clean_response and format_final_output post-processing

## 6) GraphRAG-specific components (present state)

Implemented modules:
- Graph indexer and extraction prompts:
  - app/domain/graph/graph_rag/indexer.py
  - app/domain/graph/graph_rag/prompts.py
- Community detection/summarization/map-reduce:
  - app/domain/graph/graph_rag/community.py

Current practical status in runtime path:
- Graph augmentation is active through query_graph_smart and graph_sync hooks.
- Full community-based global search in orchestrator uses simulated community summaries in execute_tool(global_search), not DB-backed community store yet.
- Therefore, graph capabilities are partially productionized and partially scaffolded.

## 7) Configuration knobs controlling behavior

File: app/core/config.py

Most relevant retrieval/augmentation controls:
- EMBEDDING_MODEL
- STRONG_CONTEXT_THRESHOLD
- WEAK_CONTEXT_THRESHOLD
- SEED_SCORE_THRESHOLD
- GRAPH_MIN_TRUST
- MAX_GRAPH_PATH_DEPTH
- MAX_GRAPH_PATHS_PER_SEED
- MAX_CONTEXT_TOKENS
- CONTEXT_CHUNK_MIN_WORDS
- MAX_CONTEXT_CHUNKS
- Neo4j connection fields + AURA_WAIT_SECONDS

## 8) Data model alignment

File: app/core/models.py

Key entities:
- User
- Document (ingested, chunk_count, ingest_log, graph_ready)
- DocumentChunk (optional DB fallback retrieval source)
- Conversation and Message (chat persistence)

This alignment is important because retrieval graph usage is gated on Document.graph_ready, and fallback retrieval can query DocumentChunk or uploaded files.

## 9) Reliability and fallback behavior

Observed built-in fallbacks:
- If GEMINI_API_KEY missing: explicit message from LLM gateway
- If vector store empty/unavailable: DB/file fallback in similarity_search
- If Neo4j unavailable: graph query path returns [] without failing request
- If reranker timeout/error: fused ranking path used
- If retrieval empty: orchestrator returns general knowledge prompt-based response
- If tool-call loop errors or 429: orchestrator returns best-effort synthesis from retrieved snippets

This gives robust continuity, but response quality strongly depends on ingestion quality and graph readiness.

## 10) Important architecture observations

1. Two backend app entrypoints exist
- app/api/server.py (active via Node gateway)
- backend/app/api/server.py (alternate/legacy diagnostic app)

2. Route-based API path uses AgenticOrchestrator
- Legacy answer_with_rag exists but is not the primary /api/chat/message path.

3. Graph global search in tool mode is currently simulated
- Not yet pulling persisted community summaries from Neo4j.

4. Retrieval sophistication is high
- Query rewrite + HyDE + BM25 + RRF + optional LLM rerank + graph trust gating + adaptive weighting.

## 11) End-to-end sequence (chat)

1. User submits question in frontend dashboard
2. Frontend POST /api/chat/message with Bearer token
3. Express proxy forwards to FastAPI
4. FastAPI route stores message and prepares history-enriched query
5. AgenticOrchestrator invokes HybridRetriever
6. Retriever performs expanded multi-query vector search + BM25 + RRF + rerank + graph-seed scoring
7. Orchestrator composes evidence context and calls Gemini (direct or tool loop)
8. Answer cleaned and persisted as assistant message
9. Frontend refreshes conversation and renders response with confidence/citations

## 12) Suggested next hardening steps

1. Unify backend entrypoints
- Keep one canonical FastAPI app, retire or clearly label alternate app.

2. Replace simulated global community data
- Persist and query real community summaries from Neo4j.

3. Add explicit observability
- Persist retrieval diagnostics per response (mode, top_score, graph_used, reranker_skipped).

4. Strengthen ingestion consistency
- Add extraction for DOC/DOCX or reject them explicitly to avoid empty-ingest surprises.

5. Add integration tests for retrieval modes
- strong/hybrid/fallback transitions and graph_ready gating.

## 13) Key implementation files index

Core runtime:
- backend/server.ts
- app/api/server.py
- app/api/routes/auth.py
- app/api/routes/documents.py
- app/api/routes/chat.py

Retrieval + augmentation:
- app/domain/retrieval/hybrid_search.py
- app/domain/retrieval/bm25.py
- app/domain/retrieval/reranker.py
- app/domain/retrieval/strategies/query_rewriting.py
- app/domain/retrieval/strategies/hypothetical_queries.py
- app/domain/retrieval/strategies/reranker.py
- app/domain/agents/orchestrator.py
- app/domain/agents/tools.py
- app/domain/generation/llm_gateway.py
- app/domain/graph/graph_querying.py
- app/domain/graph/strategies/query_builder.py
- app/domain/graph/strategies/schema.py
- app/domain/graph/graph_rag/vector_ingest.py
- app/domain/graph/graph_rag/graph_sync.py
- app/domain/graph/graph_rag/community.py

Persistence/config:
- app/core/config.py
- app/core/database.py
- app/core/models.py
- app/core/schemas.py
- app/core/security.py

Frontend:
- frontend/src/App.tsx
- frontend/src/pages/LoginPage.tsx
- frontend/src/pages/SignupPage.tsx
- frontend/src/pages/DashboardPage.tsx
