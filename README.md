# GraphRAG Learning Platform

A modern AI-powered learning and retrieval system that combines **Graph-based Retrieval-Augmented Generation (GraphRAG)** with a conversational interface for intelligent document analysis and knowledge discovery.

> **Status**: ✅ Fully functional. Document ingestion, semantic search, and LLM-powered Q&A with source citations working end-to-end.

---

## 🎬 Demo

### Live Screenshot (System Running)
The platform includes a full-stack RAG system with:
- **User Authentication** - Secure login/signup
- **Document Management** - Upload and process documents
- **Intelligent Chat Interface** - Multi-turn conversations with source verification
- **Citation System** - All answers include linked sources and page numbers

**Test Account (Pre-configured):**
```
Email: suhasms839@gmail.com
Password: pass
```

### Quick Test (2 minutes)

1. Start the system: `npm run dev`
2. Open http://localhost:5173 (or http://localhost:3000)
3. Login with test account above
4. Try these questions on pre-loaded documents:
   - "What material is used for the Aether-Core housing?"
   - "What are the main challenges in the project?"
   - "Who is the lead engineer for the Prism Squad?"

**Expected Output:** AI generates cited answers pulling from uploaded documents with source verification ✓

---

## Features

- 📚 **Document Upload & Ingestion**: Upload text, PDF, and other documents for intelligent processing
- 🔍 **Advanced Retrieval**: Multi-hop retrieval with graph-based context awareness
- 🤖 **AI-Powered Responses**: Generate accurate, cited answers using Gemini or local LLMs (Ollama)
- 👥 **Multi-User Support**: Isolated document collections per user with auth
- 📊 **RAG Evaluation**: Built-in evaluation metrics (RAGAS) for response quality
- 🏗️ **Modular Architecture**: Clean separation of concerns with dedicated domain modules

---

## Prerequisites

- **Node.js** 18+ (for frontend and dev server)
- **Python** 3.11+ (for backend)
- **pip** (Python package manager)
- **GEMINI_API_KEY** (from Google AI Studio) or **Ollama** for local LLMs

Optional:

- **Neo4j** for graph storage (can use SQLite fallback)
- **Chroma** vector database (included)

---

## Quick Start

### 1. Clone and Install

```bash
# Install Node dependencies
npm install

# Set up Python environment (optional, if not already set up)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install Python dependencies
pip install -r backend/requirements.txt
```

### 2. Configure Environment

Create `.env.local` in the project root:

```env
# API Keys (Required)
GEMINI_API_KEY=your_gemini_api_key_here

# Ollama (optional, for local LLMs)
USE_OLLAMA=false
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1

# Database
DATABASE_URL=sqlite:///./test.db
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### 3. Start the Application

#### Option A: Full Stack (Recommended for Development)
```bash
# Starts both FastAPI backend + Express proxy + Vite frontend
npm run dev
```
- Frontend: http://localhost:3000 (or http://localhost:5173 for standalone)
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs

#### Option B: Individual Servers

**Terminal 1 - Backend (FastAPI):**
```bash
python app/api/server.py
```
Backend runs on http://localhost:8001

**Terminal 2 - Frontend (Vite):**
```bash
cd frontend
npm run dev
```
Frontend runs on http://localhost:5173

---

## Project Structure

```
graphrag-learning-platform/
├── app/                          # FastAPI backend + domain logic
│   ├── api/
│   │   ├── server.py            # Main FastAPI app (canonical entry point)
│   │   └── routes/              # API endpoints (auth, chat, documents, system)
│   ├── core/                    # Core utilities (config, logging, auth, DB)
│   ├── domain/                  # Business logic modules
│   │   ├── agents/              # AI orchestration & agentic flows
│   │   ├── generation/          # Answer generation & synthesis
│   │   ├── graph/               # Graph RAG pipeline & querying
│   │   ├── retrieval/           # Semantic search & context retrieval
│   │   ├── learning/            # Course & learning path generation
│   │   └── evaluation/          # RAG quality metrics & benchmarking
│   └── infrastructure/          # External integrations
│       ├── db/                  # Database adapters
│       └── vectorstore/         # Vector DB (Chroma) management
├── frontend/                    # Vite + React UI
│   ├── src/
│   │   ├── App.tsx              # Main component
│   │   ├── pages/               # Page components (Login, Dashboard, etc.)
│   │   └── components/          # Reusable React components
│   ├── vite.config.ts           # Vite build config
│   └── index.html               # Entry point
├── backend/
│   ├── server.ts                # Dev server entry (starts both Python & Node)
│   └── deprecated/              # Legacy code (archived)
├── tests/                       # Pytest automated tests
│   └── integration/
├── scripts/                     # Manual testing & evaluation tools
│   ├── debug/                   # Troubleshooting scripts
│   ├── evaluation/              # RAG quality runners
│   └── integration/             # Component & E2E test scripts
├── uploads/                     # User-uploaded documents
├── chroma_db/                   # Vector database storage
└── README.md                    # This file
```

---

## Usage

### Running the App

**Development (both servers):**

```bash
npm run dev
```

**Production build:**

```bash
npm run build
npm start
```

### Accessing the Application

1. **Web UI**: http://localhost:3000
   - Sign up or log in
   - Upload documents
   - Chat and ask questions

2. **API**: http://localhost:8001/api
   - Interactive docs: http://localhost:8001/docs
   - Endpoints:
     - `POST /api/auth/signup` - Create account
     - `POST /api/auth/login` - Log in
     - `POST /api/documents/upload` - Upload document
     - `POST /api/chat` - Send query
     - `GET /api/system/health` - Health check

### Example API Workflow

```bash
# 1. Sign up
curl -X POST http://localhost:8001/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Pass123!","username":"user1","full_name":"User One"}'

