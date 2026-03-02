#  Personal Grounding Assistant
## ADR-003 · Prompt Engineering Guide
### AI Agent Prompts for Codebase Review, ADR Update & Implementation

---

> **CLASSIFICATION: RESTRICTED — Level 3 Internal. Not for distribution outside the  AI Platform team.**

| Document ID | Status | Owner | Date | Version |
|---|---|---|---|---|
| ADR-003-PROMPTS | Active | AI Platform Team | March 2026 | v1.0 |

---

## Overview & How to Use This Guide

This document provides three sets of expert-level prompts for AI agents (Claude, Copilot, Cursor, or similar) working on the RAG pipeline described in ADR-003. Each prompt is designed to be copy-pasted directly into your AI agent interface.

> 💡 **How to Use:** Copy each prompt block verbatim. Replace `[BRACKETED]` placeholders with your actual values. Run prompts in the order shown — each phase builds on the previous.

| Prompt Set | Purpose | Run When |
|---|---|---|
| Prompt Set 1 | Principal Architect Codebase Review | Before any ADR changes |
| Prompt Set 2 | ADR Update Based on Review | After Set 1 produces findings |
| Prompt Set 3 | Implementation Phases (5 phases) | After ADR is finalized |

---

# PROMPT SET 1 — Principal Architect Codebase Review

---

## 1.1 Context-Setting System Prompt

Paste this as the **system prompt** or at the very start of a new conversation:

```
You are a Principal Software Architect with 20+ years of experience in enterprise financial
systems, specializing in:
- Retrieval-Augmented Generation (RAG) pipelines at scale
- On-premises AI deployments for regulated financial institutions (OSFI, FINTRAC, PCI-DSS)
- Zero-trust security architectures for classified data (equivalent to Government of Canada
  Protected B/C)
- Microsoft Exchange (EWS/Graph API) integration patterns
- Vector database design (SQLite + sqlite-vec, pgvector, Milvus)
- Kubernetes-native microservices on OpenShift

Your review will be presented to 's Architecture Review Board (ARB). You must:
- Be brutally honest. Flag every issue, no matter how small.
- Distinguish between CRITICAL (blocks production), HIGH (degrades quality), and MEDIUM
  (technical debt).
- Cite industry standards and RFCs where applicable.
- Assume this handles data classified at Level 2–4 (sensitive credit data, credentials,
  vault codes).
- The hard constraint is: ZERO raw email text may be persisted to disk at any time.
```

---

## 1.2 Codebase Review Prompt

After setting context, paste this main review prompt with your repo attached or pasted:

```
I am sharing the codebase for the  Personal Grounding Service — a RAG-based email
intelligence system described in ADR-003.

## YOUR TASK
Perform a full Principal Architect review across every layer of the stack. Structure your
review EXACTLY as follows:

## 1. SECURITY AUDIT (Highest Priority)
- Scan for any code path where raw email body text is written to disk, logged, or persisted
  to any store
- Identify any unencrypted secrets, API keys, or EWS credentials in config files or
  environment variables
- Check if embedding inversion attacks are mitigated (is noise/differential privacy applied
  to stored vectors?)
- Verify that user_id partitioning exists on all SQLite queries (no cross-user data leakage)
- Identify any tmpfs / in-memory cache that could spill to swap partitions
- Flag any logging statements that could capture email content

## 2. RAG PIPELINE CORRECTNESS
- Verify the JIT Hydration step: does raw email text exist ONLY in RAM during Cross-Encoder
  scoring?
- Is the Cross-Encoder being called with (query_string, chunk_string)? If chunk_string comes
  from disk, flag it.
- How is SPLADE implemented? Native sparse vectors or relational token table? Show the schema.
- Is RRF fusion happening at chunk level or document level? Show the merge code.
- Is there output filtering AFTER LLM generation to prevent credential leakage in responses?

## 3. ARCHITECTURE & CODE QUALITY
- Does the service decomposition match ADR-003's target architecture diagram?
- Identify any tight coupling between the Grounding Service MCP and the Personal Data Ingestor
- Is the embedding sync idempotent? What happens on partial failure mid-sync?
- Review the OpenShift PVC configuration — is it sized correctly for the embedding volume?

## 4. PERFORMANCE GAPS
- Measure the actual EWS hydration latency in the code. Is there connection pooling?
- Is there a TTL-based ephemeral cache for hydrated email text (target: 5-min TTL in RAM only)?
- What is the estimated query latency end-to-end? Map it to:
  embed -> search -> hydrate -> rerank -> generate

## 5. OBSERVABILITY
- Is there distributed tracing (OpenTelemetry / Jaeger)?
- Are there structured logs with correlation IDs that CAN be enabled without capturing email
  content?
- What SLO metrics are instrumented? P50/P95/P99 query latency?

## 6. GAPS VS ADR-003
List every capability described in ADR-003 that is NOT yet implemented in the codebase.
Format as:
  GAP: [feature name]
  ADR Section: [section reference]
  Impact: [CRITICAL / HIGH / MEDIUM]
  Effort: [estimated days]

## OUTPUT FORMAT
After your analysis, produce:
A) A prioritized findings table: Finding | Severity | File/Component | Recommended Fix
B) A GAP analysis table: ADR Feature | Implementation Status | Risk
C) A "Green Path" narrative: what is correctly implemented and should NOT be changed
```

