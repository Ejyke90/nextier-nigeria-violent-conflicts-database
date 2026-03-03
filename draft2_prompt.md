# ADR-003 — RAG Methods and Strategies for Best Results
### RBC Personal Grounding Assistant — Production Architecture (v3.0)

---

| Field | Value |
|---|---|
| **Document ID** | ADR-003 |
| **Status** | **Approved — Pending ARB Ratification** |
| **Created By** | AI Platform Team |
| **Last Updated** | March 2026 |
| **Version** | 3.0 (Final — PVC/S3/SQLite Architecture) |
| **Proposed Date** | March 2, 2026 |
| **Scale Target** | 70,000 RBC employees |

> **CLASSIFICATION: RESTRICTED — Level 3 Internal. Not for distribution outside the RBC AI Platform team.**

---

## Principal Architect Assessment

> This section records the independent architecture review of both the ADR and the AI Agent's initial proposal before ARB submission.

### On the AI Agent's Initial Review — Agreement & Gaps

The AI Agent's proposal to adopt **Option 3 (Advanced RAG) with S3 as source of truth and PVC as warm cache** is **architecturally sound and the correct direction**. The decoupling of the search index (SQLite on PVC) from the sensitive payload (email bodies fetched transiently via EWS JIT) is the right answer for a regulated financial environment at this scale.

However, **the proposal as written is not yet production-ready for 70,000 users.** Seven critical gaps must be addressed before ARB sign-off:

| # | Gap | Severity |
|---|---|---|
| 1 | EWS rate limiting at scale: 700 concurrent users × 30 JIT fetches = 21,000 simultaneous EWS calls. No queue or back-pressure mechanism specified. | 🔴 Critical |
| 2 | PVC IOPS budget not sized. 70,000 SQLite files × read/write ops during peak has no capacity model. | 🔴 Critical |
| 3 | S3 → PVC sync is every 15 minutes but conflict resolution during active-query windows is unspecified. | 🔴 Critical |
| 4 | Embedding model serving capacity for 70K users not addressed (GPU allocation, queue depth). | 🟠 High |
| 5 | Cold start during pod restart — PVC not mounted yet, S3 fallback latency undefined. | 🟠 High |
| 6 | No request queue or concurrency governor for 6-variant LLM enrichment at peak load. | 🟠 High |
| 7 | Decision Drivers missing three production-grade drivers: Scalability, Operational Observability, Cost/GPU Footprint. | 🟡 Medium |

All seven gaps are addressed in this document. This ADR constitutes the **complete, corrected specification** for production implementation.

---

## Table of Contents

