# PERSONALIZED GROUNDING RAG SYSTEM — MVP EXPERIMENT CONTEXT
### For: AI Agent Reviewing and Refactoring PoC Code
*Read this entire document before touching any code.*

---

## Purpose of This Document

You are an AI agent reviewing an existing PoC codebase. This document is your
authoritative reference for:

1. **What this experiment is** — the hypothesis, the architecture, the constraints
2. **What the code must prove** — five explicit success criteria
3. **How every component must behave** — models, DB schema, retrieval pipeline, MCP tools
4. **What is explicitly forbidden** — constraints that are non-negotiable
5. **What good looks like** — the experiment ladder the code must be able to run

Your job is to read the existing code, identify gaps between what is implemented
and what is described here, then fix or refactor the code until it satisfies the
experiment requirements and success criteria. Do not add features not described
here. Do not change the models. Do not simplify the retrieval pipeline below the
minimum described. The experiment is the deliverable — the code exists to prove it.

---

## Hard Constraints — Non-Negotiable

Any code that violates these must be fixed.

| Constraint | Enforcement |
|---|---|
| **No Full-Text Search of any kind** | No `tsvector`, no `LIKE`, no `ILIKE`, no `FULLTEXT`, no BM25, no FTS5, no keyword index on email subject or body. Data classification forbids it. Any such code must be removed. |
| **No plaintext data on disk** | OCP PVC uses an encrypted storage class. No intermediate files containing email text written to unencrypted paths. Embedding generation happens in memory only. |
| **RLS enforced at the DB layer** | Postgres Row-Level Security on every user-data table. User isolation is not enforced in application code — it is enforced in the database. Application code sets the session variable; the DB enforces the policy. |
| **All LLM calls go to Ollama** | No calls to OpenAI, Anthropic API, Cohere, or any external LLM API. Ollama runs locally inside the cluster. Every LLM call — enrichment, tag extraction, contextual prefix, report generation — hits the Ollama internal service endpoint. |
| **Ollama model is `llama3.1`** | Model name in all Ollama API calls must be `llama3.1`. |
| **Emails are multilingual** | French, Spanish, English, and others are present. The embedding model must support multilingual content. English-only models are not acceptable. |
| **Embedding model is environment-dependent** | See the Model Selection section below. The correct model depends on whether a GPU node is available to the RAG embedding pod. The vector column dimension in Postgres must match the active model exactly. A mismatch silently corrupts retrieval. |

---

## ⚠️ Embedding Model Selection — Read Before Touching Schema or Embedding Code

GPU availability for the RAG app pod is **not confirmed**. The codebase must
support both deployment paths. The active path is controlled by a single
environment variable.

```
EMBEDDING_PROFILE=gpu   →  intfloat/multilingual-e5-large  (1024-dim)
EMBEDDING_PROFILE=cpu   →  intfloat/multilingual-e5-base   (768-dim)
```

### Why Two Models, Not One

| Property | `multilingual-e5-large` (GPU) | `multilingual-e5-base` (CPU) |
|---|---|---|
| **Dimensions** | **1024** | **768** |
| **Model size** | ~560 MB | ~278 MB |
| **RAM at runtime** | ~2.5–4 GB | ~1.2–2 GB |
| **CPU inference / query** | 80–200 ms — too slow for prod | 20–60 ms — acceptable |
| **GPU inference / query** | 5–15 ms — fast | N/A |
| **Ingestion batch (CPU, 1000 emails)** | 10–30 min — operationally painful | 3–8 min — acceptable |
| **Multilingual quality** | Highest | ~3–5% below large |
| **MTEB retrieval rank** | Top tier | Strong — within acceptable range |
| **pod memory at 4–8 GB limit** | Fits with GPU pod | Fits comfortably on CPU pod |

Both models use the same `query: ` / `passage: ` instruction prefix behavior.
Zero code changes between profiles except the model name and the vector dimension.

### The Vector Dimension Is Schema-Bound

**This is the critical implication.** The Postgres `vector(N)` column dimension
must match the active model. You cannot mix them.

| EMBEDDING_PROFILE | vector column | IVFFlat index |
|---|---|---|
| `gpu` | `vector(1024)` | `lists = 100` |
| `cpu` | `vector(768)` | `lists = 100` |

