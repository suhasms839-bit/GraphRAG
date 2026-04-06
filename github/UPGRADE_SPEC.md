# ROLE

You are an expert Backend Engineer specialized in RAG/GraphRAG.

# TASK

Your goal is to implement the following system upgrade.

# RULES

1. Follow the version 3.0 specs strictly.
2. If a coding suggestion contradicts these specs, prioritize the specs.
3. Use modular, clean code for each step.

🚀 RAG / GraphRAG SYSTEM — COMPLETE UPGRADE INSTRUCTION FILE (v3.0)

---

🎯 OBJECTIVE

Upgrade your current system from ~8.5/10 → 9+/10 production-ready level by fixing:

- Retrieval quality
- Grounding clarity
- Fallback intelligence
- Conversation continuity
- System explainability

---

🏗️ STEP 1: INGESTION PIPELINE (FOUNDATION)

1.1 Data Cleaning (MANDATORY)

Before storing anything:

- Remove headers, footers, page numbers
- Remove duplicate text
- Normalize whitespace
- Convert to clean paragraphs

---

1.2 Semantic Chunking (CRITICAL UPGRADE)

DO NOT use fixed-size naive splitting.

Implement:

- Chunk size: 300–500 tokens
- Overlap: 50–100 tokens
- Split by:
  - Headings
  - Paragraphs
  - Meaning boundaries

Goal:

Each chunk should represent one complete idea

---

1.3 Metadata Enrichment (REQUIRED)

For every chunk:

{
"chunk_id": "uuid",
"source": "file_name.pdf",
"topic": "computer_networks",
"subtopic": "topology",
"created_at": "timestamp"
}

Why:

- Enables filtering
- Improves retrieval precision
- Adds explainability

---

1.4 Embedding Generation

Use strong embeddings:

- Preferred: high-quality embedding model (latest available)
- Alternative: open-source large embedding models

Rule:

- Generate embedding AFTER cleaning + chunking

---

1.5 Storage

Store in vector DB:

- FAISS / Chroma / Pinecone

Each record:

(chunk_text, embedding, metadata)

---

✅ INGESTION VALIDATION CHECK

- [ ] Clean text
- [ ] Semantic chunks
- [ ] Metadata present
- [ ] Embeddings generated
- [ ] Stored in DB

---

🔎 STEP 2: RETRIEVAL PIPELINE (INTELLIGENCE LAYER)

---

2.1 Query Preprocessing

Add Query Rewriting:

if query_is_short_or_vague:
expand_query()

Example:
"bus topology" →
"what is bus topology in computer networks"

---

2.2 Retrieval (Top-K)

- Use Top-K = 5 to 10
- Never rely on single document

---

2.3 Metadata Filtering

If topic detected:

- Filter by metadata

Example:

topic = "networking"

---

2.4 Reranking (HIGH IMPACT)

After retrieval:

- Apply reranker (cross-encoder)

Effect:

- Removes irrelevant chunks
- Boosts accuracy significantly

---

2.5 Confidence Scoring

confidence = max(similarity_scores)

Thresholds:

- «0.75 → High»
- 0.5–0.75 → Medium
- < 0.5 → Low

---

2.6 Final Context Selection

- Select top 3–5 chunks after reranking
- Pass ONLY relevant context to LLM

---

✅ RETRIEVAL VALIDATION

- [ ] Query rewriting working
- [ ] Top-K retrieval used
- [ ] Reranking applied
- [ ] Confidence computed

---

🧠 STEP 3: GENERATION FLOW (LLM RESPONSE DESIGN)

---

3.1 Prompt Template (USE EXACT STRUCTURE)

You are a helpful AI assistant using retrieved documents.

Context:
{retrieved_chunks}

Conversation History:
{chat_history}

User Question:
{query}

Instructions:

1. Answer using the context.
2. If context is incomplete, use general knowledge but clearly state it.
3. Structure response as:
   - Definition
   - Key Points
   - Limitations (if applicable)
4. Be clear and concise.

Output Format:

[Answer]
...

[Source]

- Retrieved documents / General knowledge

[Confidence]
High / Medium / Low

---

3.2 Output Rules

MUST:

- Always answer (never return empty)
- Always include:
  - Source section
  - Confidence level

---

3.3 Example Output

[Answer]
Bus topology is a network structure...

[Source]
Retrieved documents on network topology

[Confidence]
High

---

✅ GENERATION VALIDATION

- [ ] Structured output
- [ ] Source mentioned
- [ ] Confidence included

---

🔁 STEP 4: FALLBACK LOGIC (SMART HANDLING)

---

4.1 Implement Multi-Level Fallback

if confidence > 0.75:
answer_from_docs()

elif 0.5 < confidence <= 0.75:
answer_docs_plus_general()

else:
answer_general_with_disclaimer()

---

4.2 Behavior

HIGH:

- Fully grounded

MEDIUM:

- Combine docs + LLM knowledge

LOW:

- Use general knowledge
- Add disclaimer:
  "Retrieved documents contain limited information"

---

✅ FALLBACK VALIDATION

- [ ] No empty responses
- [ ] Graceful degradation
- [ ] Proper disclaimers

---

💬 STEP 5: CONVERSATION MEMORY (CHAT CONTINUITY)

---

5.1 Store History

[
{"role": "user", "content": "..."},
{"role": "assistant", "content": "..."}
]

---

5.2 Use in Retrieval (IMPORTANT)

Rewrite queries using history:

Example:
Q1: "What is topology?"
Q2: "Explain bus type"

→ Final query:
"Explain bus topology in computer networks"

---

5.3 Memory Window

- Keep last 3–5 messages only
- Avoid token overload

---

5.4 Optional (Advanced)

- Store conversation summary
- Use it for long sessions

---

✅ MEMORY VALIDATION

- [ ] History stored
- [ ] Used in query rewriting
- [ ] Context-aware answers

---

🎨 STEP 6: CHAT INTERFACE (UX UPGRADE)

---

REQUIRED FEATURES

- Typing indicator
- Smooth response rendering
- Clear formatting

---

DISPLAY

- Show:
  - Answer
  - Source
  - Confidence badge

---

OPTIONAL (HIGH IMPACT)

- Expandable sources section
- Highlight retrieved text
- Loading animation

---

📊 STEP 7: EVALUATION SYSTEM

---

7.1 Metrics

Track:

1. Answer relevance
2. Grounding accuracy
3. Latency
4. Fallback correctness

---

7.2 Test Queries

Normal:

- "What is bus topology?"

Vague:

- "Explain bus type"

Out-of-scope:

- "What is quantum physics?"

---

7.3 Expected Behavior

Case| Expected
Normal| Strong grounded answer
Vague| Query rewritten + correct answer
Out-of-scope| General answer + disclaimer

---

🏁 FINAL SYSTEM CHECKLIST

---

INGESTION

- [ ] Cleaned data
- [ ] Semantic chunks
- [ ] Metadata added

RETRIEVAL

- [ ] Query rewriting
- [ ] Top-K retrieval
- [ ] Reranking
- [ ] Confidence scoring

GENERATION

- [ ] Structured output
- [ ] Source + confidence

CHAT

- [ ] Memory-aware
- [ ] Context continuity

---

🏆 FINAL RESULT

If all steps are implemented:

👉 System Quality: 9 – 9.5 / 10
👉 Placement Level: Top-tier (15+ LPA ready)
👉 Interview Impact: High (clear system design + robustness)

---

🔥 OPTIONAL NEXT STEP

- Convert this into:
  - LangChain pipeline
  - FastAPI backend
  - Streamlit / React frontend

---

END OF INSTRUCTION FILE