---

## 1.3 Follow-Up Probes

After the initial review, use these targeted prompts to go deeper:

### 🔬 Follow-Up Probe A — Memory Safety

```
Focus specifically on the ephemeral cache and JIT Hydration memory lifecycle.

Show me every location where hydrated email text is assigned to a variable, object, or buffer.
For each one, trace:
  (1) when it's created
  (2) when it's passed to the Cross-Encoder
  (3) when it's explicitly dereferenced or garbage collected

Is there any scenario where hydrated text survives beyond a single query's generation phase?

Are Python/Node.js objects holding this text eligible for GC immediately after generation, or
are they referenced by closures or async callbacks that could extend their lifetime?
```

### 🔬 Follow-Up Probe B — SPLADE Schema Validation

```
Extract the complete SQLite schema definition from the codebase and show it to me in full.
Then answer:
- Are SPLADE sparse vectors stored as a native vector type, a JSON blob, or a relational token
  table (chunk_id, token_id, weight)?
- If relational: show the SQL query used for sparse retrieval. Is it using a JOIN or a
  subquery? What is the index strategy?
- If native: which sqlite-vec version is used and does it actually support sparse
  (SPLADE-style) indexing?
- What is the cardinality of the sparse token table for a 50,000 email corpus? Is there a
  maintenance job to prune stale vectors?
```

### 🔬 Follow-Up Probe C — EWS Integration Resilience

```
Review the Exchange Web Services (EWS) client code and answer:
- Is there connection pooling or does each JIT hydration request open a new TCP connection?
- What is the retry strategy on EWS failures (exponential backoff, circuit breaker, or none)?
- If EWS is unavailable during a user query, what is the degraded behavior? Does the system
  return an error, fall back to metadata-only response, or hang?
- Is OAuth token refresh handled? What happens if the token expires mid-query?
- Are there any synchronous blocking calls in async code paths that could cause event loop
  starvation?
```

---

# PROMPT SET 2 — Update the ADR Based on Code Review Findings

---

> ⚙️ **Pre-condition:** You must have the output from Prompt Set 1 before running this. Paste both the original ADR content AND the review findings into the same conversation context, then use the prompt below.