# 2. Log in
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Pass123!"}' > login_response.json

# Extract token from response and set it:
export TOKEN=$(jq -r '.access_token' login_response.json)

# 3. Upload a document
curl -X POST http://localhost:8001/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@path/to/document.txt"

# 4. Chat and get answers
curl -X POST http://localhost:8001/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the main topic in the document?",
    "topic": "General"
  }'
```

---

## Testing

### Automated Tests

```bash
# Run all pytest tests (only from tests/ folder)
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test
python -m pytest tests/integration/test_multihop_query.py::test_multihop_generation
```

### Manual Testing Scripts

See [scripts/](scripts/) for manual debugging and evaluation:

- **Integration tests**: `scripts/integration/test_e2e_v3.py`
- **Ingestion tests**: `scripts/integration/test_ingestion_v3.py`
- **RAG quality**: `scripts/evaluation/ragas_evaluation.py`
- **Debugging**: `scripts/debug/db_inspect.py`, `scripts/debug/debug_retrieval_run.py`

---

## System Architecture

### Data Flow

1. **Document Upload** → Cleaning & chunking → **Vector embedding** (Hugging Face models)
2. **Vector storage** → Chroma (semantic search)
3. **Graph extraction** → Entity & relationship extraction → Neo4j storage
4. **Query processing** → Multi-hop retrieval → Context ranking
5. **Answer generation** → LLM synthesis (Gemini or Ollama) → Cited response

### Key Components

- **VectorStoreManager**: Handles document ingestion and similarity search
- **AgenticOrchestrator**: Coordinates multi-step reasoning flows
- **GraphRAGIndexer**: Extracts entities and relationships for graph storage
- **AnswerEngine**: Generates cited responses using retrieved context
- **CourseBuilder**: Creates structured learning paths

---

## Configuration

### Environment Variables (`.env.local`)

```env
# LLM Configuration
GEMINI_API_KEY=sk-...
USE_OLLAMA=false