1. [Glossary](#1-glossary)
2. [Context](#2-context)
3. [Challenge](#3-challenge)
4. [Decision Drivers](#4-decision-drivers)
5. [Options Considered](#5-options-considered)
6. [Alternatives Considered and Rejected](#6-alternatives-considered-and-rejected)
7. [Options Comparison Matrix](#7-options-comparison-matrix)
8. [Decision](#8-decision)
9. [Target Architecture — Production at 70K Users](#9-target-architecture--production-at-70k-users)
10. [Production Capacity Model](#10-production-capacity-model)
11. [Consequences](#11-consequences)
12. [Risks and Mitigations](#12-risks-and-mitigations)
13. [Implementation Phases](#13-implementation-phases)
14. [Revision History](#14-revision-history)

---

## 1. Glossary

### Core Technologies

| Term | Definition |
|---|---|
| **FTS** | Full-Text Search — Database-native keyword search indexing (SQLite FTS5) |
| **RAG** | Retrieval-Augmented Generation — AI pattern combining document retrieval with LLM generation |
| **RRF** | Reciprocal Rank Fusion — Algorithm for combining multiple search result rankings |
| **MCP** | Model Context Protocol — Interface protocol for AI assistant integration |
| **EWS** | Exchange Web Services — Microsoft API for real-time email access from Exchange Server |
| **JIT** | Just-In-Time Hydration — Fetching raw email text transiently into RAM only; never persisted |
| **PVC** | Persistent Volume Claim — Kubernetes-native persistent storage, used here as warm local cache |
| **S3** | Object store (RBC on-prem equivalent) — durable source of truth for per-user SQLite files |
| **NER** | Named Entity Recognition — ML technique for identifying and masking sensitive entities in text |
| **ANN** | Approximate Nearest Neighbour — Fast vector similarity search algorithm (sqlite-vec) |
| **OCP** | OpenShift Container Platform — RBC's on-premises Kubernetes distribution |
| **Gaussian Noise** | Random noise from normal distribution added to embeddings before storage to prevent embedding inversion attacks that could reconstruct source text. Recall loss will be about 2–4% loss for security. |
| **IOPS** | Input/Output Operations Per Second — storage throughput metric; critical for PVC sizing |

### Embedding Types

| Term | Definition |
|---|---|
| **Dense Vectors** | Traditional semantic embeddings (768-dimensional continuous values) |
| **Sparse Vectors** | Learned keyword embeddings with mostly zero values (1,000–30,522 dimensions) |
| **SPLADE** | Sparse Lexical and Expansion Model — neural model for learned keyword matching. `splade_tokens` table stores sparse vectors as rows `(chunk_id, token_id, weight)`. Only non-zero values stored; uses SQL JOIN for scoring. |
| **Cross-Encoder** | Neural reranking model that jointly scores a (query, document) pair with full attention — requires raw text at scoring time, supplied via JIT Hydration |

### Search Enhancement Methods

| Term | Definition |
|---|---|
| **HyDE** | Hypothetical Document Embeddings — generates a hypothetical answer document to improve retrieval |
| **Semantic Variants** | Multiple LLM reformulations of the query for broader recall coverage |
| **Query Enrichment/Expansion** | LLM-based query rewriting and variant generation |
| **BM25** | Best Match 25 — probabilistic ranking function for keyword relevance |

---

## 2. Context

The Personal Grounding Service revolutionizes how RBC assists users to interact with their entire digital work ecosystem — starting with email. By seamlessly integrating with RBC's Exchange environment, it delivers sophisticated assistance via email communications intelligence. Leveraging advanced RAG (Retrieval-Augmented Generation) capabilities, it enables semantic search, pattern recognition, and predictive analysis. Through an MCP (Model Context Protocol) interface, it allows RBC's AI assistant to provide contextual, intelligent assistance that anticipates needs, streamlines decision-making, and elevates productivity across the enterprise.

**Scale:** 70,000 RBC employees. Each user has a dedicated per-user SQLite database containing only their personal embeddings and metadata — zero email body text stored anywhere on any persistent medium.

**Infrastructure Stack:** RBC on-premises OpenShift (OCP) cluster, on-prem Ollama LLM, on-prem embedding services, RBC S3-compatible object store, Exchange Web Services (EWS) for live email access.

---

## 3. Challenge

Enterprise email search requires both semantic understanding (natural language queries) and exact keyword retrieval (Message IDs, project codes, employee IDs). However, **RESTRICTED emails contain Level 2–4 classified information** that must never be stored, indexed, or processed locally.

### Hard Constraints

1. **Zero Text Storage:** Email body text must never be persisted to disk for Level 2–4 data. Only embeddings and metadata may be stored.
2. **User Isolation:** Each user's data must be strictly partitioned. Cross-user access is a critical security violation.
3. **Classification-Aware Processing:** System must route queries based on data classification level.
4. **Embedding Inversion Protection:** Dense vectors must be protected against reconstruction attacks.

### Data Classification Requirements

| Level | Classification | Examples | Search Constraints |
|---|---|---|---|
| **L4** | RESTRICTED | Passwords, PINs, vault codes, digital certificates | No text storage permitted; FTS allowed via EWS |
| **L3** | SENSITIVE | PHI, Material Business Information, confidential documents | No text storage permitted; FTS allowed via EWS |
| **L2** | CONFIDENTIAL | Financial information, project documents, source code | No text storage permitted but FTS allowed via EWS |
| **L1** | INTERNAL | Internal directories, policies, HR programs | No text storage permitted but FTS allowed via EWS |
| **L0** | PUBLIC | Public websites, published results | No text storage permitted but FTS allowed via EWS |

---

## 4. Decision Drivers

Decision drivers are listed in priority order. All are non-negotiable unless explicitly marked.

### 4.1 Result Relevance (Primary Priority — Accuracy)
Retrieve the correct emails matching user intent for both semantic and keyword queries. Speed is secondary — correctness takes priority over performance. **Target: ≥ 90% recall@10 on benchmark evaluation set.**

### 4.2 Result Quality (Ranking)
Properly rank retrieved emails so the most relevant result appears first. Users should not need to scroll. **Target: MRR (Mean Reciprocal Rank) ≥ 0.85.**

### 4.3 Data Security (Non-Negotiable)
Prevent unauthorized storage or processing of classified information (RESTRICTED/SENSITIVE/CONFIDENTIAL). Complete audit trail for observability, security events, and regulatory review (OSFI, FINTRAC, PCI-DSS).

### 4.4 User Isolation (Non-Negotiable)
Each user's embeddings, sparse tokens, and metadata must be stored in isolated per-user SQLite files. No shared database. Cross-user access is a CRITICAL security violation.

### 4.5 No Email Storage (Non-Negotiable — Hard Constraint)
Emails must NOT be stored locally. Only embeddings and metadata may be persisted. Raw email text exists exclusively in RAM during the JIT Hydration window. This constraint eliminates all FTS approaches that require indexing email body text.

### 4.6 Response Speed
- Retrieval latency (vector + sparse + metadata): target P95 < 200ms
- JIT Hydration + Cross-Encoder: target P95 < 600ms
- Total response time (including LLM generation): target P95 < 3 seconds
- Cold start penalty (pod restart, PVC not warm): target < 5 seconds via S3 fallback

### 4.7 Scalability (NEW — Critical at 70K Users) *(REVISED: March 2026)*
The architecture must sustain **70,000 concurrent-capable users** with graceful degradation under load. This drives:
- Per-user SQLite file isolation (no shared database contention)
- PVC sharding strategy (no monolithic volume)
- EWS connection pooling and request queue with back-pressure
- Horizontal scaling of OCP worker pods with stateless query processing

### 4.8 Operational Observability (NEW) *(REVISED: March 2026)*
At 70K users, silent failures are unacceptable. The system must expose:
- Per-stage latency metrics (P50/P95/P99) via Prometheus
- EWS availability and throttle rate
- S3 → PVC sync lag and failure rate
- SECURITY_SCRUB_EVENT rate with alerting
- PVC IOPS utilization

### 4.9 Cost and Compute Efficiency (NEW) *(REVISED: March 2026)*
Running 6 LLM query variants × Cross-Encoder × Ollama generation per user request creates significant GPU demand. The architecture must:
- Make query enrichment (6-variant HyDE) **toggleable** — can be reduced to 2–3 variants under GPU pressure
- Implement request queuing to smooth peak demand
- Size GPU nodes based on projected concurrent query volume (see Section 10)

### 4.10 Embedding Inversion Attack Mitigation
Dense embedding vectors are not inherently safe. Inversion attacks can reconstruct source text from stored embeddings. **REQUIRED:** Apply post-hoc Gaussian noise (sigma = 0.01–0.05) to all dense embeddings before storage. Accept 2–4% recall degradation for protection against L3/L4 text reconstruction.

---

## 5. Options Considered

> **Constraint note:** Traditional FTS approaches requiring email text indexing are eliminated. We evaluate alternatives providing keyword matching while respecting the no-storage requirement.

---

### Option 1: Simple RAG with Pure Vector Search

**Description:** Basic RAG pipeline using semantic search only (dense embeddings) without keyword matching, query enrichment, or reranking.

**Architecture:** Per-user SQLite with sqlite-vec extension (embeddings only).

#### Storage Schema
```sql
embeddings (chunk_id, dense_vector[768], metadata)
-- No email text. No sparse tokens.
```

#### RAG Pipeline
```
Document Ingestion:
  EWS/Ingestion Service → Classify → Chunk → Dense Embed (768-dim)
  Apply Gaussian noise to embeddings (inversion protection)
  Store: Embeddings + metadata only (NO email text)
  Per-user SQLite file → S3 object store

Query Processing:
  Load user SQLite from S3 → OCP worker pool
  User query → Dense embed → Vector ANN search
  Return: chunk_ids + metadata (NO text)

Optional JIT Hydration:
  Client fetches email text from EWS using message_ids
  Or: Service fetches transiently for LLM generation (RAM only)
```

| Pros | Cons |
|---|---|
| Simple implementation | Misses exact keyword matches |
| No email storage (privacy compliant) | Lower accuracy on ID/project queries |
| Good semantic understanding | Poor ranking for keyword-heavy queries |
| No additional model dependencies | Not suitable as primary strategy |

---

### Option 2: Hybrid RAG with SPLADE Sparse Vectors

**Description:** Dual-encoder RAG pipeline using both dense vectors (semantic) and SPLADE sparse vectors (learned keyword matching) with RRF fusion. No FTS required. SPLADE provides keyword matching without storing email text.

**Architecture:** Per-user SQLite storing dense embeddings + sparse tokens (relational format).

#### Per-User SQLite Database Schema
```sql
-- Dense vector storage
embeddings (chunk_id, dense_vector[768], metadata)

-- Relational SPLADE storage
splade_tokens (chunk_id, token_id, weight)  -- relational storage
```

> **Note:** SQLite lacks native sparse vector support (30,522 dimensions would waste storage storing zeros). Relational token table is space-efficient but uses SQL JOIN for scoring instead of native vector operators.
>
> **Tradeoff:** JOIN-based scoring is ~10–100x slower than native vector ops at scale, requiring careful indexing and benchmarking at 990+ emails.

#### RAG Pipeline
```
Document Ingestion:
  EWS/Ingestion Service → Classify → Chunk (512 tokens, 128 overlap)
  Dense Embed: multilingual-e5-base (768-dim)
  Sparse Embed: SPLADE-cocondenser (30,522-dim)
  Apply Gaussian noise to dense vectors
  Store: Dense vector + Sparse tokens relationally
  Per-user SQLite file → S3 object store
  Purge email text from memory

Query Processing:
  Load user SQLite from S3 → OCP worker pool
  User query → Dense + Sparse (parallel)
  Dense ANN search + Sparse SQL JOIN search
  RRF fusion → Top-K chunk_ids + scores (NO text)

Optional JIT Hydration:
  Fetch chunks from EWS for selected chunk_ids
  Transient in-memory only for LLM generation
```

| Pros | Cons |
|---|---|
| No email storage | Requires SPLADE model dependency |
| Good keyword matching via sparse vectors | Sparse tokens increase storage vs Option 1 |
| Maintains semantic understanding | SQL JOIN-based sparse search needs benchmarking at scale |
| No network dependency for search operations | More complex than pure vector search |
| SPLADE learns keyword importance contextually | Additional model loading time |

---

### Option 3: Advanced RAG with Query Enrichment and Cross-Encoder *(Recommended)*

**Description:** RAG pipeline with LLM query enrichment, multi-variant search (dense + SPLADE), cross-encoder reranking, and metadata FTS. Highest accuracy for complex queries. Full JIT hydration from EWS. Last retrieval from EWS.

**Architecture:** Per-user SQLite + on-prem LLM + Cross-Encoder (embeddings-only storage). **S3 as source of truth. PVC as warm local cache.**

#### Document Ingestion
```
EWS/Ingestion Service → Classify → Chunk (512 tokens, overlap)
Dense + Sparse embedding (dual encoder)
Metadata extraction (subject, sender, IDs) — NO body text
Apply Gaussian noise to dense vectors
Store: Dense + Sparse + Metadata FTS
Per-user SQLite file → S3 object store
Purge email text from memory
```

#### Query Processing — Multi-Variant Enrichment
```
Load user SQLite from S3 → OCP worker pool (or PVC warm cache)

User query → LLM Query Enrichment:
  - Rewritten query (1 variant)
  - Semantic variants (4 variants)
  - HyDE hypothetical document (1 variant)
  → Total: 6 query variants

Per variant (parallel):
  - Dense ANN search
  - SPLADE SQL JOIN search
  - Metadata FTS search (structured entities)
  → Per-variant RRF fusion

Cross-variant RRF → Top-30 candidates (chunk_ids only)
```

#### JIT Hydration & Reranking (RAM only)
```
Fetch email text from EWS for Top-30 chunks
  → Ephemeral cache (5-min TTL, heap memory, swappiness=0)

NER Anonymization Gateway:
  Mask: credentials, vault codes, PAN, SIN
  Build token_map in RAM

Cross-Encoder scoring (query, anonymized_text)
Select Top-5 to Top-10 reranked results
Purge hydrated text from memory
```

#### LLM Generation
```
Ollama (on-prem) receives anonymized context
Output scrubber (detect/redact credentials, vault codes)
De-anonymize by clearance level (L1–L4)
Purge all hydrated text + token_map
Return final response
```

| Pros | Cons |
|---|---|
| Highest accuracy | Slowest (most pipeline stages) |
| Multi-variant diversity | LLM dependency for query enrichment |
| No email storage | Not suitable for interactive/autocomplete search |
| Cross-encoder precision | Most complex implementation |
| Structured report generation | High computational cost |
| Metadata FTS for exact entity matching | HyDE may generate docs missing RBC-specific terminology |
| Multi-layer security (noise, NER, scrubbing) | EWS coupling at hydration time |

---

### Option 4: Hybrid RAG with EWS Native Search *(Rejected)*

**Description:** Vector search for initial retrieval, then EWS native search for keyword refinement.

**Critical Limitation:** Granularity mismatch — Vector chunks vs EWS threads incompatible for RRF fusion. Normalization degrades quality.

**Additional Production Concern at 70K users:** EWS becomes a query-path dependency (not just hydration-path), meaning any Exchange throttling event collapses the entire retrieval pipeline — not just generation.

| Pros | Cons |
|---|---|
| No email storage | Chunk/thread granularity mismatch |
| Leverages Exchange's native search | Network dependency at retrieval time |
| Keyword matching without local FTS | Higher latency due to API calls |
| Emails always up-to-date | Cannot control EWS ranking quality |
| | Tight EWS coupling for ALL queries |
| | Potential rate limiting from Exchange |

**Status: REJECTED** — Granularity mismatch makes reliable RRF fusion impractical. At 70K users, making EWS a retrieval-path dependency (not just hydration) is an unacceptable availability risk.

---

### Option 5: Metadata-Only FTS *(Integrated into Option 3)*

**Description:** FTS on metadata fields only (subject, sender, extracted IDs) without indexing email body text.

**Status: MERGED into Option 3** as a third parallel search path. The `metadata_fts` table (SQLite FTS5) provides 100% precision for structured entity matching (project codes, incident numbers, sender lookups) without additional infrastructure.

---

## 6. Alternatives Considered and Rejected

### PostgreSQL as Primary Store
Evaluated but **rejected**. PostgreSQL adds network hop latency for every query, requires a shared cluster that creates multi-tenancy complexity at 70K users, and introduces a stateful service dependency that conflicts with the OCP pod scaling model. Per-user SQLite files on PVC achieve better isolation, lower latency (local reads), and simpler operational model.

### Redis for Ephemeral Cache
Evaluated but **rejected** for hydrated email text. Redis persists to disk by default (AOF/RDB), which would violate the no-storage constraint for Level 3/4 email bodies unless carefully configured. Heap-memory-only ephemeral cache within the OCP pod is simpler and provably non-persistent. Redis may be reconsidered for non-sensitive query metadata caching in a future iteration.

### Database-Native FTS (SQLite FTS5 / PostgreSQL tsvector) on Email Body
**Rejected.** FTS fundamentally requires indexing and storing email body text, violating the hard constraint.

---

## 7. Options Comparison Matrix

| Criteria | Option 1: Simple RAG | Option 2: SPLADE Hybrid | **Option 3: Advanced RAG** *(Recommended)* | Option 4: EWS Search *(Rejected)* |
|---|---|---|---|---|
| **Accuracy** | ~75% | ~88% | **~96%** | ~75% (rejected) |
| **RAG Pipeline Architecture** | Single-stage semantic | Dual embedding (dense+sparse) | **Multi-stage + cross-encoder** | Vector + EWS fusion |
| **Document Ingestion** | Basic (vectors only) | Dual embedding (dense+sparse) | **Dense + sparse + metadata extraction** | Basic (vectors only) |
| **Query Processing** | Single search | Parallel hybrid search | **Multi-variant + cross-encoder** | Vector + EWS fusion |
| **Generation** | Direct LLM | Direct LLM | **Structured reports** | Direct LLM |
| **Query Enrichment** | ✗ No | ✗ No | **✓ LLM (6 variants, toggleable)** | ✗ No |
| **Keyword Matching** | ✗ No | ✓ SPLADE sparse | **✓ SPLADE + Metadata FTS** | ✓ EWS native |
| **Reranking** | ✗ No | ✗ No | **✓ Cross-Encoder** | ✗ No |
| **Storage Model** | SQLite (S3+PVC) | SQLite (S3+PVC) | **SQLite (S3+PVC, per-user)** | SQLite (S3+PVC) |
| **Latency (retrieval)** | Very fast | Fast | **Moderate*** | Moderate |
| **Latency (total)** | Fast | Fast | **Slow (highest accuracy)*** | Moderate |
| **Network Dependency** | ✗ No (retrieval) | ✗ No (retrieval) | **✗ No (retrieval) / ✓ EWS (hydration only)** | ✓ Yes (EWS always) |
| **External Dependency** | None | SPLADE model | **Ollama LLM + Cross-Encoder + SPLADE** | EWS API |
| **Embedding Inversion Protection** | Required | Required | **Required (Gaussian noise)** | Required |
| **User Partitioning** | Per-user SQLite | Per-user SQLite | **Per-user SQLite** | Per-user SQLite |
| **70K User Ready** | Needs capacity model | Needs capacity model | **Yes — with sharding & EWS queue** | ✗ No — EWS bottleneck |

> ⚠️ *All latency figures are estimates pending EWS benchmark and embedding service performance validation in the RBC target environment.*

---

## 8. Decision

**Adopt Option 3: Advanced RAG with S3 as Source of Truth and PVC Warm Cache.**

Implement an **Advanced Dual-Encoder RAG architecture** with JIT Hydration, incorporating Metadata FTS as a merged third retrieval path. Per-user SQLite databases are the storage unit. S3 is the durable source of truth. PVC provides warm local cache for sub-millisecond retrieval. EWS is contacted only during JIT Hydration — never during the retrieval phase.

### Decision Rationale

| Driver | Outcome |
|---|---|
| **Accuracy** | Multi-variant enrichment + cross-encoder achieves ~96% — essential for executive-grade assistance |
| **No Email Storage** | JIT Hydration ensures raw email text exists only in RAM during the generation window |
| **User Isolation** | Per-user SQLite files on S3/PVC provide natural, enforced per-user data boundaries |
| **Keyword Matching** | Relational SPLADE + Metadata FTS provides precision on both unstructured semantics and structured entity IDs |
| **Security** | Gaussian noise + NER anonymization + output scrubbing + per-user isolation creates layered defense appropriate for L2–L4 |
| **Scalability at 70K** | PVC sharding + EWS request queue + stateless query workers enables horizontal scaling |
| **Cold Start Elimination** | S3 → PVC 15-minute sync daemon ensures warm files are available before user queries arrive |
| **Operational Resilience** | EWS circuit breaker with metadata-only degraded mode ensures graceful failure at Exchange outages |

### Mandatory Implementation Requirements

1. **Per-user SQLite files** — one file per employee, containing embeddings, SPLADE tokens, and metadata FTS only
2. **S3 as source of truth** — all SQLite writes go to S3; PVC is a read-optimised cache layer
3. **Background sync daemon** — proactively copies S3 files to PVC every 15 minutes; workers read from PVC only
4. **PVC sharding** — shard 70,000 user files across multiple PVCs (see Section 10); no monolithic volume
5. **PVC read-only for query workers** — only the sync daemon has write access to PVC; eliminates SQLite locking contention
6. **EWS request queue** — bounded concurrency queue with back-pressure for JIT Hydration; prevents Exchange throttling
7. **Relational SPLADE schema** — no native sparse vector types in SQLite; `(chunk_id, token_id, weight)` rows
8. **Explicit JIT Hydration lifecycle** — secure zero-overwrite memory purge post-generation; `swappiness=0` on all pods
9. **NER Anonymization Gateway** before any ML model receives hydrated text
10. **Output scrubbing** with `SECURITY_SCRUB_EVENT` Prometheus alerting
11. **Gaussian noise** (sigma 0.01–0.05) on all dense embeddings before S3/PVC write
12. **Query enrichment toggleable** — 6-variant default; 2-variant fallback under GPU pressure via feature flag

---

## 9. Target Architecture — Production at 70K Users

### 9.1 Full System Architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  DATA SOURCES                                                                ║
║  Exchange (EWS) · Slack · SharePoint                                         ║
╚══════════════════════╦═══════════════════════════════════════════════════════╝
                       ║ OAuth / mTLS
                       ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  EWS / INGESTION SERVICE                                                     ║
║                                                                              ║
║  1. Classify email (L0–L4)                                                   ║
║  2. Chunk: 512-token windows, 128-token overlap                              ║
║  3. Dense Embed: multilingual-e5-base (768-dim, on-prem GPU)                 ║
║  4. Sparse Embed: SPLADE-cocondenser-ensemble-distil (on-prem GPU)           ║
║  5. Extract: subject, sender, project IDs, ticket numbers (NO body text)     ║
║  6. Apply Gaussian noise (sigma=0.01–0.05) to dense vectors                  ║
║  7. Write to per-user SQLite file                                             ║
║  ⚠️  8. PURGE all raw email text from memory immediately                     ║
╚══════════════════════╦═══════════════════════════════════════════════════════╝
                       ║ Write per-user SQLite file
                       ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  S3 OBJECT STORE (Source of Truth)                                           ║
║                                                                              ║
║  /embeddings/{user_hash}.db   ← per-user SQLite file                        ║
║                                                                              ║
║  Schema per file:                                                            ║
║  ├── embeddings(chunk_id, dense_vector BLOB, metadata JSON)                 ║
║  ├── splade_tokens(chunk_id, token_id, weight)                               ║
║  └── metadata_fts (FTS5: subject, sender, extracted_ids, project_names)      ║
║                                                                              ║
║  ✗ NO email body text in any column of any table                            ║
║  ✗ NO subject stored as plaintext (only in FTS5 index)                      ║
╚══════════════════════╦═══════════════════════════════════════════════════════╝
                       ║ Background sync every 15 min
                       ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  PVC WARM CACHE LAYER (OCP Persistent Volume Claims)                         ║
║                                                                              ║
║  Shard strategy: 10 PVCs, ~7,000 users each, sharded by email prefix hash   ║
║  Mount mode: READ-ONLY for all query worker pods                             ║
║  Write access: EXCLUSIVE to sync daemon pod only                             ║
║                                                                              ║
║  PVC-A: users [0000–0FFF hash range] ── 7,000 SQLite files                  ║
║  PVC-B: users [1000–1FFF hash range] ── 7,000 SQLite files                  ║
║  ...                                                                         ║
║  PVC-J: users [9000–9FFF hash range] ── 7,000 SQLite files                  ║
║                                                                              ║
║  Cold start fallback: if PVC miss → fetch from S3 directly (< 2s)           ║
╚══════════════════════╦═══════════════════════════════════════════════════════╝
                       ║ Local read (sub-millisecond)
                       ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  GROUNDING SERVICE (MCP — OCP Worker Pods, horizontally scaled)              ║
║                                                                              ║
║  ┌─ RETRIEVAL PHASE ─────────────────────────────────────────────────────┐  ║
║  │                                                                        │  ║
║  │  User Query → LLM Query Enrichment (Ollama, on-prem)                  │  ║
║  │    └── 6 variants: rewrite(1) + semantic(4) + HyDE(1)                 │  ║
║  │         [TOGGLEABLE: reduce to 2–3 under GPU pressure]                 │  ║
║  │                                                                        │  ║
║  │  Per variant, parallel:                                                │  ║
║  │    ├── Dense ANN search (sqlite-vec)                                   │  ║
║  │    ├── SPLADE SQL JOIN search (splade_tokens)                          │  ║
║  │    └── Metadata FTS search (FTS5, subject/sender/IDs)                 │  ║
║  │         └── Per-variant RRF (k=60)                                    │  ║
║  │                                                                        │  ║
║  │  Cross-variant RRF → Top-30 candidate chunk_ids (NO text returned)    │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌─ JIT HYDRATION PHASE (RAM only — never touches disk) ─────────────────┐  ║
║  │                                                                        │  ║
║  │  EWS Request Queue (bounded: max 20 concurrent per pod)               │  ║
║  │    └── EWSHydrationClient.batch_get(message_ids, user_token)          │  ║
║  │         Connection pool: 5 connections, 30s timeout                   │  ║
║  │         Circuit breaker: 3 failures → 60s open → degraded mode        │  ║
║  │                                                                        │  ║
║  │  Ephemeral Cache:                                                      │  ║
║  │    5-min TTL · heap memory only · swappiness=0 · LRU 50 entries       │  ║
║  │    secure zero-overwrite on eviction                                   │  ║
║  │                                                                        │  ║
║  │  NER Anonymization Gateway:                                            │  ║
║  │    Mask: credentials, vault codes (VAULT-[A-Z0-9]{8}), PAN, SIN       │  ║
║  │    Build: token_map {placeholder→original} in RAM                     │  ║
║  │                                                                        │  ║
║  │  Cross-Encoder Reranking:                                              │  ║
║  │    score(query_string, anonymized_chunk_string)                        │  ║
║  │    Model: cross-encoder/ms-marco-MiniLM-L-6-v2                        │  ║
║  │    → Top-5 to Top-10 reranked candidates                              │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌─ GENERATION PHASE ────────────────────────────────────────────────────┐  ║
║  │                                                                        │  ║
║  │  Ollama LLM (on-prem) ← anonymized context only                       │  ║
║  │                                                                        │  ║
║  │  Prompt templates (per use case):                                      │  ║
║  │    ├── Email Summary & Action Items                                    │  ║
║  │    ├── Structured Report (Exec Summary, Risks, Actions, Next Steps)    │  ║
║  │    └── Task & Calendar Extraction (JSON output)                        │  ║
║  │                                                                        │  ║
║  │  Response Scrubber:                                                    │  ║
║  │    Regex: vault codes, PAN, credentials, SIN                          │  ║
║  │    SECURITY_SCRUB_EVENT → Prometheus counter + alert (>3 in 5min)     │  ║
║  │                                                                        │  ║
║  │  De-anonymization by clearance level:                                  │  ║
║  │    L1–L2: restore names and dates only                                 │  ║
║  │    L3: restore all except vault codes                                  │  ║
║  │    L4: full restore (authorized users only)                            │  ║
║  │                                                                        │  ║
║  │  ⚠️  MEMORY PURGE: hydrated text = ∅, token_map = ∅ (zero-overwrite)  │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════════════════════╝
                       ║
                       ▼ Final response (safe, scrubbed, de-anonymized)
                    RBC User (via MCP / RBC App)
```

### 9.2 S3 → PVC Sync Architecture

```
╔══════════════════════════════════════════════════════╗
║  BACKGROUND SYNC DAEMON (Kubernetes CronJob)         ║
║  Schedule: every 15 minutes                          ║
║                                                      ║
║  1. Scan S3 for files modified since last sync       ║
║     (use S3 object ETag + last-modified timestamp)   ║
║                                                      ║
║  2. For each changed file:                           ║
║     a. Download to temp path on PVC shard            ║
║     b. Atomic rename: temp → live path               ║
║        (prevents partial file reads by workers)      ║
║     c. Update shard manifest (JSON index)            ║
║                                                      ║
║  3. On sync failure: log SYNC_FAILURE_EVENT          ║
║     → alert if > 2 consecutive failures             ║
║     → workers continue reading stale PVC file        ║
║       (acceptable: max 15-min stale window)          ║
║                                                      ║
║  Active query conflict resolution:                   ║
║  → Workers open SQLite in WAL mode (read-only)       ║
║  → Atomic rename is safe: new fd opened post-rename  ║
║  → In-flight queries finish on old file descriptor   ║
╚══════════════════════════════════════════════════════╝
```

### 9.3 EWS Request Queue — Preventing Throttling at 70K Users

```
╔══════════════════════════════════════════════════════════════════════╗
║  EWS RATE LIMITING PROBLEM AT SCALE                                  ║
║                                                                      ║
║  Scenario: 1% peak concurrency = 700 simultaneous users             ║
║  Each user triggers JIT: fetch up to 30 email bodies               ║
║  Worst case: 700 × 30 = 21,000 simultaneous EWS GetItem calls       ║
║  Exchange throttling threshold: typically 20 concurrent per tenant  ║
║  → Without mitigation: complete EWS collapse                        ║
║                                                                      ║
║  MITIGATION ARCHITECTURE:                                            ║
║                                                                      ║
║  Per OCP Pod:                                                        ║
║    EWS Request Queue: max 20 concurrent JIT fetches                 ║
║    Overflow: queue with 5s wait, then degrade gracefully            ║
║                                                                      ║
║  Across all pods (cluster-wide):                                     ║
║    Token bucket: 500 EWS calls/minute shared across all pods        ║
║    Distributed rate limiter: Redis-backed token bucket              ║
║                                                                      ║
║  Degraded mode (circuit breaker open):                              ║
║    Skip JIT Hydration                                               ║
║    Return metadata-only response:                                   ║
║      "Found N relevant emails: [subject, sender, date]              ║
║       Full content unavailable — Exchange temporarily unavailable"  ║
║    Log: EWS_DEGRADED_MODE_EVENT                                     ║
╚══════════════════════════════════════════════════════════════════════╝
```

### 9.4 JIT Hydration Memory Lifecycle

```
query received → HybridRetriever → chunk_ids only (no text)
                                         │
                               EWS Request Queue
                               (bounded, back-pressure)
                                         │
                               EWSHydrationClient
                               batch GetItem via EWS
                                         │
                               EphemeralCache
                               (heap, 5-min TTL, swappiness=0)
                                         │ raw email bodies (strings in heap)
                               AnonymizationGateway
                               NER pass → token_map in RAM
                                         │ anonymized text only
                               CrossEncoderReranker
                               score(query, anonymized_text)
                                         │ top-N chunk scores
                               Ollama LLM
                               generation (anonymized context)
                                         │ raw response
                               ResponseScrubber
                               + De-anonymizer (clearance-aware)
                                         │
                               ⚠️  MEMORY PURGE
                               hydrated text = ∅
                               token_map = ∅
                                         │
                               response to user
```

---

## 10. Production Capacity Model

> This section is **required** for ARB approval at 70K user scale. Estimates must be validated with load testing before production cut-over.

### 10.1 SQLite Storage Sizing

| Metric | Estimate | Basis |
|---|---|---|
| Emails per user (average) | 50,000 | Industry average for knowledge workers |
| Chunks per email (average) | 3 | 512-token chunks, typical email length |
| Dense vector size per chunk | ~3KB | 768 float32 values |
| SPLADE tokens per chunk (avg non-zero) | ~200 rows × 8 bytes | Typical SPLADE sparsity |
| Metadata per chunk | ~500 bytes | JSON: subject, sender, date, IDs |
| **SQLite file size per user** | **~75–100MB** | Dense + SPLADE + FTS overhead |
| **Total S3 storage (70K users)** | **~5–7TB** | At 75–100MB per user |
| **Total PVC storage (70K users)** | **~5–7TB** | Same files, warm cache |
| PVC shard size (10 shards × 7K users) | **~500–700GB per PVC** | Must size accordingly |

> ⚠️ **ARB Action Required:** PVC storage request must be submitted. Recommend provisioning 1TB per shard (10 × 1TB = 10TB total PVC) to allow 40% growth headroom.

### 10.2 GPU Compute Sizing

| Operation | GPU Cost | Peak Load (1% concurrency = 700 users) |
|---|---|---|
| Query embedding (dense, per variant) | ~5ms per embed | 700 × 6 = 4,200 embed ops/min |
| SPLADE query encoding (per variant) | ~15ms per encode | 700 × 6 = 4,200 encode ops/min |
| Cross-Encoder reranking (30 candidates) | ~80ms per query | 700 × 80ms = 56 GPU-seconds/min |
| Ollama LLM generation | ~1,500ms per query | 700 × 1.5s = 1,050 GPU-seconds/min |
| **Total GPU demand at peak** | | **~18–20 A100-equivalent GPU-minutes/peak-minute** |

> ⚠️ **ARB Action Required:** GPU node sizing must be approved. Recommend minimum 8× A100 (or equivalent) with horizontal pod autoscaler. Query enrichment toggleable to 2-variant mode if GPU utilization exceeds 80%.

### 10.3 EWS Capacity Requirements

| Metric | Value |
|---|---|
| Peak concurrent users | 700 (1% of 70K) |
| EWS calls per user at peak | Up to 30 (Top-30 JIT fetches) |
| **Peak EWS call rate (worst case)** | **21,000 concurrent calls** |
| Recommended cluster-wide rate limit | 500 calls/minute (token bucket) |
| Expected JIT latency with queue | P95: 300–500ms |
| Degraded mode trigger | 3 consecutive EWS failures |

### 10.4 PVC IOPS Requirements

| Metric | Value |
|---|---|
| SQLite reads per query per user | ~50–100 random reads (ANN + SPLADE JOIN) |
| Concurrent users peak | 700 |
| **Peak IOPS demand** | **35,000–70,000 IOPS** |
| Recommended per-PVC IOPS provisioning | 8,000–10,000 IOPS (across 10 PVCs) |
| Storage class recommendation | SSD-backed, not NFS (NFS cannot sustain random IOPS at this rate) |

> ⚠️ **Critical:** Do NOT use NFS-backed PVCs for SQLite. NFS latency for random SQLite reads will cause P99 latency spikes. **Require SSD-backed block storage (OCP block PVCs).**

---

## 11. Consequences

### Positive Consequences

- **Absolute privacy compliance:** No email text ever persists to any storage medium. SQLite files contain only vectors, tokens, and metadata.
- **Elimination of cold starts:** PVC warm cache reduces initial retrieval from S3 network latency (2–5s) to local SSD reads (<10ms).
- **Highest retrieval accuracy (~96%):** SPLADE + Dense + Metadata FTS + Cross-Encoder provides the most precise results available without storing email text.
- **Natural user isolation:** Per-user SQLite files make cross-user data leakage structurally impossible — there is no shared database to misconfigure.
- **Graceful degradation:** EWS circuit breaker + metadata-only fallback ensures the system remains useful during Exchange outages, returning subject/sender/date context without LLM generation.
- **Extensible to other data sources:** Slack, SharePoint, Teams can be added as new ingestion paths writing to the same per-user SQLite format.
- **S3 as durable backup:** All embedding work is preserved in S3; a PVC failure results in stale data, not data loss. Rebuild from S3 is always possible.

### Negative Consequences

- **High infrastructure complexity:** The sync daemon, PVC sharding, EWS queue, NER gateway, and cross-encoder form a multi-component pipeline requiring careful orchestration, monitoring, and failure recovery.
- **Significant GPU footprint:** 6-variant LLM enrichment + Cross-Encoder + Ollama generation requires dedicated GPU nodes at RBC scale.
- **SPLADE at scale:** SQL JOIN-based sparse scoring must be benchmarked at 50K+ emails per user. If performance is inadequate, consider time-windowing the SPLADE index (last 6–12 months) as a mitigation.
- **15-minute data freshness lag:** New emails arrive in Exchange immediately but appear in the RAG index only after the next S3 sync + PVC sync cycle (~15–30 minutes total lag). This is acceptable for the assistant use case but must be communicated to users.
- **HyDE quality risk:** Hypothetical document generation may miss RBC-specific terminology. Monitor HyDE's contribution to RRF scores; disable if it degrades precision.

---

## 12. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation | Residual Risk |
|---|---|---|---|---|
| **EWS rate limiting collapse** — 700 concurrent JIT fetches overwhelm Exchange | High at peak | Critical | Bounded EWS queue per pod (max 20 concurrent); cluster-wide Redis token bucket (500 calls/min); circuit breaker → metadata-only degraded mode | Medium |
| **PVC IOPS saturation** — SQLite random reads overwhelm network storage | High if NFS used | High | Use SSD-backed block PVCs only; shard across 10 PVCs; workers read-only (no write contention) | Low (with SSD) |
| **Embedding inversion attack** — stored vectors reconstructed to reveal L3/L4 text | Medium | Critical | Gaussian noise injection (sigma 0.01–0.05) before S3/PVC write; accept 2–4% recall loss | Low |
| **Cross-user data leakage** | Very Low (per-file isolation) | Critical | Per-user SQLite files — structural isolation; no shared DB to misconfigure | Very Low |
| **Hydrated text surviving in memory** — text not purged post-generation | Low | High | Explicit zero-overwrite on cache eviction; `swappiness=0`; memory safety integration test in CI | Low |
| **SQLite file corruption during sync** — partial write during atomic rename | Low | High | Atomic rename pattern; workers open read-only fd; SQLite WAL mode; S3 always available for rebuild | Very Low |
| **SPLADE JOIN performance at 200K+ emails** | High (future growth) | Medium | Time-window index (last 12 months); periodic token pruning; benchmark at 50K and 200K corpus sizes | Medium |
| **S3 sync daemon failure** — PVC becomes increasingly stale | Medium | Medium | Alert on >2 consecutive sync failures; workers fall back to S3 direct read; PVC becomes cold cache only | Low |
| **GPU node unavailability** — query enrichment unavailable | Medium | Medium | Feature flag: reduce to 2-variant mode (dense + sparse only); no cross-encoder; direct LLM; maintain basic RAG | Low |
| **HyDE generating misleading synthetic documents** | Medium | Medium | Monitor HyDE RRF contribution score; feature flag to disable HyDE independently of other variants | Medium |
| **LLM generating responses implying masked credentials** | Low | High | Output scrubbing regex on every response; SECURITY_SCRUB_EVENT alert >3 in 5 minutes; red-team testing quarterly | Low |
| **Kubernetes pod swap spilling hydrated text to disk** | Low | Critical | `swappiness=0` enforced in pod spec; validated in deployment pipeline | Very Low |

---

## 13. Implementation Phases

This ADR defines the **target state specification**. The codebase is to be built or migrated using this document as the authoritative reference.

### Phase 1 — Foundation: Security, Schema & Storage (Sprint 1–2)

**Goal:** Establish all security controls and storage infrastructure before any RAG capability is built. Security cannot be retrofitted.

| Deliverable | Description |
|---|---|
| Per-user SQLite schema | `embeddings`, `splade_tokens`, `metadata_fts` tables + migration script |
| S3 integration | Write per-user SQLite file to S3 after each ingestion run |
| PVC shard provisioning | 10 SSD-backed block PVCs, read-only mount for workers |
| Background sync daemon | CronJob: S3 → PVC, every 15 min, atomic rename, WAL mode |
| Gaussian noise injector | sigma configurable 0.01–0.05; unit test: cosine similarity ≥ 0.95 |
| No-storage audit | Scan all code paths for email text persistence; remediate all findings |
| Pre-commit CI hook | Block SQL INSERT with body/content/text columns |
| SECURITY.md | Document all security controls implemented in this phase |

### Phase 2 — Dual-Encoder Retrieval Pipeline (Sprint 3–4)

**Goal:** Working hybrid retrieval with all three search paths, validated benchmarks, and S3/PVC integration.

| Deliverable | Description |
|---|---|
| PersonalDataIngestor | Chunk → dense embed → SPLADE embed → Gaussian noise → SQLite → S3 → text purge (idempotent) |
| HybridRetriever | Parallel dense ANN + SPLADE SQL JOIN + Metadata FTS → RRF → returns `{chunk_id, message_id, score}` only |
| MetadataExtractor | Project ID regex, ticket number extraction, sender normalization |
| PVC cache loader | On query: check PVC → if miss, fall back to S3 direct |
| Benchmark suite | Recall@10, P50/P95/P99 latency at 10K and 50K email corpus; SQLite file size per user |
| Updated ADR matrix | Replace estimated latencies with measured values |

### Phase 3 — JIT Hydration + NER Anonymization (Sprint 5–6)

**Goal:** Safe cross-encoder reranking pipeline; no text persisted beyond the query window.

| Deliverable | Description |
|---|---|
| EWSHydrationClient | Batch GetItem, connection pool (5 conn), circuit breaker (3 failures → 60s open), OAuth refresh, degraded mode |
| EWS Request Queue | Bounded concurrency (max 20/pod), Redis token bucket (500/min cluster-wide) |
| EphemeralHydrationCache | 5-min TTL, LRU 50 entries, secure zero-overwrite wipe, context manager API |
| AnonymizationGateway | spaCy NER + custom patterns (credentials, vault codes, PAN, SIN); token_map lifecycle |
| CrossEncoderReranker | `ms-marco-MiniLM-L-6-v2`, batch scoring, text purge post-scoring |
| Memory safety test | CI: verify no hydrated text survives in heap after generation |

### Phase 4 — LLM Generation + Output Safety (Sprint 7–8)

**Goal:** Structured, safe LLM generation with clearance-level-aware de-anonymization.

| Deliverable | Description |
|---|---|
| Prompt template library | YAML templates: Email Summary, Structured Report, Task/Calendar Extraction |
| OllamaClient | Streaming, 30s timeout, no prompt/response logging, feature flag for variant count |
| ResponseScrubber | Regex-based credential/PAN/vault detection, `SECURITY_SCRUB_EVENT` counter + alert |
| De-anonymization engine | Clearance-level rules (L1–L4); token_map purge after de-anonymize |
| E2E pipeline test | Full latency profiling: embed → retrieve → hydrate → rerank → generate |

### Phase 5 — Observability, Load Testing & ARB Sign-off (Sprint 9–10)

**Goal:** Production-ready system passing all performance and security targets; ARB package complete.

| Deliverable | Description |
|---|---|
| OpenTelemetry instrumentation | Spans per stage; no PII in attributes; Jaeger export |
| Prometheus metrics | Query duration, EWS latency, cache hit/miss, IOPS pressure, scrub events, partition violations |
| Grafana dashboard | P50/P95/P99 per stage, pipeline success rate, EWS availability, sync lag |
| Load test | Locust/k6: 700 concurrent users, 10 min; targets: P99 < 3s, EWS hydration < 600ms, error rate < 0.1% |
| Security test suite | Cross-user isolation, vault code scrubbing, no-disk-persistence assertion, memory safety |
| ARB package | Security Attestation, Benchmark Results (vs. ADR estimates), Gap Closure Report, Risk Register |

---

## 14. Revision History

| Version | Date | Author | Summary of Changes |
|---|---|---|---|
| 1.0 | March 2, 2026 | AI Platform Team | Initial ADR: Options 1–5, comparison matrix, empty Decision and Consequences sections |
| 2.0 | March 2026 | AI Platform Team | Critical corrections: JIT Hydration made explicit in Option 3; Relational SPLADE schema; Option 4 formally rejected; new sections: embedding inversion, user partitioning, NER gateway, output scrubbing; Decision section populated; Option 5 merged into Option 3 |
| 3.0 | March 2026 | AI Platform Team | **Production-scale revision for 70,000 users.** PostgreSQL removed; SQLite per-user confirmed as target. S3 as source of truth with PVC warm cache architecture adopted. Background sync daemon specified. PVC sharding strategy added (10 shards × 7K users, SSD block only). EWS Request Queue and Redis token bucket added to prevent Exchange throttling. Cold start fallback via S3 defined. Three new decision drivers: Scalability, Operational Observability, Cost/GPU Footprint. Production capacity model added (Section 10): storage sizing (5–7TB), GPU sizing (8× A100+), EWS capacity (500 calls/min), PVC IOPS (SSD mandatory). All seven gaps from AI Agent initial review addressed. |

---

> **Next Steps for ARB:**
> 1. ARB review and approval of this ADR (v3.0)
> 2. Security team sign-off on: Gaussian noise sigma selection, NER pattern coverage for L4 data, output scrubbing regex completeness
> 3. Infrastructure team approval of: 10 × 1TB SSD block PVCs, GPU node allocation (8× A100), EWS API rate limit agreement with Exchange team
> 4. EWS benchmark in target environment to replace estimated latencies with measured values
> 5. Phase 1 implementation commences upon ARB approval

---

*© 2026 Royal Bank of Canada — RBC AI Platform Team — CONFIDENTIAL INTERNAL USE ONLY*