If the existing schema has the wrong dimension, it must be migrated before any
embedding code runs. Check the current schema first. If `EMBEDDING_PROFILE` is
not set, default to `cpu` (safer assumption for on-prem OCP without confirmed GPU).

### Implementation Pattern

```python
import os
from sentence_transformers import SentenceTransformer

EMBEDDING_PROFILE = os.getenv("EMBEDDING_PROFILE", "cpu")  # default: cpu

EMBEDDING_MODELS = {
    "gpu": {
        "model_name": "intfloat/multilingual-e5-large",
        "dimensions": 1024,
    },
    "cpu": {
        "model_name": "intfloat/multilingual-e5-base",
        "dimensions": 768,
    },
}

profile = EMBEDDING_MODELS[EMBEDDING_PROFILE]
EMBEDDING_MODEL_NAME = profile["model_name"]
EMBEDDING_DIMENSIONS  = profile["dimensions"]

embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

def embed_query(text: str) -> list[float]:
    """Embed a user query. Must use 'query: ' prefix for e5 models."""
    return embedding_model.encode(
        f"query: {text}",
        normalize_embeddings=True
    ).tolist()

def embed_document(text: str) -> list[float]:
    """Embed a document chunk. Must use 'passage: ' prefix for e5 models."""
    return embedding_model.encode(
        f"passage: {text}",
        normalize_embeddings=True
    ).tolist()
```

### OCP Pod Scheduling — GPU Path

If `EMBEDDING_PROFILE=gpu`, the embedding service pod **must** be scheduled
on a GPU node. Without this, it silently falls back to CPU and you get the
slow performance the GPU profile was chosen to avoid.

```yaml
# Embedding service Deployment — GPU path only
spec:
  template:
    spec:
      nodeSelector:
        nvidia.com/gpu: "true"          # adjust label to match your cluster
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      containers:
        - name: embedding-service
          resources:
            limits:
              nvidia.com/gpu: "1"
              memory: "6Gi"
            requests:
              nvidia.com/gpu: "1"
              memory: "4Gi"
```

For `EMBEDDING_PROFILE=cpu`, remove `nodeSelector`, `tolerations`, and GPU
resource limits. Set memory `requests: 2Gi` / `limits: 4Gi`.

The RAG API, MCP Server, and Ingestion pods do **not** need GPU nodes regardless
of the embedding profile — they call the embedding service, they do not run the
model themselves.

---

## The Experiment — What the Code Must Prove

> **HYPOTHESIS:** An LLM Gateway running on Ollama (llama3.1) can enrich a raw
> user query, route it to an RLS-scoped RAG layer over ingested multilingual emails
> stored in Postgres (no FTS, encrypted OCP PVC, RWX), retrieve the most relevant
> records via semantic search using `intfloat/multilingual-e5-large` or
> `intfloat/multilingual-e5-base` (profile-dependent) and structured metadata
> filters, and return a structured executive-level report — accessible via both
> an MCP tool interface and a REST API — with zero external API calls at any stage.

### Five Success Criteria

The experiment is proven when all five pass:

```
SC-1  "What's the status of Konek ID?"
      → full_rag tool returns Kevin Sivaperumal's September 2025 email in top-3
        retrieved chunks, with correct sender and date attribution.

SC-2  Executive report generated from SC-1 retrieval matches the fixed template
      exactly: Executive Summary, Key Findings, Source Emails table, Status
      Timeline, Open Items, Retrieval Note. Generated by llama3.1 via Ollama.

SC-3  MCP tool report_generation called from an MCP client (Cursor or Claude Code)
      returns the same report as the REST API endpoint for the same query.

SC-4  User A cannot retrieve User B's emails under any query, tool, or API call.
      Verifiable: seed two users, run cross-user queries, confirm zero results
      from the other user's corpus in all cases.

SC-5  No external API call is made at any point during retrieval or generation.
      All embedding and LLM calls route to internal OCP services only.
      Verifiable via network trace, mock, or log inspection.
```

---

## System Architecture — MVP