```
I am providing you with:
1. The original ADR-003 document (pasted below / attached)
2. The Principal Architect review findings from the codebase analysis

## YOUR TASK
Produce a complete, updated version of ADR-003. Apply ALL of the following changes:

─────────────────────────────────────────────────────────────
MANDATORY CORRECTIONS (from known errors in the original ADR)
─────────────────────────────────────────────────────────────

CORRECTION 1 — JIT Hydration in Option 3:
In the Option 3 RAG Pipeline section, insert an explicit "JIT Hydration" step.
The corrected pipeline MUST read:

  RRF Fusion (yields Vector IDs only, no text)
  -> JIT Hydration: Fetch raw email body for each ID via EWS/Ingestor API (in-memory only)
  -> NER Anonymization Pass: Mask credentials, vault codes, PII before passing to models
  -> Cross-Encoder Reranking (query_string, hydrated_chunk_string) in RAM
  -> LLM Generation with anonymized context
  -> Output Filter: Scrub any credential patterns from generated response
  -> De-anonymize placeholders in response if authorized
  -> Purge all hydrated text from memory

CORRECTION 2 — SQLite SPLADE:
Replace all references to "SQLite with sparse vector support" with "Relational SPLADE on SQLite."
Add this schema definition to the Architecture section for Options 2 and 3:

  CREATE TABLE splade_tokens (
    chunk_id  TEXT    NOT NULL,
    token_id  INTEGER NOT NULL,
    weight    REAL    NOT NULL,
    user_id   TEXT    NOT NULL,
    PRIMARY KEY (chunk_id, token_id)
  );
  CREATE INDEX idx_token_weight ON splade_tokens(token_id, weight DESC);

Add a Cons note: "Requires SQL JOIN-based scoring; benchmark required at 50K+ email scale."

CORRECTION 3 — EWS Fusion Mismatch in Option 4:
Add the following known limitation to Option 4's Cons column:
"EWS returns thread-level results; Vector Search returns chunk-level results. RRF fusion
across granularity levels produces mathematically inconsistent rankings. Requires a
chunk-to-thread normalization pass before fusion, adding 50–150ms latency."

──────────────────────────────
NEW SECTIONS TO ADD
──────────────────────────────

NEW SECTION A — Embedding Inversion Risk:
Add a new sub-section under "Data Security" in Decision Drivers:
Title: "Embedding Inversion Attack Mitigation"
Content: "Dense embedding vectors are not inherently safe. Inversion attacks can reconstruct
source text from stored embeddings with measurable accuracy. REQUIRED: Apply post-hoc
Gaussian noise (sigma=0.01 to 0.05) to all dense embeddings before storage. Accept 2–4%
recall degradation in exchange for protection against Level 3/4 text reconstruction."

NEW SECTION B — User-Level Vector Partitioning:
Add to the Architecture section of Options 2, 3, and 5:
"All SQLite queries MUST include WHERE user_id = :current_user as a mandatory filter. The
embedding sync job must enforce user_id tagging at write time. Cross-user embedding access
is a CRITICAL security violation."

NEW SECTION C — Ephemeral Cache Specification:
Add to Option 3's architecture notes:
"The JIT Hydration cache operates as a 5-minute TTL key-value store in process heap memory
only. Deployment requirements: (1) Kubernetes pod must have swappiness=0, (2) tmpfs mount
for any temp files, (3) explicit memory wipe on cache eviction using language-appropriate
secure deletion."

──────────────────────────────────────
UPDATES TO COMPARISON MATRIX
──────────────────────────────────────

Add two new rows to the Options Comparison Matrix:
  Row: "Embedding Inversion Protection" — all options require DP noise
  Row: "User Partitioning" — all options: Required (user_id filter mandatory)

Flag all latency estimates in the matrix as:
"Estimated — pending EWS benchmark in target environment."

──────────────────────────────
DECISION SECTION
──────────────────────────────

Populate the currently empty "Decision" section with:
"Adopt Option 3 (Advanced RAG) with the following mandatory modifications: Relational SPLADE
schema, explicit JIT Hydration lifecycle, NER Anonymization Gateway, output scrubbing,
user_id partitioning, Gaussian noise on dense embeddings, and Kubernetes swappiness=0.
Metadata FTS (Option 5 elements) to be merged for structured entity matching."

──────────────────────────────
FORMAT REQUIREMENTS
──────────────────────────────

- Maintain the original ADR structure and section numbering
- Mark all new/changed content with a sidebar annotation: [REVISED: March 2026]
- Output the full ADR in Markdown so it can be imported to Confluence
- Add a "Revision History" table at the end
```

---

# PROMPT SET 3 — Implementation Phases

There are **five implementation phases**. Run each prompt at the START of that phase, with the codebase in context. Each prompt produces a specific, testable pull request deliverable.

| Phase | Name | Duration | Key Deliverable |
|---|---|---|---|
| Phase 1 | Foundation & Security Hardening | Sprint 1–2 | Secure SQLite schema, user partitioning, no-storage audit |
| Phase 2 | Relational SPLADE + Dense Dual Encoder | Sprint 3–4 | Working hybrid retrieval, RRF fusion, benchmarks |
| Phase 3 | JIT Hydration + NER Anonymization Layer | Sprint 5–6 | Safe Cross-Encoder reranking pipeline |
| Phase 4 | LLM Generation + Output Scrubbing | Sprint 7–8 | Structured reports, credential scrubbing |
| Phase 5 | Observability, Hardening & ARB Sign-off | Sprint 9–10 | OTel tracing, load tests, ARB presentation |

