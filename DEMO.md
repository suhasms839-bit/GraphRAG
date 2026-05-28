# GraphRAG Learning Platform - Live Demo

## System Status: ✅ FULLY OPERATIONAL

The complete RAG system is working end-to-end with document ingestion, semantic search, and LLM-powered answer generation.

---

## Quick Demo (2 Minutes)

### 1. Start the System

```bash
npm run dev
```

**Servers Started:**

- Backend API: http://localhost:8001
- Frontend UI: http://localhost:5173 (or http://localhost:3000)
- API Docs: http://localhost:8001/docs

### 2. Login to Frontend

Navigate to: **http://localhost:5173**

**Test Account (Pre-configured):**

```
Email: suhasms839@gmail.com
Password: pass
```

### 3. Test Queries

Ask these questions on the chat interface:

#### Query 1: Material Composition

**Question:** "What material is used for the Aether-Core housing?"

**Expected Response:**

> "The Prism Squad utilizes advanced Crystalline-X composite materials for superior heat resistance. This material is exclusively sourced from Northern Extractives, a specialized subsidiary of Titan Strategic."

**Verification:**

- ✓ Answer includes specific material name (Crystalline-X)
- ✓ Source citations linked to uploaded documents
- ✓ Confidence score displayed

#### Query 2: Project Challenges

**Question:** "What are the main challenges in the project?"

**Expected Response:**

> "Project Aethelgard faces two primary challenges. Firstly, ensuring robust system security is critical... Secondly, the project encounters a significant supply chain dependency..."

**Verification:**

- ✓ Multi-sentence comprehensive answer
- ✓ Specific challenges identified from documents
- ✓ Source verification with page references

#### Query 3: Team Leadership

**Question:** "Who is the lead engineer for the Prism Squad?"

**Expected Response:**

> "Sarah Chen is the lead engineer for the Prism Squad, responsible for physical housing and thermal dissipation of the Aether-Core."

**Verification:**

- ✓ Specific name extraction
- ✓ Role identification
- ✓ Linked sources

---

## Key Features Demonstrated

### 1. **Authentication System**

- Secure login/signup
- User-isolated document storage
- Session management

### 2. **Document Management**

- Upload new documents
- Automatic chunking and embedding
- Vector storage in Chroma

### 3. **Intelligent Retrieval**

- Semantic search on uploaded content
- Multi-hop queries for complex relationships
- Ranked result ordering

### 4. **Answer Generation**

- LLM-powered responses (Gemini API)
- Cited answers with source tracking
- Confidence scoring

### 5. **Conversation History**

- Multi-turn conversations
- Source verification UI
- Citation expansion

---

## System Architecture (Running)

```
┌─────────────────┐
│  Frontend UI    │ (React 19 + Vite)
│  :5173          │
└────────┬────────┘
         │
         ├─────────────────────────────────┐
         │                                 │
    ┌────v─────────┐          ┌──────────v──────────┐
    │ API Server   │          │  Vector Store      │
    │ FastAPI      │◄────────►│  Chroma DB         │
    │ :8001        │          │  (Persistent)      │
    └────┬─────────┘          └────────────────────┘
         │
         ├──────────────────┬──────────────────┐
         │                  │                  │
    ┌────v────────┐    ┌────v────────┐  ┌───v──────────┐
    │ Database    │    │ LLM Service │  │ Graph Module │
    │ SQLAlchemy  │    │ Gemini API  │  │ (Optional)   │
    │ SQLite      │    │ + Ollama    │  │ Neo4j        │
    └─────────────┘    └─────────────┘  └──────────────┘
```

---

## Test Results

### Document Upload ✓

- File ingestion: **Working**
- Embedding generation: **Working**
- Vector storage: **Working**
- Chroma persistence: **Working**

### Semantic Retrieval ✓

- Keyword matching: **Working**
- Embedding similarity: **Working**
- Context ranking: **Working**
- Result filtering: **Working**

### Answer Generation ✓

- LLM inference: **Working**
- Citation extraction: **Working**
- Source linking: **Working**
- Response formatting: **Working**

### End-to-End Flow ✓

1. Upload document → ✓ Success
2. Generate embeddings → ✓ Success
3. Query backend → ✓ Success
4. Retrieve context → ✓ Success
5. Generate answer → ✓ Success
6. Display with citations → ✓ Success

---

## Pre-loaded Test Documents

The system includes pre-loaded documents for testing:

1. **Project Aethelgard Briefing** - Internal project documentation
   - Teams: Prism Squad, Flux Squad, Sentinel Squad
   - Technical specs, architecture, team leadership
   - Use cases: Material queries, team structure, project goals

2. **Titan Strategic Internal** - Company information
   - Supply chain details
   - Northern Extractives partnership
   - Business strategy

3. **Additional test documents** - Domain-specific content

---

## Upload a New Document

1. Click "View Documents" in sidebar
2. Upload a .txt or .pdf file
3. Wait for embedding (shows progress)
4. Ask questions about the new document

Example:

```
Upload: "my_project.txt"
Question: "What are the objectives in my project?"
```

---

## Performance Metrics

| Metric                | Result            |
| --------------------- | ----------------- |
| Document upload time  | < 5s              |
| Embedding generation  | < 3s per doc      |
| Query processing      | < 2s              |
| Answer generation     | < 5s (Gemini API) |
| Frontend load time    | < 2s              |
| Chat response display | Instant           |

---

## Troubleshooting During Demo

### Issue: Frontend shows "Cannot connect to API"

**Solution:**

- Ensure backend is running: `npm run dev`
- Check http://localhost:8001/health returns `{"status":"ok"}`

### Issue: Answer generation is slow

**Solution:**

- First query is slower (model loading)
- Subsequent queries are faster
- Check internet connection (Gemini API)

### Issue: Chat returns "requires specific context"

**Solution:**

- Upload a document first
- Wait for embedding to complete
- Ask questions matching document content

### Issue: Login fails

**Solution:**

- Clear browser cache
- Try test account: suhasms839@gmail.com / pass
- Check backend health endpoint

---

## Next Steps After Demo

1. **Create New Documents** - Upload your own content
2. **Fine-tune Retrieval** - Adjust similarity thresholds
3. **Customize LLM** - Switch to Ollama for offline mode
4. **Deploy** - See README.md for deployment options
5. **Extend** - Add custom evaluation metrics (RAGAS)

---

## GitHub Repository

**Repository:** https://github.com/suhasms839-bit/GraphRAG

**Branches:**

- `main` - Production releases
- `graphiti` - Development (current)

**Key Files:**

- `README.md` - Full documentation
- `app/api/server.py` - Backend entry point
- `frontend/src/App.tsx` - Frontend entry point
- `test_system_e2e.py` - Automated E2E test

---

## Support

For issues or questions:

1. Check [README.md](README.md) troubleshooting section
2. Run debug scripts: `scripts/debug/`
3. Review logs from `npm run dev`
4. Check API docs: http://localhost:8001/docs

---

**Last Tested:** May 15, 2026  
**System Status:** ✅ Fully Operational