```
┌─────────────────────────────────────────────────────────────────────┐
│                           OCP Cluster                               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     Postgres Instance                         │   │
│  │        (StatefulSet — OCP PVC RWX, encrypted class)           │   │
│  │                                                               │   │
│  │   ┌──────────────────────────┐  ┌─────────────────────────┐  │   │
│  │   │     Metadata Tables       │  │    pgvector Tables       │  │   │
│  │   │   emails                  │  │   email_embeddings       │  │   │
│  │   │   email_chunks            │  │    - chunk_id            │  │   │
│  │   │   (RLS on user_id)        │  │    - user_id  (RLS)      │  │   │
│  │   │                          │  │    - vector(1024|768) ←  │  │   │
│  │   └──────────────────────────┘  │      profile-dependent   │  │   │
│  │                                 └─────────────────────────┘  │   │
│  │           ↑  Dual write — single Postgres transaction  ↑      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│  │  RAG API    │  │  Ingestion Svc   │  │  MCP Server          │   │
│  │  (FastAPI)  │  │  (OCP CronJob /  │  │  (stdio + HTTP/SSE)  │   │
│  │             │  │  triggered Job)  │  │                      │   │
│  └──────┬──────┘  └───────┬──────────┘  └──────────┬───────────┘   │
│         │                 │                         │               │
│         └─────────────────┴─────────────────────────┘               │
│                           │                                         │
│            ┌──────────────┴──────────────┐                          │
│            │                             │                          │
│   ┌────────▼────────┐        ┌───────────▼────────────────────┐     │
│   │  Ollama         │        │  Embedding Service              │     │
│   │  llama3.1       │        │  sentence-transformers          │     │
│   │                 │        │                                 │     │
│   │  ALL LLM calls: │        │  GPU path: multilingual-e5-large│     │
│   │  - enrichment   │        │            vector(1024)         │     │
│   │  - tag extract  │        │                                 │     │
│   │  - prefix gen   │        │  CPU path: multilingual-e5-base │     │
│   │  - report gen   │        │            vector(768)          │     │
│   └─────────────────┘        └─────────────────────────────────┘     │
│                                                                     │
│   ── Nothing exits the cluster. Zero external API calls. ──         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Models — Exact Specifications

### LLM: Ollama `llama3.1`

```python
import os
import httpx

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama-service:11434")

async def ollama_chat(messages: list[dict], temperature: float = 0.1) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": "llama3.1",
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 1024
                }
            },
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

async def ollama_generate(prompt: str, system: str = "",
                          temperature: float = 0.1) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": "llama3.1",
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 2048
                }
            },
            timeout=90.0
        )
        response.raise_for_status()
        return response.json()["response"]
```

**Temperature settings by use case:**

| Use Case | Call Style | Temperature |
|---|---|---|
| Tag extraction (ingestion) | chat, JSON output | 0.0 |
| Contextual prefix generation (ingestion) | chat, structured prose | 0.1 |
| Query enrichment (Gateway) | chat, JSON output | 0.1 |
| HyDE document generation | generate | 0.2 |
| Executive report generation | generate, fixed template | 0.2 |

### Embedding: Profile-Dependent (see Model Selection section above)

```python
# CRITICAL: intfloat/e5 models require instruction prefixes.
# Omitting them silently degrades retrieval quality — no error is thrown.

def embed_query(text: str) -> list[float]:
    # "query: " prefix required for all query-time embeddings
    return embedding_model.encode(
        f"query: {text}",
        normalize_embeddings=True   # required for pgvector cosine (<=>)
    ).tolist()

def embed_document(text: str) -> list[float]:
    # "passage: " prefix required for all document/chunk embeddings
    return embedding_model.encode(
        f"passage: {text}",
        normalize_embeddings=True
    ).tolist()