---

## Phase 1 — Foundation & Security Hardening

```
We are beginning Phase 1 of the RAG pipeline implementation for the  Personal Grounding
Service.

## PHASE 1 GOALS
Establish the secure foundation before any RAG capability is built. Security cannot be
retrofitted.

## TASK 1 — No-Storage Audit & Guardrails
Scan the entire codebase for every location where email content (subject, body, sender)
could be written to:
- SQLite tables (show the CREATE TABLE statements)
- Log files (grep for logger calls that include email fields)
- Kubernetes PVCs (show all file write operations)
- Any caching layer

For each finding: show the file, line number, and provide the corrected code that removes
the persistence.

Then generate a CI/CD pre-commit hook (Python script) that blocks any commit containing a
SQL INSERT with an 'email_body', 'body_text', or 'raw_content' column.

## TASK 2 — SQLite Schema Design
Generate the complete SQLite schema for the no-storage RAG architecture. Include:
- embeddings table: chunk_id (TEXT PK), user_id (TEXT NOT NULL), dense_vector (BLOB),
  created_at (INTEGER), email_metadata (JSON — subject, sender, date, message_id ONLY)
- splade_tokens table: chunk_id (TEXT), user_id (TEXT NOT NULL), token_id (INTEGER),
  weight (REAL), with composite index on (token_id, weight DESC)
- metadata_fts virtual table: FTS5 on subject, sender, extracted_ids, project_names
- Schema migration script (v0 -> v1)
- A schema_audit trigger that raises an error if any column named 'body', 'content',
  or 'text' is added

## TASK 3 — User Partitioning Enforcement
Generate a SQLite middleware class (Python) that:
- Wraps all database connections
- Accepts user_id at initialization
- Automatically appends WHERE user_id = ? to every SELECT query
- Raises UserPartitionViolationError if a query is executed without a WHERE user_id clause
- Logs a WARNING (without email content) if a query touches more than 1000 rows for a
  single user

## TASK 4 — Embedding Inversion Protection
Implement a GaussianNoiseInjector class that:
- Takes a dense embedding vector (numpy array, 768 dimensions)
- Applies Gaussian noise with sigma configurable between 0.01–0.05
- Is called in the embedding pipeline BEFORE any write to SQLite
- Includes a unit test that verifies cosine similarity between original and noised vector
  is >= 0.95 (recall preservation check)

## DELIVERABLE
A pull request containing:
1. Updated SQLite schema with migration script
2. UserPartitionedDB middleware class with tests
3. GaussianNoiseInjector with tests
4. Pre-commit hook for no-storage enforcement
5. SECURITY.md documenting all controls implemented in this phase
```

---

## Phase 2 — Relational SPLADE + Dense Dual-Encoder Retrieval

```
We are beginning Phase 2. Phase 1 security foundation is complete. Now we build the
dual-encoder retrieval layer.

## CONTEXT
- Dense encoder: intfloat/multilingual-e5-base (768 dimensions)
- Sparse encoder: SPLADE-cocondenser-ensemble-distil (30,522-dim vocabulary)
- Storage: SQLite with sqlite-vec for dense, relational token table for sparse
- Hard constraint: SPLADE outputs stored as (chunk_id, token_id, weight) rows —
  NOT as raw sparse arrays

## TASK 1 — Embedding Pipeline
Build a PersonalDataIngestor class that:
1. Accepts a list of email objects: {message_id, subject, sender, date, body_text}
2. Chunks body_text into 512-token overlapping windows (128-token overlap)
3. Generates dense embeddings via the on-prem embedding service (POST /embed)
4. Generates SPLADE sparse vectors via the on-prem SPLADE service
5. Applies GaussianNoiseInjector from Phase 1 to dense embeddings
6. Writes to SQLite via UserPartitionedDB from Phase 1
7. Drops body_text from memory immediately after embedding (set to None, log "text purged")
8. Is idempotent: re-running for the same message_id must be a no-op (upsert by chunk_id)

## TASK 2 — Dual Retrieval + RRF Fusion
Build a HybridRetriever class with a search(query, user_id, k=20) method that:
1. In PARALLEL:
   - Generates dense query embedding and runs ANN search on sqlite-vec (top-k*2 candidates)
   - Generates SPLADE query tokens and runs SQL JOIN on splade_tokens table (top-k*2)
   - Runs FTS5 query on metadata_fts table (top-k candidates)
2. Merges all result lists using Reciprocal Rank Fusion (RRF, k=60)
3. Returns a list of {chunk_id, message_id, rrf_score, metadata} — NO raw text
4. Enforces user_id partitioning on ALL three search paths

## TASK 3 — Benchmarking Suite
Create a benchmark script that:
- Generates a synthetic corpus of 10,000 and 50,000 emails
- Measures: dense-only recall@10, sparse-only recall@10, hybrid recall@10
- Measures: p50/p95/p99 retrieval latency at each corpus size
- Outputs a Markdown table suitable for pasting into ADR-003
- Reports SQLite file size for each corpus size (to validate PVC sizing estimates)

## TASK 4 — Metadata FTS Integration
Build a MetadataExtractor class that:
- Extracts project IDs matching patterns: [A-Z]{2,5}-[0-9]{3,6} (e.g., PROJ-12345)
- Extracts  system IDs, ticket numbers, and employee IDs (configurable regex)
- Writes extracted_ids as a JSON array to the metadata column (NOT email body)

## DELIVERABLE
A pull request containing:
1. PersonalDataIngestor with unit and integration tests
2. HybridRetriever with RRF fusion and all three search paths
3. MetadataExtractor with regex patterns and tests
4. Benchmark suite with results at 10K and 50K email scale
5. Updated ADR-003 Comparison Matrix with real latency numbers
```

