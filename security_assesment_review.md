1. MCP Server Security Audit

Security review this MCP server.

Service: mcp
Transport: stdio (local) + SSE (remote, if enabled)
Auth context: RBC internal, JWT RS256 session propagated from API gateway

Focus areas:
- Confused deputy analysis: trace every tool call's auth chain from 
  client identity → tool execution → downstream resource (EWS, Drive, Calendar)
- Tool allowlist enforcement: verify no tool is callable outside declared 
  role-based allowlist
- Input validation: check all tool input schemas for injection vectors 
  (prompt injection via document content, path traversal via file refs)
- Blast radius per tool: what is the maximum damage if this tool is called 
  with a malicious payload?
- MCP Reqs compliance: flag any deviation from P1-P6 principles

Output: findings ranked by Impact x Likelihood, one finding per issue, 
OWASP + MITRE ATLAS tags, controls implemented, remediation priority.

2. Ingestion Service Security Audit
Security review this ingestion service.

Service: PG Intelligence ingestion pipeline
Sources: EWS (Exchange email), Google Calendar MCP, Google Drive MCP
Pipeline stages: Embed (Cohere v4) → Dense Search → Metadata/Lexical → 
                 RRF Fusion → Hydration → Reranking
Vector store: self-hosted MongoDB Enterprise (Atlas Search blocked by RBC DBaaS GEN2)
Fallback: PostgreSQL + pgvector + ParadeDB

Focus areas:
- Trust boundary validation: every document enters from an external source — 
  verify sanitization before it touches the vector store
- Folder-aware ingestion: EmailRecord must carry source_folder metadata; 
  BCC fields must only surface when source_folder == sent AND user is sender
- Prompt injection via ingested content: can a malicious email body 
  influence downstream LLM behavior through the RAG pipeline?
- Idempotency and dedup: can the same document be ingested twice and 
  cause data integrity issues?
- PII handling: are emails/calendar events classified for sensitivity 
  before embedding?
- Audit trail: is there a per-record log of what was ingested, when, 
  and from which source folder?

Output: findings ranked by Impact x Likelihood, OWASP LLM Top 10 tags, 
P1-P6 principle violations flagged, remediation steps scoped to pipeline stage.

3. S3-to-PVC Sync Service Security Audit

Security review this sync service.

Service: S3-to-PVC file sync
Behavior: polls S3 every 60s, compares ETags, downloads changed/new files 
          to PVC, skips if no change
Deployment context: Kubernetes pod with PVC mount, S3 credentials 
                    injected via environment or secret

Focus areas:
- Supply chain / path traversal: can a malicious S3 object key 
  escape the PVC mount path via directory traversal (e.g. ../../etc/)?
- ETag integrity: is the ETag comparison sufficient, or can an 
  adversary with S3 write access swap file content while preserving ETag?
- Credential exposure: how are S3 credentials managed? 
  Are they rotated? Scoped to least privilege (read-only on target prefix)?
- Write atomicity: if a download is interrupted mid-write, can a 
  partial file corrupt the PVC state seen by the ingestion service?
- Denial of service: can an attacker flood S3 with new objects to 
  trigger continuous large downloads and exhaust PVC or network bandwidth?
- Logging: is there an audit log of every file written, skipped, 
  or failed, with ETag and timestamp?

Output: findings ranked by Impact x Likelihood, controls implemented, 
Semgrep rule suggestions for path traversal and credential leak patterns.