```

**Check every `model.encode()` call in the codebase.** If the `query: ` or
`passage: ` prefix is missing, add it. This is the most common mistake with
this model family.

---

## Database Schema — Authoritative

Any schema in the existing code that differs from this must be migrated.
The vector dimension is determined by `EMBEDDING_PROFILE` — check the env
var before deciding which dimension to use.

```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────
-- emails — metadata table
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS emails (
    message_id          TEXT PRIMARY KEY,
    thread_id           TEXT,
    user_id             TEXT NOT NULL,        -- RLS enforcement key

    -- Stored for display and structured filtering ONLY.
    -- NEVER used as a full-text search target.
    from_email          TEXT NOT NULL,
    from_name           TEXT,
    to_emails           JSONB,
    cc_emails           JSONB,
    sent_at             TIMESTAMPTZ NOT NULL,
    subject             TEXT,                 -- display/attribution only, no FTS

    -- Extracted structured tags — populated by llama3.1 at ingestion.
    -- These columns replace BM25 keyword matching. Must be indexed.
    project_names       JSONB,                -- ["Konek ID"]
    person_mentions     JSONB,                -- ["Kevin Sivaperumal"]
    cycle_references    JSONB,                -- ["Cycle 2", "Preauth"]
    status_keywords     JSONB,                -- ["completed", "in progress"]
    email_type          TEXT,                 -- status_report | meeting_invite |
                                              --   action_item | fyi | other
    urgency             TEXT,                 -- high | medium | low

    -- Stored for debug and re-ingestion only. Never queried for text search.
    llm_context_prefix  TEXT,

    ingested_at         TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────
-- email_chunks
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_chunks (
    chunk_id            TEXT PRIMARY KEY,
    message_id          TEXT NOT NULL REFERENCES emails(message_id) ON DELETE CASCADE,
    user_id             TEXT NOT NULL,
    chunk_index         INTEGER NOT NULL,
    chunk_text          TEXT NOT NULL,        -- stored for display, NOT FTS indexed
    token_count         INTEGER,
    UNIQUE (message_id, chunk_index)
);

-- ─────────────────────────────────────────────────────────
-- email_embeddings — vector store (dual-copy with metadata)
--
-- DIMENSION IS PROFILE-DEPENDENT:
--   EMBEDDING_PROFILE=gpu  →  vector(1024)   multilingual-e5-large
--   EMBEDDING_PROFILE=cpu  →  vector(768)    multilingual-e5-base
--
-- The application must read EMBEDDING_PROFILE and create/migrate
-- this table with the correct dimension before any ingestion runs.
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_embeddings (
    chunk_id            TEXT PRIMARY KEY
                            REFERENCES email_chunks(chunk_id) ON DELETE CASCADE,
    user_id             TEXT NOT NULL,
    embedding           vector(1024)          -- GPU path default
                                              -- change to vector(768) for CPU path
);

-- Vector index
CREATE INDEX IF NOT EXISTS idx_embeddings_vector
    ON email_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Structured filter indexes — these replace BM25, they must exist
CREATE INDEX IF NOT EXISTS idx_emails_user_sent
    ON emails (user_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_emails_project_names
    ON emails USING gin (project_names);
CREATE INDEX IF NOT EXISTS idx_emails_person_mentions
    ON emails USING gin (person_mentions);
CREATE INDEX IF NOT EXISTS idx_emails_type
    ON emails (user_id, email_type);
CREATE INDEX IF NOT EXISTS idx_chunks_message
    ON email_chunks (message_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_user
    ON email_embeddings (user_id);

-- ─────────────────────────────────────────────────────────
-- Row-Level Security — applied to ALL user-data tables
-- ─────────────────────────────────────────────────────────
ALTER TABLE emails           ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_chunks     ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_isolation_emails ON emails
    USING (user_id = current_setting('app.current_user_id')::text);
CREATE POLICY user_isolation_chunks ON email_chunks
    USING (user_id = current_setting('app.current_user_id')::text);
CREATE POLICY user_isolation_embeddings ON email_embeddings
    USING (user_id = current_setting('app.current_user_id')::text);

-- The application MUST execute this before any query in a request:
--   SET LOCAL app.current_user_id = '{authenticated_user_id}';
-- Failure to set this causes the policy to throw an error — intentional.
```

---

## Ingestion Pipeline — Required Behavior

Every step must be present for every email. If the existing code skips any step, add it.

### Step 1: Tag Extraction (llama3.1 → Ollama, temperature 0.0)

```python
TAG_EXTRACTION_SYSTEM = (
    "You are extracting structured metadata from an email. "
    "Return ONLY a valid JSON object. No explanation. No markdown. No extra text."
)

TAG_EXTRACTION_PROMPT = """
Extract from the email below. Return exactly this JSON structure:
{{
  "project_names":    [],
  "person_mentions":  [],
  "cycle_references": [],
  "status_keywords":  [],
  "email_type":       "",
  "urgency":          ""
}}

Rules:
- project_names:    exact project names as they appear in the text
- person_mentions:  full names only, no email addresses
- cycle_references: testing cycles, sprint numbers, version strings
- status_keywords:  completed | blocked | in progress | pending | escalated | etc.
- email_type:       one of: status_report | meeting_invite | action_item | fyi | other
- urgency:          one of: high | medium | low

Email:
{email_text}
"""
```

### Step 2: Contextual Prefix Generation (llama3.1 → Ollama, temperature 0.1)

The prefix is prepended to the chunk text **before** embedding. This is the
most critical ingestion step for retrieval quality under the no-FTS constraint.
It encodes what BM25 would have caught lexically into the embedding vector.

```python
CONTEXT_PREFIX_TEMPLATE = (
    "[PROJECT: {project_names}] "
    "[FROM: {from_name}] "
    "[DATE: {sent_at}] "
    "[TYPE: {email_type}] "
    "[STATUS: {status_keywords}] "
    "[CYCLE: {cycle_references}] "
    "[DIST: {recipient_count} recipients]\n"
    "Summary: {llm_one_sentence_summary}\n"
    "---\n"
    "{chunk_text}"
)
```

The `llm_one_sentence_summary` is a separate Ollama call asking llama3.1 to
summarize the email in one sentence. The full prefix is stored in
`llm_context_prefix` for debugging and re-ingestion.

### Step 3: Chunking

```
CHUNK_SIZE_TOKENS   = 512
CHUNK_OVERLAP_TOKENS = 64
```

Split order: section headers first (structured emails) → message boundaries
(threads) → token count with overlap. Approximate: 1 token ≈ 4 characters if
a tokenizer is unavailable.

### Step 4: Embedding

```python
# Input = contextual_prefix + chunk_text (already concatenated in prefix template)
# MUST use "passage: " prefix — this is a document, not a query

full_text  = f"passage: {context_prefix}"   # prefix already contains chunk_text
embedding  = embed_document(full_text)       # normalize_embeddings=True inside
# → list of floats, length = EMBEDDING_DIMENSIONS (1024 or 768)
```

### Step 5: Atomic Write

```python
async with db.transaction():
    await db.execute(INSERT_EMAIL_SQL, email_metadata)
    for chunk in chunks:
        await db.execute(INSERT_CHUNK_SQL, chunk_data)
        await db.execute(INSERT_EMBEDDING_SQL,
                         chunk.chunk_id, user_id, chunk.embedding)
# If any step fails, the whole transaction rolls back.
# No partial ingestion state ever.
```

---

## Query Enrichment — LLM Gateway

Every `search` and `full_rag` call passes through enrichment first.
The enrichment call goes to **Ollama llama3.1**, temperature 0.1.

```python
ENRICHMENT_SYSTEM = (
    "You are a query enrichment assistant for a multilingual email search system. "
    "Emails may be in English, French, Spanish, or other languages. "
    "Return ONLY a valid JSON object. No explanation. No markdown."
)

ENRICHMENT_PROMPT = """
Enrich this user query for semantic email retrieval.

User query: "{raw_query}"

Return:
{{
  "rewritten_query": "...",
  "semantic_variants": ["...", "...", "...", "..."],
  "metadata_filters": {{
    "project_names":    [],
    "date_range":       {{"from": null, "to": null}},
    "email_type":       [],
    "person_mentions":  []
  }},
  "query_type": "status | search | summary",
  "hyde_prompt": "Write an email that would perfectly answer: {raw_query}"
}}

Rules:
- semantic_variants: exactly 4 alternative phrasings, may include French/Spanish
  equivalents if the query implies multilingual content
- metadata_filters: only populate fields explicitly mentioned or strongly implied
- hyde_prompt: a prompt to generate the ideal email answering this query
- query_type: status = project status questions | search = general lookup |
              summary = synthesis across emails
"""
```

After enrichment, generate the HyDE embedding:

```python
hyde_text      = await ollama_generate(enrichment.hyde_prompt, temperature=0.2)
hyde_embedding = embed_document(f"passage: {hyde_text}")
# Note: passage: prefix — HyDE text is treated as a document
```

---

## Retrieval Pipeline — `full_rag`

Every step must be present. If any step is missing, add it.

```python
async def full_rag(raw_query: str, user_id: str) -> RagResult:

    # Step 1 — Enrichment
    enrichment     = await enrich_query(raw_query)           # llama3.1 via Ollama
    hyde_embedding = await generate_hyde_embedding(enrichment.hyde_prompt)

    # Step 2 — Metadata pre-filter
    # Structured WHERE clauses only — no text search of any kind
    candidate_ids = await metadata_prefilter(
        user_id=user_id,
        filters=enrichment.metadata_filters
    )
    # candidate_ids scopes ALL subsequent vector searches to this user's
    # filtered subset. If no filters apply, candidate_ids = all user's chunks.

    # Step 3 — Multi-variant semantic search
    all_query_texts = [enrichment.rewritten_query] + enrichment.semantic_variants
    all_embeddings  = [embed_query(q) for q in all_query_texts]
    all_embeddings.append(hyde_embedding)   # HyDE is a passage embedding

    result_sets = []
    for emb in all_embeddings:
        results = await vector_search(
            embedding=emb,
            user_id=user_id,
            candidate_ids=candidate_ids,
            top_k=20
        )
        result_sets.append(results)

    # Step 4 — RRF fusion across all variant result sets
    fused = reciprocal_rank_fusion(result_sets, k=60)   # → top-50

    # Step 5 — Reranking (local cross-encoder)
    reranked = reranker.rerank(
        query=raw_query,
        documents=[r.chunk_text for r in fused[:50]]
    )                                                   # → top-5

    # Step 6 — Report generation
    report = await generate_report(
        query=raw_query,
        chunks=reranked[:5],
        enrichment=enrichment
    )                                                   # llama3.1 via Ollama

    return RagResult(report=report, sources=reranked[:5])
```

### Vector Search SQL

```sql
-- SET LOCAL app.current_user_id already executed before this query
SELECT
    ec.chunk_id,
    ec.chunk_text,
    e.from_name,
    e.from_email,
    e.sent_at,
    e.subject,
    e.email_type,
    ee.embedding <=> $1::vector AS distance
FROM email_embeddings ee
JOIN email_chunks ec ON ee.chunk_id  = ec.chunk_id
JOIN emails       e  ON ec.message_id = e.message_id
WHERE ee.chunk_id = ANY($2::text[])    -- $2 = pre-filtered candidate_ids
ORDER BY distance
LIMIT 20;
```

### RRF Implementation

```python
def reciprocal_rank_fusion(
    result_sets: list[list[SearchResult]],
    k: int = 60
) -> list[SearchResult]:
    scores: dict[str, float]        = {}
    docs:   dict[str, SearchResult] = {}

    for result_set in result_sets:
        for rank, result in enumerate(result_set):
            scores[result.chunk_id] = (
                scores.get(result.chunk_id, 0.0) + 1.0 / (k + rank + 1)
            )
            docs[result.chunk_id] = result

    ranked = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [docs[cid] for cid in ranked[:50]]
```

---

## Reranker — Local Only

```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, documents: list[str], top_k: int = 5) -> list[str]:
    pairs  = [(query, doc) for doc in documents]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in ranked[:top_k]]
```

**No Cohere. No external reranker API. Local cross-encoder only.**

---

## The Four MCP Tools

### `email_query`

```python
@mcp.tool(
    name="email_query",
    description="""Use when you know specific structured attributes: sender name
    or email, date range, project name, or email type. Fast metadata-only lookup
    (<30ms). Does NOT search email text or subject. No LLM involved.
    Example: 'All status reports from Kevin about Konek ID in September 2025'"""
)
async def email_query(
    project_names:    list[str] | None = None,
    from_email:       str        | None = None,
    email_type:       str        | None = None,
    date_from:        str        | None = None,
    date_to:          str        | None = None,
    person_mentions:  list[str]  | None = None,
    limit:            int               = 10
) -> list[EmailRecord]: ...
```

### `search`

```python
@mcp.tool(
    name="search",
    description="""Use for natural language questions about email content when
    you don't know the specific sender or date. Finds emails with similar meaning
    even with different words. Supports multilingual queries.
    Example: 'emails discussing testing delays or stakeholder concerns'"""
)
async def search(query: str, top_k: int = 10) -> list[ChunkResult]: ...
```

### `full_rag`

```python
@mcp.tool(
    name="full_rag",
    description="""Use for complex questions requiring synthesis across multiple
    emails, or when search returns poor results. Highest accuracy, slower (2-5s).
    Runs enrichment, multi-variant semantic search, RRF fusion, and reranking.
    Example: 'What is the overall status of the Konek ID project?'"""
)
async def full_rag_tool(query: str) -> RagResult: ...
```

### `report_generation`

```python
@mcp.tool(
    name="report_generation",
    description="""Use when the user explicitly wants an executive report or
    structured status briefing. Fixed-format output: executive summary, key
    findings, source attribution, and timeline.
    Example: 'Generate a status report on Konek ID for executive review'"""
)
async def report_generation(query: str) -> ExecutiveReport: ...
```

---

## Executive Report Template — Fixed

Enforce this structure in the LLM system prompt. The model must not deviate.

```
SYSTEM PROMPT (verbatim):
You are an executive communications assistant. Generate a status report using
ONLY the provided email context. Use the EXACT template below.
Do not add sections. Do not remove sections. Do not infer beyond what is stated.

## Executive Summary
{2-3 sentences maximum. State what was found and the current status.}

## Key Findings
- {finding — (Source: Name, Date)}
- {finding — (Source: Name, Date)}
- {finding — (Source: Name, Date)}

## Source Emails
| Sender | Date | Type | Key Point |
|--------|------|------|-----------|
| {name} | {YYYY-MM-DD} | {type} | {one sentence} |

## Status Timeline
{Chronological progression from retrieved emails. Omit section if only one email.}

## Open Items
{Action items or open questions found explicitly in the emails.
Write 'None identified.' if none are present. Do not infer.}

## Retrieval Note
Retrieved: {N} emails | Top match: {sender}, {date} | Query: {rewritten_query}
```

---

## OCP Infrastructure

```yaml
# Postgres StatefulSet — key fields
spec:
  volumeClaimTemplates:
    - metadata:
        name: postgres-data
      spec:
        accessModes: ["ReadWriteMany"]             # RWX confirmed
        storageClassName: <encrypted-class-name>   # confirm with platform team
        resources:
          requests:
            storage: 50Gi

# All pods — secrets from OCP Secret, never hardcoded
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef: { name: rag-db-secret, key: database_url }
  - name: OLLAMA_BASE_URL
    value: "http://ollama-service:11434"    # internal cluster service
  - name: EMBEDDING_PROFILE
    value: "gpu"                            # or "cpu" — set per environment
```

**Confirm with platform team before starting:**

| Item | Why It Blocks |
|---|---|
| Encrypted storage class name | PVC cannot be created without it |
| `EMBEDDING_PROFILE` for this cluster | Determines vector dimension — must be set before first ingestion |
| GPU node label and taint (if `EMBEDDING_PROFILE=gpu`) | Embedding pod must land on GPU node or performance degrades silently |
| Postgres 15+ with pgvector in approved image list | Bitnami Postgres 15+ includes pgvector — verify approval |
| Ollama internal service URL and reachability | Every LLM call routes here |
| Network policy for Ollama pod | RAG API, Ingestion, MCP Server must reach Ollama service port |

---

## Code Review Checklist

```
Schema
[ ] vector column dimension matches EMBEDDING_PROFILE
    gpu → vector(1024)  |  cpu → vector(768)
[ ] RLS enabled and user_isolation policy on emails, email_chunks, email_embeddings
[ ] GIN indexes on project_names and person_mentions
[ ] No FTS index anywhere (no tsvector, no GIN on text columns for search)
[ ] No LIKE or ILIKE on subject, chunk_text, or any email content column

Embedding
[ ] EMBEDDING_PROFILE env var read at startup
[ ] Correct model loaded: e5-large (gpu) or e5-base (cpu)
[ ] All query embeddings use "query: " prefix
[ ] All document/chunk embeddings use "passage: " prefix
[ ] normalize_embeddings=True on every encode() call
[ ] embed_query() and embed_document() are separate functions, not one

LLM Calls
[ ] Every LLM call points to OLLAMA_BASE_URL — zero calls to external APIs
[ ] Model name is "llama3.1" in every Ollama request body
[ ] temperature 0.0 for tag extraction
[ ] temperature 0.1 for query enrichment and prefix generation
[ ] temperature 0.2 for HyDE and report generation

Ingestion
[ ] Tag extraction runs for every email before storage
[ ] Contextual prefix generated and stored in llm_context_prefix
[ ] "passage: " prefix prepended to chunk text before embedding
[ ] Single transaction: emails + email_chunks + email_embeddings together
[ ] message_id deduplication enforced

Retrieval — full_rag
[ ] Enrichment runs first — raw query never hits vector search directly
[ ] HyDE embedding generated and included in multi-variant set
[ ] Metadata pre-filter runs before vector search, not after
[ ] RRF applied across ALL variant result sets (not just top-1)
[ ] Reranker runs on top-50 RRF results, returns top-5 to LLM
[ ] SET LOCAL app.current_user_id set before every DB query per request

MCP
[ ] Four tools registered with discriminating descriptions
[ ] stdio transport working for IDE
[ ] HTTP/SSE transport available for remote

Report
[ ] Fixed template enforced in system prompt verbatim
[ ] All six template sections present in every report
[ ] Attribution includes sender name and date on every finding

Security
[ ] user_id sourced from validated auth token only — never from request body
[ ] No raw email content, subject, or chunk text in logs
[ ] No credentials hardcoded — all from OCP Secrets via env vars
```

---

## Experiment Ladder — Run In Order

### Experiment 1: Ingestion Quality (~1.5 hrs)
- Ingest 10-20 sample emails (short, long status report, thread, forwarded, at
  least 2 in French or Spanish)
- Verify: tag extraction accurate for `project_names`, `email_type`, `person_mentions`
- Verify: `llm_context_prefix` stored and readable
- Verify: vector dimension in DB matches `EMBEDDING_PROFILE`
- Verify: single transaction — kill midway and confirm no partial rows
- Measure: time per email and Ollama call count

### Experiment 2: Retrieval Ladder — Core Evidence (~2 hrs)
Same 5 test queries through each mode. Record top-3 results per mode.

```
Mode 1: email_query          — metadata filter only, no embeddings
Mode 2: search, no prefix    — semantic only, chunks ingested without context prefix
Mode 3: search, with prefix  — semantic only, chunks ingested WITH context prefix
Mode 4: multi-variant + RRF  — enrichment + 5 variants + HyDE + RRF, no reranker
Mode 5: full_rag             — Mode 4 + reranker
```

Mode 5 must outperform Mode 2 on "What's the status of Konek ID?" — this is the
core evidence. If it does not, the pipeline has a bug.

### Experiment 3: Enrichment Value (~1 hr)
- "What's the status of Konek ID?" raw → vector search → record results
- Same query enriched → vector search → record results
- Does enrichment surface different (better) emails? Measure latency overhead.

### Experiment 4: MCP Discrimination + RLS (~1.5 hrs)
- Connect MCP server (stdio) to Cursor or Claude Code
- Run 10 queries — verify correct tool selected each time
- Seed two users with non-overlapping emails
- Verify SC-4: user A queries return zero results from user B corpus

### Experiment 5: Report Quality + SC Verification (~1 hr)
- Run SC-1 query → verify Kevin Sivaperumal email in top-3
- Verify SC-2 report template structure matches exactly
- Verify SC-3 MCP and REST return same report
- Verify SC-5 no external API calls — check logs or mock the network

---

## Tech Stack Summary

| Component | GPU Path | CPU Path |
|---|---|---|
| **Embedding model** | `intfloat/multilingual-e5-large` | `intfloat/multilingual-e5-base` |
| **Vector dimensions** | 1024 | 768 |
| **Pod scheduling** | GPU node (nodeSelector + toleration) | Any node |
| **Pod memory (embedding)** | requests 4Gi / limits 6Gi | requests 2Gi / limits 4Gi |
| **LLM** | `llama3.1` via Ollama | `llama3.1` via Ollama |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` (local) | same |
| **API Framework** | FastAPI (Python 3.11+, Pydantic v2) | same |
| **MCP SDK** | `mcp` Python SDK — stdio + HTTP/SSE | same |
| **Database** | Postgres 15+ with pgvector extension | same |
| **Encryption** | OCP PVC encrypted storage class | same |
| **Access Control** | Postgres RLS on `user_id` | same |
| **PVC Access Mode** | ReadWriteMany (RWX) | same |
| **Full-Text Search** | ❌ Forbidden | ❌ Forbidden |
| **External LLM API** | ❌ Forbidden | ❌ Forbidden |
| **External Embedding API** | ❌ Forbidden | ❌ Forbidden |
| **External Reranker API** | ❌ Forbidden | ❌ Forbidden |

---

*This document is the experiment specification. The code must prove the hypothesis.
When all five success criteria pass, the experiment is complete.*