---

## Phase 3 — JIT Hydration + NER Anonymization Gateway

```
We are beginning Phase 3. The dual-encoder retrieval (Phase 2) is complete and benchmarked.
Now we add the JIT Hydration and NER Anonymization layers — the most security-sensitive phase.

## CONTEXT
HybridRetriever returns {chunk_id, message_id} pairs. Phase 3 must:
1. Fetch raw email body for top candidates from the EWS/Ingestor API
2. Anonymize sensitive content before passing to any ML model
3. Perform Cross-Encoder reranking in RAM
4. Guarantee text is purged from memory after generation

## TASK 1 — EWS Hydration Client
Build an EWSHydrationClient class that:
- Accepts a list of message_ids and a user OAuth token
- Fetches email bodies from Exchange via EWS GetItem call (batch up to 20 per request)
- Implements connection pooling (max 5 connections, 30s timeout)
- Implements circuit breaker: after 3 consecutive failures, open the circuit for 60s
- Falls back gracefully: if EWS is unavailable, return {message_id: None} so the pipeline
  can proceed with metadata-only
- Handles OAuth token refresh transparently
- NEVER logs email body content — log only: message_id, fetch_duration_ms, status_code

## TASK 2 — Ephemeral Cache
Build an EphemeralHydrationCache with:
- In-process dictionary store (NOT Redis, NOT SQLite — heap memory only)
- 5-minute TTL per entry, enforced via asyncio background task
- Explicit secure_wipe(message_id) method that overwrites the value with zeros before
  deletion
- Maximum 50 concurrent entries (LRU eviction)
- A context manager API:
    async with cache.hydrated(message_id) as text: ...
  that auto-wipes on exit

## TASK 3 — NER Anonymization Gateway
Build an AnonymizationGateway using spaCy (en_core_web_sm) + custom patterns:
- Detect and replace: passwords/credentials ([CREDENTIAL_1], [CREDENTIAL_2] etc.)
- Detect and replace:  vault codes matching pattern VAULT-[A-Z0-9]{8}
- Detect and replace: credit card numbers (PAN masking)
- Detect and replace: SIN/SSN numbers
- Detect and replace: named persons (if classification = Level 4)
- Build a token_map: {placeholder -> original_value} in RAM for de-anonymization
- Implement de_anonymize(response_text, token_map) to restore named entities in response
- token_map must be purged from memory after de-anonymization

## TASK 4 — Cross-Encoder Reranking
Build a CrossEncoderReranker using cross-encoder/ms-marco-MiniLM-L-6-v2:
- Accepts: query (string), hydrated_candidates [(message_id, anonymized_text)]
- Scores each (query, text) pair using the cross-encoder in batch (batch_size=8)
- Returns top-N candidates sorted by score
- Anonymized text is passed directly from AnonymizationGateway — never from disk
- After scoring, text references are set to None

## TASK 5 — Integration Test: Memory Safety
Write an integration test using tracemalloc / objgraph that:
1. Runs a full Hydrate -> Anonymize -> CrossEncode cycle
2. After completion, verifies no Python object in memory contains the original email body
3. Fails the test if any string matching the test email body is found in live objects

## DELIVERABLE
A pull request containing all five components with tests.
CI must pass the memory safety integration test.
```

