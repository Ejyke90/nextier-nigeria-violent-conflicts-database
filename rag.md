#RAG Methods and Strategies for Best Results
###  Personal Grounding Assistant

---

| Field | Value |
|---|---|
| **Document ID** | ADR-003 |
| **Status** | Proposed |
| **Created By** | AI Platform Team |
| **Last Updated** | March 2026 |
| **Version** | 2.0 (Revised) |
| **Proposed Date** | March 2, 2026 |

> **CLASSIFICATION: RESTRICTED — Level 3 Internal. Not for distribution outside the  AI Platform team.**

---

## Table of Contents

1. [Glossary](#1-glossary)
2. [Context](#2-context)
3. [Challenge](#3-challenge)
4. [Decision Drivers](#4-decision-drivers)
5. [Options Considered](#5-options-considered)
   - Option 1: Simple RAG with Pure Vector Search
   - Option 2: Hybrid RAG with SPLADE (No FTS)
   - Option 3: Advanced RAG with Query Enrichment and Cross-Encoder *(Recommended)*
   - Option 4: Hybrid RAG with EWS Native Search *(Rejected)*
   - Option 5: Metadata-Only FTS *(Merged into Option 3)*
6. [Alternatives Considered and Rejected](#6-alternatives-considered-and-rejected)
7. [Options Comparison Matrix](#7-options-comparison-matrix)
8. [Decision](#8-decision)
9. [Target Architecture](#9-target-architecture)
10. [Consequences](#10-consequences)
11. [Risks and Mitigations](#11-risks-and-mitigations)
12. [Implementation Phases](#12-implementation-phases)
13. [Revision History](#13-revision-history)

---

## 1. Glossary

### Core Technologies

| Term | Definition |
|---|---|
| **FTS** | Full-Text Search — Database-native keyword search indexing (PostgreSQL tsvector, SQLite FTS5) |
| **RAG** | Retrieval-Augmented Generation — AI pattern combining document retrieval with LLM generation |
| **RRF** | Reciprocal Rank Fusion — Algorithm for combining multiple search result rankings |
| **MCP** | Model Context Protocol — Interface protocol for AI assistant integration |
| **EWS** | Exchange Web Services — Microsoft API for real-time email access from Exchange Server |
| **NER** | Named Entity Recognition — ML technique for identifying and classifying entities in text |
| **JIT** | Just-In-Time Hydration — Pattern for fetching raw text on-demand into memory only, never persisted |
| **ANN** | Approximate Nearest Neighbour — Fast vector similarity search algorithm |

### Embedding Types

| Term | Definition |
|---|---|
| **Dense Vectors** | Traditional semantic embeddings (768-dimensional continuous values) |
| **Sparse Vectors** | Learned keyword embeddings with mostly zero values (1,000–30,522 dimensions) |
| **SPLADE** | Sparse Lexical and Expansion Model — neural AI model for learned keyword matching |
| **Cross-Encoder** | Neural reranking model that jointly scores a (query, document) pair with full attention |
| **ColBERT** | Late-interaction model storing per-token vectors — a middle path between bi-encoders and cross-encoders |

### Search Enhancement Methods

| Term | Definition |
|---|---|
| **HyDE** | Hypothetical Document Embeddings — generates a hypothetical answer document to improve retrieval |
| **Semantic Variants** | Multiple reformulations of the query for better coverage |
| **Query Enrichment/Expansion** | LLM-based query rewriting and variant generation |
| **Cross-Encoder** | Neural reranking model that scores query–document pairs for precision |
| **BM25** | Best Match 25 — probabilistic ranking function for keyword relevance |

---

## 2. Context

The Personal Grounding Service revolutionizes how  assists users to interact with their entire digital work ecosystem, starting with emails for now. By seamlessly integrating with 's Exchange environment, it delivers sophisticated assistance via email communications transforming intelligence. Leveraging advanced RAG (Retrieval-Augmented Generation) capabilities, it delivers sophisticated semantic search, pattern recognition, and predictive analysis. While automated report generation synthesizes complex information into actionable business insights, the most powerful features are accessible directly through an MCP (Model Context Protocol) interface, enabling 's AI assistant to provide contextual, intelligent assistance that anticipates needs, streamlines decision-making, and elevates productivity across the entire enterprise workflow.

---

## 3. Challenge

Enterprise email search requires both semantic understanding (natural language queries and exact keyword retrieval) and intelligent awareness of context (Message IDs, project names, dates). However, **RESTRICTED emails contain Level 2–4 classified information** (passwords, credentials, vault codes, digital certificates) that must not be stored, processed, or exposed via FTS indexes due to  security requirements.

### Data Classification Hierarchy *(Highest to Lowest Sensitivity)*

| Level | Classification | Examples | FTS / Storage |
|---|---|---|---|
| **L4** | Restricted | Authentication tokens, PINs, vault codes, digital certificates, sensitive credit card data (CVV, track data) | **NO FTS. No persistence of any kind.** |
| **L3** | Sensitive | Personal Health Information (PHI), Material Business Information, confidential documents, voice notes, invoice numbers | **NO FTS. No persistence.** |
| **L2** | Internal | Internal directories, policies, HR programs, internal certificates | **FTS allowed** |
| **L1** | Public | Public websites, bank rates, published results, external publications | **FTS allowed** |

---

## 4. Decision Drivers

### Result Relevance (Accuracy)
Return the correct emails that match user intent for both semantic queries and exact keyword lookups. Target 90%+ accuracy in finding relevant emails.

### Result Quality (Ranking)
Properly rank search results so the most relevant email appears first. Users should not need to scroll past irrelevant results.

### Data Security *(Non-Negotiable)*
Prevent unauthorized storage or processing of classified information (RESTRICTED/SENSITIVE/CONFIDENTIAL).

### Regulatory Compliance
Complete audit trail and logging for observability, security events, and regulatory review (OSFI, FINTRAC, PCI-DSS).

### Response Speed
- Retrieval latency: ensure fast context gathering
- Time to first token: maintain responsive generation
- Total response time: enable rapid task completion and user productivity

### No Email Storage *(Hard Constraint)*
Emails must NOT be stored locally to comply with data privacy requirements. **Only embeddings and metadata may be persisted.** This constraint eliminates traditional FTS approaches that require indexing email body text.

### 4.1 Embedding Inversion Attack Mitigation *(REVISED: March 2026)*

Dense embedding vectors are **not inherently safe**. Research has demonstrated that inversion attacks can reconstruct source text from stored embeddings with measurable accuracy, particularly for short, structured content like email subjects and credentials.

**REQUIRED:** Apply post-hoc Gaussian noise (sigma = 0.01 to 0.05) to all dense embeddings **before** storage. Accept 2–4% recall degradation in exchange for protection against Level 3/4 text reconstruction. This is a mandatory control for all options considered.

### 4.2 User-Level Vector Partitioning *(REVISED: March 2026)*

All SQLite queries **MUST** include `WHERE user_id = :current_user` as a mandatory filter. The embedding sync job must enforce `user_id` tagging at write time. Cross-user embedding access is a **CRITICAL security violation** and must be enforced at the middleware layer, not the application layer.

---

## 5. Options Considered

> **Note on "No Email Storage" constraint:** Given this hard constraint, traditional FTS approaches (Database-native FTS5/tsvector) are eliminated. We must find alternatives that provide keyword-matching capabilities while respecting this requirement.

---

### Option 1: Simple RAG with Pure Vector Search

**Description:** Basic RAG pipeline using semantic search only (DENSE, ONLY retrieval) without keyword matching, query enrichment, or reranking.

**Architecture:** SQLite with sqlite-vec extension (embeddings only, no email storage)

#### RAG Pipeline

```
Document Ingestion:
  Data Ingestor → Classify → Chunk → Embed
  Store: Embeddings + Metadata only (NO email text)
  Apply: Gaussian noise to dense vectors before storage

Query Processing:
  User Query → Query Embed → Vector Search
  Return: Search results with chunk IDs only

JIT Hydration (for generation only):
  Fetch email text via EWS API using chunk IDs → in RAM only
  Pass to LLM → Purge from memory after generation

Generation:
  Search results → Augmented Context → LLM → Response
```

| Pros | Cons |
|---|---|
| Simple implementation | Misses exact keyword matches |
| No email storage (privacy compliant) | Lower accuracy on ID/project queries |
| Good semantic understanding | Poor ranking for keyword-heavy queries |
| No additional model dependencies | Not suitable as primary strategy |

---

### Option 2: Hybrid RAG with SPLADE (No FTS)

**Description:** RAG pipeline using hybrid search (dense + SPLADE sparse vectors) with RRF fusion. NO FTS required. Provides keyword matching without storing email text.

**Architecture:** SQLite with **Relational SPLADE token table** (embeddings only, no email storage)

#### Relational SPLADE Schema *(REVISED: March 2026)*

> ⚠️ **Critical Note:** Native SQLite vector extensions (sqlite-vec) do **not** have a native sparse vector data type optimized for SPLADE-style 30,522-dimensional sparse arrays. Attempting native storage will fail or perform unacceptably. The correct approach is a relational token mapping table:

```sql
-- Dense vector storage
CREATE TABLE embeddings (
  chunk_id       TEXT PRIMARY KEY,
  user_id        TEXT NOT NULL,
  dense_vector   BLOB NOT NULL,        -- 768-dim, Gaussian-noised before storage
  created_at     INTEGER NOT NULL,
  email_metadata JSON NOT NULL         -- subject, sender, date, message_id ONLY. No body text.
);
CREATE INDEX idx_embeddings_user ON embeddings(user_id);

-- Relational SPLADE sparse token storage
CREATE TABLE splade_tokens (
  chunk_id  TEXT    NOT NULL,
  token_id  INTEGER NOT NULL,
  weight    REAL    NOT NULL,
  user_id   TEXT    NOT NULL,
  PRIMARY KEY (chunk_id, token_id)
);
CREATE INDEX idx_token_weight ON splade_tokens(token_id, weight DESC);
CREATE INDEX idx_splade_user  ON splade_tokens(user_id);
```

**Sparse retrieval** is performed via SQL JOIN scoring, not native vector operators:
```sql
SELECT s.chunk_id, SUM(q.weight * s.weight) AS sparse_score
FROM splade_tokens s
JOIN query_tokens q ON s.token_id = q.token_id
WHERE s.user_id = :current_user
GROUP BY s.chunk_id
ORDER BY sparse_score DESC
LIMIT :k;
```

#### RAG Pipeline

```
Document Ingestion:
  Data Ingestor → Classify → Chunk
  Dense Embed (intfloat/multilingual-e5-base, 768-dim)
  Sparse Embed (SPLADE-cocondenser-ensemble-distil, 30,522-dim)
  Apply: Gaussian noise to dense vectors
  Store: Dense vector + Relational SPLADE tokens + Metadata only (NO email text)
  Purge: Raw email text from memory immediately after embedding

Query Processing:
  User Query → Dense Embed + Sparse SPLADE Embed (parallel)
  Parallel Dense Search + Sparse SQL JOIN Search
  RRF Fusion (k=60) → Top candidate chunk IDs

JIT Hydration (for generation only):
  Fetch raw email text via EWS API → in-process RAM only
  Pass to LLM → Purge from memory post-generation

Generation:
  Augmented Context → LLM → Response
```

| Pros | Cons |
|---|---|
| No email storage | Requires SPLADE model (additional dependency) |
| Good keyword matching via sparse vectors | Sparse tokens increase storage requirements vs. Option 1 |
| Maintains semantic understanding | SQL JOIN-based scoring — benchmark required at 50K+ emails |
| No network dependency for search operations | Additional model loading time |

---

### Option 3: Advanced RAG with Query Enrichment and Cross-Encoder *(Recommended)*

**Description:** RAG pipeline with LLM query enrichment, multi-variant search (SPLADE hybrid), cross-encoder reranking, and structured report generation. Highest accuracy for complex queries. **Incorporates elements of Option 5 (Metadata FTS) for structured entity matching.**

**Architecture:** SQLite + Ollama LLM + Cross-Encoder (embeddings only, no email storage)

#### Complete SQLite Schema

```sql
-- Dense embeddings (Gaussian-noised before storage)
CREATE TABLE embeddings (
  chunk_id       TEXT PRIMARY KEY,
  user_id        TEXT NOT NULL,
  dense_vector   BLOB NOT NULL,
  created_at     INTEGER NOT NULL,
  email_metadata JSON NOT NULL    -- subject, sender, date, message_id ONLY
);

-- Relational SPLADE sparse tokens
CREATE TABLE splade_tokens (
  chunk_id  TEXT    NOT NULL,
  token_id  INTEGER NOT NULL,
  weight    REAL    NOT NULL,
  user_id   TEXT    NOT NULL,
  PRIMARY KEY (chunk_id, token_id)
);
CREATE INDEX idx_token_weight ON splade_tokens(token_id, weight DESC);

-- Metadata FTS (merged from Option 5)
CREATE VIRTUAL TABLE metadata_fts USING fts5(
  chunk_id UNINDEXED,
  user_id  UNINDEXED,
  subject,
  sender_email,
  extracted_ids,    -- project codes, ticket numbers, employee IDs
  project_names
);
```

#### RAG Pipeline

```
Document Ingestion:
  Data Ingestor → Classify → Chunk (512-token, 128-token overlap)
  Dense Embed (768-dim) + Sparse SPLADE Embed (30,522-dim)
  Metadata Extraction: subject, sender, project IDs, ticket numbers (NO body text)
  Apply: Gaussian noise to dense vectors before storage
  Store: Dense vector + Relational SPLADE tokens + Metadata FTS only
  Purge: Raw email text from memory immediately after embedding

Query Processing:
  User Query
    → LLM Query Enrichment:
        rewrite(query)                    [1 variant]
      + semantic_variants(query, n=4)     [4 variants]
      + HyDE document generation          [1 synthetic doc]
      → Total: 6 query variants

  Per variant (parallel):
    → Dense Search (sqlite-vec ANN)
    → Sparse Search (SPLADE SQL JOIN)
    → Metadata FTS Search (structured entity matching)
    → RRF Fusion per variant

  Cross-variant RRF Fusion → Top-30 candidate chunk IDs

JIT Hydration & Reranking:  ← ⚠️ CRITICAL STEP (REVISED: March 2026)
  Fetch raw email bodies for Top-30 chunk IDs via EWS/Ingestor API
  ↓ In-process RAM only — never written to disk
  NER Anonymization Pass:
    Mask: credentials, vault codes, PAN, SIN/SSN, named persons (L4)
    Build: token_map {placeholder → original} in RAM
  Cross-Encoder Reranking: score(query_string, anonymized_chunk_string)
    Model: cross-encoder/ms-marco-MiniLM-L-6-v2, batch_size=8
  Select: Top-5 to Top-10 reranked candidates

Generation:
  LLM (Ollama, on-prem) receives anonymized context only
  Output Filter (ResponseScrubber):
    Detect & redact: passwords, vault codes (VAULT-[A-Z0-9]{8}), PAN, SIN
    Log: SECURITY_SCRUB_EVENT (pattern type only, never value)
  De-anonymization by clearance level:
    L1–L2: restore names and dates only
    L3:    restore all except vault codes
    L4:    full restore (authorized users only)
  Purge: all hydrated text, token_map from memory
  Return: Final response to user
```

#### Ephemeral Cache Specification *(REVISED: March 2026)*

The JIT Hydration cache operates as a **TTL-bound, in-process heap store only**:

- **Storage**: In-process dictionary (NOT Redis, NOT SQLite, NOT tmpfs files)
- **TTL**: 5 minutes per entry — enables follow-up query reuse without re-fetching EWS
- **Capacity**: Maximum 50 concurrent entries (LRU eviction)
- **Wipe**: Explicit secure wipe (zero-overwrite) on eviction and session end
- **Kubernetes requirements**: `swappiness=0` on pod, `tmpfs` for any temp mounts, swap disabled
- **Compliance**: In-volatile-memory-only lifecycle satisfies "No Storage" constraint

| Pros | Cons |
|---|---|
| Highest accuracy | Slowest (~90ms base, see benchmarks) |
| Multi-variant query diversity | LLM dependency for query enrichment |
| No email storage | Not suitable for interactive/type-ahead search |
| Cross-encoder precision | Most complex implementation |
| Structured report output | High computational cost |
| Best for complex queries | HyDE limitation: may generate documents missing -specific terminology |

---

### Option 4: Hybrid RAG with EWS Native Search *(Rejected)*

**Description:** RAG pipeline using vector search for initial retrieval, then leveraging Exchange Web Services (EWS) native search for keyword refinement. No local email storage required.

**Architecture:** SQLite for embeddings + EWS API for search (no local email storage)

#### Known Critical Limitation *(REVISED: March 2026)*

> ⚠️ **Granularity Mismatch — RRF Fusion is Mathematically Unsound:**
> Vector Search returns specific **512-token chunk-level** results. EWS Native Search returns entire **email thread-level** results. Standard RRF fusion requires both ranked lists to operate at the same granularity. Fusing chunk-level and thread-level relevance scores produces mathematically inconsistent rankings that often **destroy retrieval quality**. A chunk-to-thread normalization pass is required before fusion, adding 50–150ms latency and significant engineering complexity.

#### RAG Pipeline

```
Document Ingestion:
  Data Ingestor → Classify → Chunk
  Store: Embeddings + Metadata only (no email text)

Query Processing:
  User Query → Dense Embed → Vector Search (initial candidates)
  EWS Native Search (keyword refinement of Exchange server)
  [Normalization pass: chunk-level → thread-level alignment required]
  Result Fusion → Top-K Results

Generation:
  Search results → Augmented Context → LLM → Response
```

| Pros | Cons |
|---|---|
| No email storage | Requires network connectivity to Exchange at query time |
| Keyword matching without local FTS | Limited control over search ranking |
| Email always up-to-date | EWS search quality cannot be controlled |
| No local FTS maintenance | Potential rate limiting from Exchange |
| | **Chunk/thread granularity mismatch degrades RRF quality** |
| | Dependent on EWS API availability |

**Status: REJECTED** — Granularity mismatch makes reliable RRF fusion impractical without significant additional engineering. Dependency on EWS at query time (vs. only at hydration time) creates a harder availability coupling.

---

### Option 5: Metadata-Only FTS *(Merged into Option 3)*

**Description:** RAG pipeline using FTS on metadata fields only (subject, sender, extracted IDs) without indexing email body text. Provides keyword matching on safe metadata while maintaining the no-storage requirement.

**Status: MERGED into Option 3** — The Metadata FTS table (SQLite FTS5) is incorporated directly into Option 3's schema and retrieval pipeline as a third parallel search path (alongside dense and sparse). This provides 100% precision for structured entity matching (project codes, ticket numbers, sender lookups) without additional infrastructure.

| Pros | Cons |
|---|---|
| No email storage | Limited to metadata fields only |
| Fast keyword matching on known entities | Misses keywords in email body |
| Database-native FTS performance | Requires robust metadata extraction pipeline |
| No external dependencies | Extraction quality caps recall |

---

## 6. Alternatives Considered and Rejected

### Database-Native FTS (SQLite FTS5 / PostgreSQL tsvector)

Evaluated for keyword matching but **fundamentally incompatible** with the no-storage requirement. FTS fundamentally requires indexing and storing email body text, which violates the architecture's data privacy constraints. Rejected approaches include naive hybrid RAG and Enhanced Hybrid RAG (FTS + EWS reranking).

---

## 7. Options Comparison Matrix

| Criteria | Option 1: Simple RAG | Option 2: SPLADE | **Option 3: Advanced RAG** *(Recommended)* | Option 4: EWS Search *(Rejected)* | Option 5: Metadata FTS *(Merged)* |
|---|---|---|---|---|---|
| **Accuracy** | 75% | ~88% | **~96%** | 75% | ~80% |
| **RAG Pipeline Architecture** | Single-stage | Dual-embedding (dense+sparse) | **Multi-stage + cross-encoder** | Vector + EWS fusion | Vectors only |
| **Document Ingestion** | Basic (vectors only) | Dual embedding (dense+sparse) | **Dense + sparse + metadata extraction** | Basic (vectors only) | Basic (vectors only) |
| **Query Processing** | Single search | Parallel hybrid search | **Multi-variant + cross-encoder** | Vector + EWS fusion | Parallel hybrid search |
| **Generation** | Direct LLM | Direct LLM | **Structured reports** | Direct LLM | Direct LLM |
| **Query Enrichment** | ✗ No | ✗ No | **✓ LLM (6 variants)** | ✗ No | ✗ No |
| **Keyword Matching** | ✗ No | ✓ SPLADE sparse | **✓ SPLADE + Metadata FTS** | ✓ EWS native | ✓ Metadata FTS |
| **Reranking** | ✗ No | ✗ No | **✓ Cross-Encoder** | ✗ No | ✗ No |
| **Latency (est.)** | ~160ms | ~180ms | **~90ms retrieval + ~300ms total*** | ~200–500ms | ~100–150ms |
| **Network Dependency** | ✗ No (retrieval) | ✗ No (retrieval) | **✗ No (retrieval), ✓ Yes (hydration)** | ✓ Yes (EWS) | ✗ No |
| **External Dependency** | None | SPLADE model | **Ollama LLM + Cross-Encoder + SPLADE** | EWS API | None |
| **Embedding Inversion Protection** | Required (DP noise) | Required (DP noise) | **Required (DP noise)** | Required (DP noise) | Required (DP noise) |
| **User Partitioning** | Required | Required | **Required** | Required | Required |

> ⚠️ *Latency estimates are indicative pending EWS benchmark in target  environment. Cross-encoder and LLM generation latency are model-size and hardware-dependent.*

---

## 8. Decision

**Adopt Option 3: Advanced RAG with the following mandatory modifications.**

Implement an **Advanced Dual-Encoder RAG architecture** utilizing JIT (Just-In-Time) Hydration, incorporating Metadata FTS from Option 5 as a merged third retrieval path.

### Decision Rationale

| Driver | Outcome |
|---|---|
| **Accuracy** | Option 3's multi-variant enrichment + cross-encoder reranking achieves the highest relevance (~96%) — essential for an executive-grade assistant |
| **No Email Storage** | JIT Hydration ensures raw email text exists only in RAM during the generation window, satisfying the hard constraint |
| **Keyword Matching** | Relational SPLADE + Metadata FTS provides precision on both unstructured body semantics and structured entity IDs |
| **Security** | NER Anonymization Gateway + Output Scrubber + Gaussian noise on embeddings creates a layered defense appropriate for L2–L4 data |
| **Extensibility** | The pipeline architecture supports addition of new retrieval paths (e.g., Slack, SharePoint) without restructuring |

### Mandatory Implementation Requirements

1. **Relational SPLADE schema** — no native sparse vector types in SQLite
2. **Explicit JIT Hydration lifecycle** with secure memory wipe post-generation
3. **NER Anonymization Gateway** before any ML model receives hydrated text
4. **Output Scrubbing** with SECURITY_SCRUB_EVENT alerting
5. **User-ID partitioning** enforced at middleware layer on all queries
6. **Gaussian noise** (sigma 0.01–0.05) on all dense embeddings before storage
7. **Kubernetes `swappiness=0`** and swap-disabled pods for the Grounding Service
8. **Ephemeral cache** TTL-bound to 5 minutes, heap memory only

---

## 9. Target Architecture

### 9.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                │
│              EWS (Exchange)  /  Slack  /  SharePoint                │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  Fetching latest emails
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PERSONAL DATA INGESTOR                           │
│                                                                     │
│  1. Classify email (L1–L4)                                          │
│  2. Chunk (512-token, 128-token overlap)                            │
│  3. Dense Embed (intfloat/multilingual-e5-base, 768-dim)            │
│  4. Sparse Embed (SPLADE-cocondenser-ensemble-distil)               │
│  5. Extract Metadata (subject, sender, project IDs — NO body)       │
│  6. Apply Gaussian noise to dense vectors                           │
│  7. Write to Personal Embedding Storage (SQLite PVC)               │
│  8. ⚠️  PURGE raw email text from memory                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  Daily refresh / incremental sync
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  PERSONAL EMBEDDING STORAGE (SQLite PVC)            │
│                                                                     │
│  • embeddings table       (chunk_id, user_id, dense_vector [BLOB])  │
│  • splade_tokens table    (chunk_id, user_id, token_id, weight)     │
│  • metadata_fts table     (FTS5: subject, sender, extracted_ids)    │
│                                                                     │
│  ✗ NO email body text stored anywhere                               │
│  ✗ NO subject line stored as plaintext                              │
│  ✓ All queries enforce WHERE user_id = :current_user               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  Loaded into OpenShift PVC
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GROUNDING SERVICE (MCP)                          │
│                                                                     │
│  RETRIEVAL PHASE:                                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  User Query → LLM Query Enrichment (6 variants)              │  │
│  │       ↓                                                       │  │
│  │  [Parallel per variant]                                       │  │
│  │  Dense ANN Search ──┐                                        │  │
│  │  SPLADE SQL JOIN ───┼→ Per-variant RRF → Cross-variant RRF  │  │
│  │  Metadata FTS ──────┘                                        │  │
│  │       ↓                                                       │  │
│  │  Top-30 Candidate chunk_ids (NO text)                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  JIT HYDRATION PHASE (RAM only):                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Fetch email bodies via EWS/Ingestor API for Top-30 IDs      │  │
│  │  → Ephemeral cache (5-min TTL, heap memory, swappiness=0)    │  │
│  │  → NER Anonymization Gateway                                 │  │
│  │       Mask: credentials, vault codes, PAN, SIN               │  │
│  │       Build: token_map in RAM                                │  │
│  │  → Cross-Encoder Reranking (query, anonymized_text)          │  │
│  │  → Top-5 to Top-10 candidates                                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  GENERATION PHASE:                                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Ollama LLM (on-prem) ← anonymized context only             │  │
│  │  → Output Scrubber (regex: vault codes, PAN, credentials)    │  │
│  │  → De-anonymize by clearance level (L1–L4)                  │  │
│  │  → ⚠️  PURGE all hydrated text + token_map from memory       │  │
│  │  → Return response to  user                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Security Boundary Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│  TRUST BOUNDARY:  On-Premises OpenShift Cluster                   │
│                                                                      │
│  ┌────────────────┐    server-to-server     ┌──────────────────┐    │
│  │  Data Sources  │ ──────────────────────► │ Personal Data    │    │
│  │  EWS/Slack     │   (OAuth, mTLS)         │ Ingestor         │    │
│  └────────────────┘                         └────────┬─────────┘    │
│                                                      │              │
│                                              Store embeddings only   │
│                                                      │              │
│                                             ┌────────▼─────────┐    │
│                                             │ Personal Embedding│    │
│  ┌────────────────┐   MCP (local)           │ Storage (SQLite)  │    │
│  │    User     │ ──────────────────────► │                   │    │
│  │   ( App)    │                         │ Grounding Service │    │
│  └────────────────┘                         │ MCP               │    │
│                                             │                   │    │
│                                             │ JIT Hydration     │    │
│                                             │ ← EWS API call   │    │
│                                             │ (RAM only)        │    │
│                                             └───────────────────┘    │
│                                                                      │
│  ✗ No email text crosses the trust boundary to any storage           │
│  ✗ No email text leaves the trust boundary                           │
│  ✓ All inter-service calls use mTLS                                  │
│  ✓ All pods run with swappiness=0                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 9.3 JIT Hydration Memory Lifecycle *(REVISED: March 2026)*

```
                    query received
                         │
              ┌──────────▼──────────┐
              │   HybridRetriever   │
              │   returns chunk_ids │  ← No text. IDs only.
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  EWSHydrationClient │
              │  batch fetch via    │  ← Network call, OAuth token
              │  EWS GetItem API    │
              └──────────┬──────────┘
                         │ raw email bodies (strings in heap)
              ┌──────────▼──────────┐
              │  EphemeralCache     │
              │  (heap, 5-min TTL,  │  ← swappiness=0 enforced
              │   50 entries max)   │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  AnonymizationGW    │
              │  NER pass → masks   │  ← Credentials, vault codes, PAN
              │  builds token_map   │    token_map in heap RAM only
              └──────────┬──────────┘
                         │ anonymized text
              ┌──────────▼──────────┐
              │  CrossEncoder       │
              │  score(query, text) │  ← Both strings in RAM
              │  → Top-N ranking    │
              └──────────┬──────────┘
                         │ top-N anonymized chunks
              ┌──────────▼──────────┐
              │  Ollama LLM         │
              │  generation         │  ← Anonymized context only
              └──────────┬──────────┘
                         │ raw response
              ┌──────────▼──────────┐
              │  ResponseScrubber   │
              │  + De-anonymizer    │  ← token_map applied, then purged
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  ⚠️  MEMORY PURGE   │
              │  hydrated text = ∅  │  ← Secure zero-overwrite
              │  token_map = ∅      │
              └──────────┬──────────┘
                         │
                    response to user
```

---

## 10. Consequences

### Positive Consequences

- **Highest retrieval accuracy** (~96%) for both semantic and keyword queries in enterprise email context
- **Full compliance** with "No Email Storage" constraint — raw text never touches disk
- **Multi-layered security** — Gaussian noise (storage), NER anonymization (in-flight), output scrubbing (generation), user partitioning (access)
- **Extensible pipeline** — additional data sources (Slack, SharePoint, Teams) can be added as new ingestor paths without restructuring the retrieval or generation layers
- **Structured outputs** — LLM prompt templates enable task extraction, calendar optimization, and formatted report generation
- **EWS independence at retrieval time** — the retrieval phase requires no live network calls; EWS is only contacted during JIT Hydration, reducing query-path dependencies

### Negative Consequences

- **Increased complexity** — the pipeline has more components than Options 1 or 2, requiring careful orchestration and testing
- **Additional model dependencies** — SPLADE encoder, Cross-Encoder, and Ollama LLM must all be deployed and maintained on-prem
- **SPLADE at scale** — SQL JOIN-based sparse retrieval must be benchmarked at 50K+ emails; an index maintenance strategy is required
- **HyDE risk** — hypothetical document generation may produce -specific terminology mismatches; this should be monitored and the feature made toggleable
- **EWS availability coupling at hydration time** — a graceful degradation path (metadata-only response) must be implemented for EWS outages

---

## 11. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation | Residual Risk |
|---|---|---|---|---|
| **Embedding inversion attack** — stored vectors reconstructed to reveal L3/L4 text | Medium | Critical | Gaussian noise injection (sigma 0.01–0.05) before storage; accept 2–4% recall loss | Low |
| **Cross-user data leakage** — user A retrieves user B's embeddings | Low | Critical | `user_id` partitioning enforced at DB middleware layer; automated test asserts 0 cross-user results | Very Low |
| **Hydrated text surviving in memory** — text not purged after generation | Low | High | Explicit zero-overwrite on cache eviction; `swappiness=0`; memory safety integration test in CI | Low |
| **SPLADE SQL JOIN performance degradation** at 200K+ emails | High | Medium | Benchmark at 50K and 200K corpus sizes; consider partitioned index or time-windowed token pruning | Medium |
| **EWS unavailability at hydration time** | Medium | Medium | Circuit breaker (3 failures → 60s open); graceful degradation to metadata-only response | Low |
| **OAuth token expiry mid-query** | Medium | Low | Transparent token refresh in EWSHydrationClient; proactive refresh before expiry | Very Low |
| **HyDE generating misleading synthetic documents** | Medium | Medium | Monitor HyDE contribution to RRF scores; make HyDE toggleable via feature flag | Medium |
| **LLM generating responses that imply masked credentials** | Low | High | Output scrubbing regex + SECURITY_SCRUB_EVENT alerting; red-team testing | Low |
| **Kubernetes pod swap spilling hydrated text to disk** | Low | Critical | `swappiness=0` enforced in pod spec; deployment validation test | Very Low |

---

## 12. Implementation Phases

This ADR defines the target state. Codebase build or migration follows these phases:

### Phase 1 — Foundation & Security Hardening *(Sprint 1–2)*

**Goal:** Establish all security controls before any RAG capability is built.

Deliverables:
- SQLite schema with `embeddings`, `splade_tokens`, `metadata_fts` tables and migration script
- `UserPartitionedDB` middleware enforcing `user_id` filter on all queries
- `GaussianNoiseInjector` (sigma configurable 0.01–0.05) with unit test asserting cosine similarity ≥ 0.95
- Pre-commit CI hook blocking SQL INSERT with body/content/text columns
- No-storage audit: scan all existing code paths for email text persistence; remediate all findings
- `SECURITY.md` documenting all controls

### Phase 2 — Relational SPLADE + Dense Dual-Encoder Retrieval *(Sprint 3–4)*

**Goal:** Implement working hybrid retrieval with all three search paths and validated benchmarks.

Deliverables:
- `PersonalDataIngestor`: chunk → dense embed → SPLADE embed → Gaussian noise → SQLite write → text purge (idempotent)
- `HybridRetriever`: parallel dense ANN + SPLADE SQL JOIN + Metadata FTS → RRF fusion → returns `{chunk_id, message_id, rrf_score}` only
- `MetadataExtractor`: project ID regex, ticket number extraction, sender normalization
- Benchmark suite: recall@10, p50/p95/p99 latency at 10K and 50K email corpus; SQLite file size
- Updated ADR-003 Comparison Matrix with real latency figures

### Phase 3 — JIT Hydration + NER Anonymization Gateway *(Sprint 5–6)*

**Goal:** Safe cross-encoder reranking with no text persisted beyond the query window.

Deliverables:
- `EWSHydrationClient`: batch GetItem, connection pooling, circuit breaker, OAuth refresh, graceful degradation
- `EphemeralHydrationCache`: 5-min TTL, LRU eviction, secure zero-overwrite wipe, context manager API
- `AnonymizationGateway`: spaCy NER + custom patterns (credentials, vault codes, PAN, SIN), `token_map` lifecycle
- `CrossEncoderReranker`: `cross-encoder/ms-marco-MiniLM-L-6-v2`, batch scoring, text purge post-scoring
- Memory safety integration test: verifies no hydrated text survives in heap after generation

### Phase 4 — LLM Generation + Output Scrubbing *(Sprint 7–8)*

**Goal:** Structured, safe LLM generation with clearance-level-aware de-anonymization.

Deliverables:
- Prompt template library (YAML): Email Summary, Structured Report, Task/Calendar Extraction
- `OllamaClient`: streaming, 30s timeout, no prompt/response logging
- `ResponseScrubber`: regex-based credential/PAN/vault detection, `SECURITY_SCRUB_EVENT` Prometheus counter + alert
- De-anonymization by clearance level (L1–L4 rules)
- End-to-end pipeline test with full latency profiling

### Phase 5 — Observability, Load Testing & ARB Sign-off *(Sprint 9–10)*

**Goal:** Production-ready system with ARB sign-off package.

Deliverables:
- OpenTelemetry instrumentation: spans per pipeline stage, no PII in span attributes, Jaeger export
- Prometheus metrics: query duration, EWS latency, cache hit/miss, scrub events, partition violation counter
- Grafana dashboard: P50/P95/P99 per stage, pipeline success rate, scrub event rate
- Load test (Locust/k6): 50 concurrent users, 10 minutes, targets: P99 < 3s, EWS < 500ms, error rate < 0.1%
- Security test suite: cross-user isolation, vault code scrubbing, no-disk-persistence assertion
- ARB package: Security Attestation, Benchmark Results, Gap Closure Report, Risk Register

---

## 13. Revision History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | March 2, 2026 | AI Platform Team | Initial ADR with Options 1–5, comparison matrix, empty Decision section |
| 2.0 | March 2026 | AI Platform Team (revised) | **Critical corrections:** JIT Hydration explicit step added to Option 3 pipeline; Relational SPLADE schema replacing native sparse vector assumption; EWS granularity mismatch documented and Option 4 rejected. **New sections:** Embedding inversion attack mitigation; user-level vector partitioning; ephemeral cache specification; NER anonymization gateway; output scrubbing and de-anonymization by clearance level. **Decision section populated.** Option 5 merged into Option 3. |

---

*© 2026 Royal Bank of Canada —  AI Platform Team — CONFIDENTIAL INTERNAL USE ONLY*

---

> **Next Steps:**
> 1. ARB review and approval of this ADR
> 2. Security team sign-off on Gaussian noise sigma selection and NER pattern coverage
> 3. EWS benchmark in target environment to validate latency estimates
> 4. Begin Phase 1 implementation using this ADR as the specification
