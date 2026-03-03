# Enterprise RAG Caching Strategy

## Decision
We will proceed with a modified **Option 3: Advanced RAG**. The system will utilize per-user SQLite databases storing dense vectors, SPLADE sparse tokens, and metadata (with zero email body text). To meet "Response Speed" drivers, S3 will act as the source of truth, but databases will be proactively synced every 15 minutes to a Kubernetes Persistent Volume Claim (PVC) to serve as a warm local cache for OCP worker pods. Full email body text will exclusively be retrieved via Just-In-Time (JIT) Hydration directly from Exchange Web Services (EWS) into ephemeral RAM for LLM generation, heavily guarded by NER masking.

## Positive Consequences
* **Absolute Privacy Compliance:** By completely eliminating PostgreSQL and local disk storage for email text, we strictly adhere to the Level 2-4 data constraints. The Gaussian noise and NER token mapping in RAM ensure the on-prem Ollama LLM never leaks or persists vault codes or credentials.
* **Elimination of Cold Starts:** The PVC warm cache effectively reduces the initial retrieval latency from seconds (waiting for S3 network I/O) to milliseconds (local disk read). 
* **Uncompromising Accuracy:** The combination of SPLADE for exact keyword matching, dense vectors for semantic intent, and cross-encoder reranking provides the highest possible retrieval precision for complex enterprise queries.

## Negative Consequences
* **High Infrastructure Complexity:** Managing a background sync daemon that effectively orchestrates continuous state synchronization between S3 and a shared PVC across 70,000 user files is non-trivial.
* **High Compute Footprint:** Running 6 concurrent LLM query variants per user request, followed by cross-encoder scoring and an on-prem Ollama generation phase, will require significant GPU provisioning to maintain concurrent throughput at peak hours.

## Risks and Mitigations
* **Risk: EWS API Rate Limiting (The Bottleneck)** Fanning out to fetch the text for the Top-30 chunks dynamically during the JIT Hydration phase creates a massive dependency on the Exchange Server. At 70,000 users, concurrent JIT requests could trigger severe Exchange throttling, collapsing the entire generation pipeline.
  * *Mitigation:* Implement aggressive circuit breakers. If EWS latency spikes or throttles, gracefully degrade the user experience by returning only the high-confidence Metadata FTS results (e.g., Sender, Subject, IDs) and bypass the LLM summary entirely until Exchange recovers.

* **Risk: PVC IOPS Saturation and SQLite Locking** Mounting a single shared ReadWriteMany (RWX) PVC for all OCP workers to concurrently read and write thousands of SQLite databases can overwhelm network storage IOPS and cause database locking errors.
  * *Mitigation:* Ensure the SQLite files are mounted in immutable/read-only mode for the query workers. Only the background sync daemon should have write access. Furthermore, shard the 70,000 users across multiple smaller PVCs (e.g., sharded by alphabetical email prefixes) rather than a single monolithic volume.