---

## Phase 4 — LLM Generation, Structured Output & Response Scrubbing

```
We are beginning Phase 4. JIT Hydration and Cross-Encoder reranking (Phase 3) are complete.
Now we integrate the Ollama LLM for generation and add output safety controls.

## TASK 1 — Grounding Service MCP Prompt Templates
Create a PromptTemplateLibrary with these templates (each as a separate YAML file):

Template A — Email Summary & Action Items:
  System: "You are an executive assistant for an  employee. Summarize the provided emails
  concisely. Extract action items as a numbered list. Do not invent information not present
  in the provided context."
  Context injection: <email_context> [ANONYMIZED CHUNKS] </email_context>
  User turn: "{user_query}"

Template B — Structured Report Generation:
  System: "Generate a structured business report in Markdown. Include: Executive Summary,
  Key Findings, Risks, Action Items, Next Steps. Base content strictly on provided context."
  Max tokens: 2048. Temperature: 0.1

Template C — Task & Calendar Extraction:
  System: "Extract all commitments, deadlines, and calendar events from the provided email
  context. Format as JSON: [{title, date_mentioned, priority: HIGH/MED/LOW,
  requires_response: bool}]"
  Parse and validate the JSON output; retry once on parse failure.

## TASK 2 — Ollama LLM Client
Build an OllamaClient that:
- Calls the on-prem Ollama service (configurable base URL)
- Supports streaming responses (yield tokens as they arrive)
- Implements 30s request timeout with graceful cancellation
- Does NOT log the prompt or response body — log only: model_name, token_count, duration_ms
- Accepts a PromptTemplate and a context dict, renders the prompt, returns the completion

## TASK 3 — Output Scrubbing Layer
Build a ResponseScrubber that runs on every LLM response BEFORE it is returned to the user:
- Regex patterns to detect and redact:
  - Passwords (common patterns: "password: xyz", "pwd=xyz", "secret: xyz")
  - Credit card numbers (Luhn-validated 13–19 digit sequences)
  - VAULT-[A-Z0-9]{8} patterns ( vault codes)
  - Any token that matches the AnonymizationGateway placeholder map
- If a sensitive pattern is found: replace with [REDACTED], log a SECURITY_SCRUB_EVENT
  (pattern type only, not value), increment a Prometheus counter
- SECURITY_SCRUB_EVENT must trigger an alert to the security team if count > 3 in 5 minutes

## TASK 4 — De-anonymization Pass
After ResponseScrubber passes, apply de_anonymize() from Phase 3.
Clearance rules:
- Level 1–2 users: restore names and dates; do NOT restore credentials or vault codes
- Level 3 users: restore all except vault codes
- Level 4: full restore (authorized users only)

## TASK 5 — End-to-End Pipeline Test
Write an E2E test that runs the complete pipeline:

  User Query -> Embed -> HybridRetriever -> JIT Hydrate -> Anonymize
  -> CrossEncode -> LLM Generate -> Scrub -> De-anonymize -> User Response

Validate:
- No vault code appears in the response for Level 1–3 users
- Action items are correctly extracted as a list
- Total pipeline latency is measured and logged

## DELIVERABLE
Pull request with all components, YAML templates, and E2E test with latency profiling.
```

---

## Phase 5 — Observability, Load Testing & ARB Sign-off Package