# Database
DATABASE_URL=sqlite:///./test.db
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Application
APP_DEBUG=true
LOG_LEVEL=INFO
```

### .env.local for Ollama (Local LLM)

```env
USE_OLLAMA=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
GEMINI_API_KEY=  # Optional fallback
```

For detailed Ollama setup, see [OLLAMA_SETUP.md](OLLAMA_SETUP.md).

---

## Troubleshooting

### Frontend 404 errors

- Ensure `frontend/src/` exists with `main.tsx` and `App.tsx`
- Rebuild frontend: `cd frontend && npm install && npm run dev`

### Backend connection errors

- Check Python environment is activated: `.venv\Scripts\activate`
- Verify port 8001 is available
- Check logs: `npm run dev` shows both Node and Python output

### Document ingestion fails

- Verify file format is supported (txt, pdf)
- Check disk space for uploads folder
- See `scripts/debug/check_ragas_preflight.py` for diagnostics

### Vector search returns no results

- Ensure documents are uploaded and ingested
- Verify Chroma DB is initialized: `chroma_db/` folder exists
- Run `scripts/debug/debug_retrieval_run.py` to test retrieval pipeline

---

## Deployment

### GitHub Repository Setup

1. **Create GitHub repository:**
   ```bash
   # Initialize and push to GitHub (if not already done)
   git add .
   git commit -m "Initial commit: GraphRAG Learning Platform - Full stack RAG system with document upload, retrieval, and chat"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/graphrag-learning-platform.git
   git push -u origin main
   ```

2. **Branching Strategy:**
   - `main` - Production-ready releases
   - `graphiti` - Development branch (current)
   - Feature branches - `feature/feature-name`

### Docker Deployment

Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8001:8001"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - DATABASE_URL=sqlite:///./test.db
    volumes:
      - ./chroma_db:/app/chroma_db
      - ./uploads:/app/uploads

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    depends_on:
      - backend
```

Deploy with:
```bash
docker-compose up -d
```

### Building for Production

```bash
# Build frontend bundle
npm run build

# Backend deployment (see Dockerfile.backend)
# For production, consider running:
# - Vite build output on a static file server (nginx, etc.)
# - FastAPI backend on a ASGI server (gunicorn, hypercorn)
```

---
# Build frontend bundle
npm run build

# The backend can be deployed separately or as part of the Node server
# For production, consider running:
# - Vite build output on a static file server (nginx, etc.)
# - FastAPI backend on a ASGI server (gunicorn, hypercorn)
```

### Docker (Optional)

Create `Dockerfile` and `docker-compose.yml` for containerized deployment.

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and test locally: `npm run dev` + manual testing
3. Add tests under `tests/` for new features
4. Commit with clear messages: `git commit -m "Add feature: description"`
5. Push and create a Pull Request to `main` branch

### Code Organization

- **Backend logic**: `app/domain/` (agents, generation, retrieval, graph)
- **API routes**: `app/api/routes/` (one file per resource: auth, chat, documents)
- **Core utilities**: `app/core/` (config, security, logging, database models)
- **Tests**: `tests/` (pytest, one file per module)
- **Scripts**: `scripts/` (organized by debug, evaluation, integration, setup)

---

## Support & Resources

- **Gemini API**: https://ai.google.dev
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **React Docs**: https://react.dev
- **Vite**: https://vitejs.dev
- **LangChain**: https://python.langchain.com
- **RAGAS Evaluation**: https://docs.ragas.io
- **Chroma Vector DB**: https://docs.trychroma.com

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| 404 on frontend | Ensure `frontend/src/` exists with `main.tsx` and `App.tsx` |
| Backend connection fails | Check Python env activated: `.venv\Scripts\activate`, port 8001 free |
| Document upload fails | Verify file format (txt, pdf), check `uploads/` folder writable |
| Vector search empty | Upload documents first, verify `chroma_db/` exists, run `scripts/debug/debug_retrieval_run.py` |
| 500 on signup | Check backend logs, ensure `.env.local` has valid GEMINI_API_KEY |
| Port already in use | Kill existing processes: `netstat -ano \| findstr :8001` (Windows) |

### Debug Scripts

```bash
# Check system health
python scripts/debug/check_ragas_preflight.py

# Inspect vector database
python scripts/debug/db_inspect.py

# Test retrieval pipeline
python scripts/debug/debug_retrieval_run.py

# Run end-to-end test
python test_system_e2e.py
```

---

## License

MIT License - See LICENSE file for details.

---

## Project Stats

- **Backend**: FastAPI + SQLAlchemy + LangChain
- **Frontend**: React 19 + Vite 6 + TypeScript
- **Vector DB**: Chroma (persistent local storage)
- **LLM**: Gemini API (primary) + Ollama (fallback)
- **Python**: 3.11+
- **Node**: 18+
