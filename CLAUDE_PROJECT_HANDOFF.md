# Project Handoff Report for Claude

## Purpose

This document explains the project from first principles so another coding agent can rebuild it, understand its current state, and continue development safely.

The repository is a full-stack GraphRAG learning platform named **Sincra**. It combines document ingestion, per-user semantic retrieval, graph augmentation, LLM response generation, authentication, and an optional Gmail MCP integration for query augmentation.

The goal of this handoff is twofold:

1. Explain the architecture from scratch.
2. Describe the current implementation level so future changes can build on the existing code instead of rewriting it.

---

## 1. What This Project Is

Sincra is an AI-powered learning and retrieval platform that lets users:

- Sign up and log in with JWT-based auth.
- Upload documents such as PDF, TXT, CSV, DOC, and DOCX.
- Ingest those documents into a per-user vector store.
- Optionally enrich retrieval with a Neo4j knowledge graph.
- Ask natural-language questions and receive grounded answers with citations.
- Use either Gemini or Ollama as the generation backend.
- Augment answers with Gmail context through a separate MCP subprocess when enabled.

This is not a generic chatbot. It is a retrieval system where the quality of the answer depends on ingestion quality, retrieval quality, graph expansion, reranking, and context selection.

---

## 2. Project Goal in One Sentence

Build a production-oriented GraphRAG system that can ingest documents, retrieve relevant evidence, optionally augment with graph and Gmail context, and generate cited answers with confidence scoring.

---

## 3. High-Level Architecture

The system has four major layers:

### A. Frontend

- React 19 + Vite + TypeScript
- Handles login, signup, chat UI, document upload, and conversation history
- Communicates with backend APIs using JWT in the Authorization header

### B. Gateway / Host

- A Node/Express host process exists in `backend/server.ts`
- It proxies `/api` traffic and can start the Python backend in development

### C. Backend API

- FastAPI app in `app/api/server.py`
- Routes are split by domain:
  - `auth`
  - `documents`
  - `chat`
  - `system`
  - `mcp`
  - `mcp_auth`
- Uses SQLAlchemy for persistence
- Uses operational middleware such as request IDs, body-size limiting, rate limiting, and CORS restrictions

### D. Retrieval and Generation Domain

- Vector retrieval through Chroma
- Graph retrieval through Neo4j
- Query rewriting, BM25 ranking, reciprocal rank fusion, and reranking
- LLM orchestration through Gemini or Ollama

---

## 4. Current Codebase Map

Important backend files:

- `app/api/server.py` - FastAPI app entrypoint and router registration
- `app/api/routes/auth.py` - signup, login, current-user endpoint
- `app/api/routes/documents.py` - upload/list/delete document endpoints
- `app/api/routes/chat.py` - chat and conversation endpoints
- `app/api/routes/mcp.py` - Gmail MCP context endpoint
- `app/api/routes/mcp_auth.py` - Gmail OAuth start/callback endpoints
- `app/core/config.py` - environment-driven configuration
- `app/core/database.py` - SQLAlchemy engine/session/base setup
- `app/core/models.py` - ORM models
- `app/core/security.py` - password hashing and JWT helpers
- `app/infrastructure/mcp_client.py` - MCP subprocess client
- `app/infrastructure/google_oauth.py` - OAuth loading, token persistence, encryption, refresh helpers
- `app/domain/agents/mcp_context.py` - Gmail gating and user-aware MCP lookup
- `app/domain/agents/orchestrator.py` - answer orchestration
- `app/domain/retrieval/hybrid_search.py` - hybrid retrieval logic
- `app/domain/graph/graph_rag/vector_ingest.py` - ingestion pipeline
- `app/infrastructure/vectorstore/manager.py` - Chroma access

Important frontend files:

- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/index.css`
- `frontend/src/pages/*`

Useful scripts:

- `scripts/migrations/upgrade_schema.py` - schema bootstrap
- `scripts/integration/*` - smoke and end-to-end checks
- `tests/integration/test_mcp.py` - MCP gating tests
- `tests/integration/test_mcp_auth.py` - OAuth/token persistence tests

---

## 5. Data Model

The SQLAlchemy models in `app/core/models.py` currently define:

- `User`
- `Document`
- `DocumentChunk`
- `Conversation`
- `Message`
- `Telemetry`
- `UserMcpToken`

### Key storage concepts

- Users own documents and conversations.
- Documents are metadata rows for uploaded files.
- Document chunks hold extracted chunk text and embeddings.
- Conversations and messages power the chat history.
- Telemetry stores operational events.
- `UserMcpToken` stores Gmail OAuth material per user.

### Gmail token storage

The Gmail persistence model stores:

- `user_id`
- `access_token`
- `refresh_token`
- `token_uri`
- `client_id`
- `client_secret`
- `scopes`
- `expiry`
- `updated_at`

This enables per-user Gmail context retrieval and token refresh.

---

## 6. Ingestion Pipeline

Document ingestion is the first foundation of the RAG system.

### Current behavior

1. The user uploads a document.
2. The backend validates file type and auth.
3. Text is extracted from the file.
4. The document metadata is stored.
5. The extracted text is chunked.
6. Chroma embeddings are generated and stored.
7. Optional graph sync enriches the knowledge graph.
8. The document is marked as ingested.

### Key design points

- Text extraction is best-effort, not brittle.
- Chunks are user-scoped.
- Embeddings are generated only after cleaning and splitting.
- Graph readiness is tracked so retrieval can use graph signals only when available.

### Why this matters

If ingestion is weak, retrieval cannot be strong. The rest of the system depends on this layer being stable and explainable.

---

## 7. Retrieval Pipeline

The retrieval layer is the intelligence layer of the system.

### Current retrieval path

1. Accept user query.
2. Rewrite the query when needed.
3. Retrieve top-k candidate chunks from the vector store.
4. Optionally add graph-derived seeds.
5. Apply lexical reranking and score fusion.
6. Apply a precision reranker when available.
7. Select a compact final context.
8. Pass that context to the generator.

### Retrieval characteristics

- It is not single-vector search.
- It is a hybrid system combining semantic search, graph signals, and lexical scoring.
- It uses confidence scoring to characterize answer quality.
- It is built to fail safely when one signal is unavailable.

### Important retrieval files

- `app/domain/retrieval/hybrid_search.py`
- `app/domain/retrieval/bm25.py`
- `app/domain/retrieval/reranker.py`
- `app/domain/retrieval/strategies/*`
- `app/domain/graph/graph_querying.py`

### Confidence behavior

Current logic computes confidence from candidate scores and maps outputs into labels such as high, medium, or low confidence.

---

## 8. Generation Flow

The generation layer takes retrieved context and produces the final answer.

### Current behavior

1. The chat route receives a question.
2. The system builds a conversation history window.
3. Retrieval runs first.
4. The orchestrator builds a response prompt.
5. Gemini or Ollama generates the answer.
6. The response is cleaned and stored.
7. The message and metadata are persisted.

### Output expectations

The system aims for answers that include:

- Clear grounded response
- Citations or source references
- Confidence information
- Fallback behavior when retrieval is weak

### Important orchestration file

- `app/domain/agents/orchestrator.py`

---

## 9. Authentication and Security

### JWT auth

- Signup and login issue JWTs.
- `Authorization: Bearer <token>` is used on protected routes.
- `app/core/security.py` owns token signing and verification.

### Security guardrails already in the repo

- CORS is environment-driven
- Request IDs are attached to requests and responses
- Body-size limits are enforced
- Basic rate limiting exists
- Schema creation is moved out of import-time startup side effects
- Production deployment uses environment-driven configuration

### Why this matters

The project is already moving from a development prototype toward production-safe defaults.

---

## 10. Gmail MCP Integration

This is a major extension to the core RAG system.

### What it does

When a query looks email-related, the system can ask a Gmail MCP subprocess for additional context.

### Current Gmail flow

1. User starts OAuth flow at `/api/mcp/auth/start`.
2. Consent is granted through Google.
3. Google redirects to `/api/mcp/auth/callback`.
4. The code is exchanged for Gmail tokens.
5. Tokens are stored in `user_mcp_tokens`.
6. Gmail queries are keyword-gated in `app/domain/agents/mcp_context.py`.
7. The MCP client is called with user-specific environment variables when a token exists.
8. If token lookup or refresh fails, the system falls back safely instead of crashing.

### Gmail integration files

- `app/api/routes/mcp_auth.py`
- `app/infrastructure/google_oauth.py`
- `app/infrastructure/mcp_client.py`
- `app/domain/agents/mcp_context.py`
- `app/api/routes/mcp.py`

### Important design decision

This integration is fail-closed and optional. Normal RAG queries should still work if Gmail is unavailable.

---

## 11. Deployment Readiness

The project has already been hardened in several ways:

- Runtime configuration is env-driven
- DB schema bootstrapping is externalized
- Request limits and rate limits exist
- CORS is restricted by configuration
- OAuth tokens can be encrypted at rest when supported
- Tests exist for the MCP and Gmail OAuth flow

### Remaining deployment tasks

- Finalize Docker startup commands and migration invocation
- Ensure production env vars are documented clearly
- Decide whether to use a secrets manager for Gmail client secrets
- Add stronger end-to-end tests for the live MCP binary contract
- Consider replacing `datetime.utcnow()` with timezone-aware UTC timestamps everywhere

---

## 12. How to Rebuild the Project From Scratch

If Claude were rebuilding this project from zero, the correct order is:

### Phase 1: Core app scaffolding

- Create the FastAPI backend
- Create SQLAlchemy models and DB session management
- Add JWT auth
- Add upload and chat routes
- Add a basic React frontend shell

### Phase 2: Ingestion foundation

- Implement file uploads
- Extract clean text
- Split into semantically meaningful chunks
- Generate embeddings
- Store chunks in Chroma per user

### Phase 3: Retrieval intelligence

- Add query rewriting
- Add hybrid retrieval
- Add graph retrieval if Neo4j exists
- Add reranking and confidence scoring

### Phase 4: Generation layer

- Connect retrieval to prompt construction
- Add Gemini/Ollama answer generation
- Persist conversations and messages

### Phase 5: Production hardening

- Add request IDs, body limits, rate limits
- Externalize schema creation into migrations
- Add Docker and deployment docs
- Add observability and readiness checks

### Phase 6: Gmail augmentation

- Add OAuth start/callback flow
- Persist user Gmail credentials
- Refresh tokens when needed
- Inject per-user context into MCP subprocesses
- Gate Gmail queries so normal RAG traffic is unaffected

---

## 13. Current State Summary

As of now, the repository contains:

- A functioning FastAPI backend
- JWT auth
- Document ingestion and retrieval infrastructure
- Hybrid GraphRAG components
- Operational middleware and env-driven configuration
- Gmail OAuth start/callback and token persistence
- Per-user Gmail MCP environment injection
- Focused integration tests that pass locally

This means the project is no longer just a prototype. It has a real backend architecture, user auth, retrieval pipeline, and an extensible integration layer.

---

## 14. Known Gaps and Follow-Ups

These are the main remaining items if the goal is deployment-grade polish:

- Add stronger production secrets management
- Replace any remaining plaintext secret handling with centralized encryption or vault storage
- Continue consolidating duplicate routes or legacy paths if they exist
- Replace any remaining startup side effects with explicit migration steps
- Add more end-to-end tests around the real MCP subprocess and Google OAuth contracts
- Tighten docs for deployment and local onboarding

---

## 15. Short Explanation Claude Can Reuse

If you need a concise summary to explain the project in another context:

Sincra is a production-oriented GraphRAG platform built with FastAPI, React, SQLAlchemy, Chroma, and Neo4j. It ingests user documents, chunks and embeds them, retrieves relevant context with hybrid semantic/graph ranking, and generates grounded answers with citations and confidence scoring. It also includes a Gmail MCP integration that stores OAuth tokens per user and injects Gmail context into relevant queries.

---

## 16. Recommended Files to Read First

If Claude needs to continue work, start with these files:

1. `app/api/server.py`
2. `app/core/models.py`
3. `app/core/config.py`
4. `app/api/routes/auth.py`
5. `app/api/routes/documents.py`
6. `app/api/routes/chat.py`
7. `app/domain/retrieval/hybrid_search.py`
8. `app/domain/agents/orchestrator.py`
9. `app/infrastructure/google_oauth.py`
10. `app/domain/agents/mcp_context.py`

---

## 17. Current Verification Status

The following focused test slice passed locally:

- `tests/integration/test_mcp.py`
- `tests/integration/test_mcp_auth.py`

This verifies:

- Gmail keyword gating
- OAuth state flow
- Token persistence
- Per-user MCP env construction
- Safe fallback behavior when tokens are unavailable

---

## 18. Final Handoff Note

The repository is in a stage where Claude can continue from a well-defined architecture instead of reconstructing the system mentally. The project now has a clear core: authenticated GraphRAG, production guardrails, and Gmail-powered augmentation.

If the next step is to make it fully deployment-ready, focus on packaging, secret management, and end-to-end integration validation.