```
We are beginning Phase 5. The full pipeline is functionally complete.
Now we make it production-ready and prepare the Architecture Review Board sign-off package.

## TASK 1 — OpenTelemetry Instrumentation
Instrument the entire pipeline with OpenTelemetry tracing:
- Root span: "grounding.query" with attributes: user_id_hash (NOT plain user_id),
  query_length_chars
- Child spans: embed, hybrid_retrieve, ews_hydrate, anonymize, cross_encode, llm_generate,
  scrub
- Each span: duration, success/failure, error type (if any)
- NEVER include email content, query text, or response text in any span attribute
- Export to Jaeger via OTLP gRPC
- Create a Grafana dashboard JSON with: P50/P95/P99 per span, pipeline success rate,
  SECURITY_SCRUB_EVENT rate

## TASK 2 — Prometheus Metrics
Expose these metrics on /metrics endpoint:
- grounding_query_duration_seconds       (histogram, labels: stage)
- grounding_ews_hydration_latency_ms     (histogram)
- grounding_cache_hit_total              (counter)
- grounding_cache_miss_total             (counter)
- grounding_security_scrub_events_total  (counter, labels: pattern_type)
- grounding_user_partition_violation_total  (counter) — must always be 0
- grounding_memory_purge_failures_total     (counter) — must always be 0

## TASK 3 — Load Test Suite
Using Locust or k6, build a load test that:
- Simulates 50 concurrent  employees querying the system
- Uses a realistic query distribution: 40% email summary, 30% task extraction,
  30% project search
- Runs for 10 minutes and reports:
  - P99 end-to-end latency         (target: < 3 seconds)
  - EWS hydration P99              (target: < 500ms)
  - Cross-encoder P99              (target: < 200ms)
  - LLM generation P99             (target: < 2 seconds)
  - Error rate                     (target: < 0.1%)
- Outputs a Markdown report with pass/fail for each target

## TASK 4 — Security Test Suite
Write automated security tests:
- Test: inject email containing "VAULT-ABC12345" → verify it does NOT appear in any
  response for Level 1–3 users
- Test: query as User A for emails belonging to User B → verify 0 results returned
- Test: simulate EWS returning a response with a credit card number → verify scrubber
  removes it
- Test: check SQLite file on disk for any column containing email body text → must be 0
- Test: check no application log file contains email body text after 10 queries

## TASK 5 — ARB Sign-off Package
Generate the following four documents for the Architecture Review Board:

Document A — Security Attestation (Markdown):
A table with each security control from ADR-003, its implementation status, test evidence,
and sign-off field.

Document B — Benchmark Results (Markdown):
Actual measured latencies from the load test, compared against ADR-003 estimates.
Flag any metric that exceeded the estimate in RED.

Document C — Gap Closure Report (Markdown):
Every gap identified in Phase 1's codebase review, with status:
CLOSED / IN PROGRESS / ACCEPTED RISK.

Document D — Known Risks & Mitigations Register:
Embedding inversion risk, EWS availability dependency, SPLADE SQL JOIN scalability at 200K+.
Each with: likelihood (H/M/L), impact (H/M/L), current mitigation, residual risk rating.

## DELIVERABLE
Pull request with OTel instrumentation, Grafana dashboard, load test suite, security test
suite, and all four ARB documents ready for presentation.
```

---

# Quick Reference — Anti-Patterns & Agent Config

## Prompt Anti-Patterns to Avoid

| ❌ Don't Do This | ✅ Do This Instead | Why |
|---|---|---|
| `"Review my code"` | Use the full structured prompt from 1.2 with all 6 sections | Unstructured prompts get shallow reviews |
| `"Update the ADR"` | Reference the specific correction by number (e.g., "Apply CORRECTION 1") | Vague prompts produce vague edits |
| `"Add security"` | `"Implement GaussianNoiseInjector with sigma=0.01–0.05 and unit test verifying cosine similarity >= 0.95"` | Specific constraints yield testable code |
| Paste entire codebase at once | Use targeted probes (1.3 A/B/C) to focus on specific components | Context overload reduces review quality |
| Run phases out of order | Always complete Phase 1 security controls before Phase 2 retrieval logic | Security cannot be retrofitted into RAG |

## Suggested Agent Configurations

| AI Agent | Recommended Config | Notes |
|---|---|---|
| Claude (claude.ai) | Max context window, Projects feature for codebase | Best for architectural reasoning and code generation |
| Cursor / Windsurf | Composer mode with full repo indexed | Best for inline code edits and PR generation |
| GitHub Copilot | Copilot Chat with workspace context | Good for Phase 2–4 implementation tasks |
| ChatGPT o3 | Code Interpreter + repo upload | Good alternative for benchmark generation (Phase 5) |

---

> ⚠️ **Reminder:** Never paste actual Level 3/4 email content (including real vault codes, credentials, or credit card numbers) into any AI agent prompt, even for testing. Use synthetic test data only.

---

*© 2026 Royal Bank of Canada —  AI Platform Team — CONFIDENTIAL INTERNAL USE ONLY*
