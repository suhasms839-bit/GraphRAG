# GraphRAG Learning Platform

A modern AI-powered learning and retrieval system that combines **Graph-based Retrieval-Augmented Generation (GraphRAG)** with a conversational interface for intelligent document analysis and knowledge discovery.

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
# API Keys
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

```bash
# Start both backend (FastAPI) and frontend (Vite) together
npm run dev
```

The app will be available at **http://localhost:3000**

- Frontend: http://localhost:3000
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs

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

### Building for Production

```bash
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

1. Keep changes modular and focused
2. Add tests under `tests/` for new features
3. Use manual scripts under `scripts/` for evaluation
4. Update this README if you change architecture or key workflows

---

## Support & Resources

- **Gemini API**: https://ai.google.dev
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **React Docs**: https://react.dev
- **LangChain**: https://python.langchain.com
- **RAGAS**: https://docs.ragas.io

---

## License

See LICENSE file for details.
