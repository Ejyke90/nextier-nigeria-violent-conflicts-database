# Experiment Plan: Agentic RAG MVP (Evaluate & Refactor)

## 🎯 Objective
Audit and selectively upgrade the existing PoC codebase to meet the secure Retrieval-Augmented Generation (RAG) MVP standards. The system must use a single PostgreSQL database (with `pgvector` and RLS), exposed via an MCP Server, and routed through an API Gateway.

## 🤖 AI Agent Instructions: The Evaluation Loop
For every step below, you MUST execute the following loop:
1. **Read:** Analyze the existing PoC code for that specific component.
2. **Evaluate:** Compare the code strictly against the "Evaluation / Check Criteria".
3. **Decide:** - If the code meets the criteria: **LEAVE AS IS.** Do not modify.
   - If the code fails the criteria: **UPDATE ONLY** the specific functions or lines required to meet the criteria. Log what was changed and why.

---

## 🛠️ Execution Steps & Evaluation Criteria

### Step 1: Database Schema & Security Audit
* **What needs to happen:** Ensure the database is configured to handle both raw data and vector embeddings securely within the same table.
* **Evaluation / Check Criteria:**
  - [ ] Does the SQL initialization script enable the `vector` extension?
  - [ ] Does the target table (e.g., `user_emails`) contain a `user_id` column and an `embedding` column of type `VECTOR`?
  - [ ] Is Row-Level Security (`ENABLE ROW LEVEL SECURITY`) explicitly turned on for the table?
  - [ ] Is there an active RLS Policy enforcing that a session can only `SELECT` rows where the `user_id` matches the session's active user context?

### Step 2: Data Ingestion & Embedding Pipeline
* **What needs to happen:** Verify the script responsible for turning raw emails into database records.
* **Evaluation / Check Criteria:**
  - [ ] Does the ingestion script successfully call an embedding model (e.g., via an API)?
  - [ ] Does the script execute an `INSERT` statement that writes the raw text, the `user_id`, AND the generated vector embedding into the single Postgres table simultaneously?

### Step 3: MCP Server Tool Definition (`search_user_emails`)
* **What needs to happen:** Audit the MCP Server to ensure the database search is correctly exposed as a tool for the Assist App, and that it respects the security boundaries.
* **Evaluation / Check Criteria:**
  - [ ] Is the `search_user_emails` tool schema properly defined so the LLM understands its required inputs (e.g., a search string)?
  - [ ] **CRITICAL:** Before executing the vector similarity search (`ORDER BY embedding <-> ...`), does the MCP tool's database connection explicitly set the Postgres session variable (e.g., `SET app.current_user_id = ...`) using the authenticated user's ID passed from the request?

### Step 4: API Gateway & Context Passing
* **What needs to happen:** Verify that the gateway correctly routes the AI's request and securely passes the user's identity down the chain.
* **Evaluation / Check Criteria:**
  - [ ] Does the API Gateway extract the user identity (e.g., from a JWT or auth token)?
  - [ ] Is that user identity actively forwarded in the payload or headers to the MCP Server so Step 3 can utilize it for the RLS policy?

---

## 🏁 Final Agent Checklist
Before completing the task, the Agent must output a summary detailing:
1. Which files were audited and passed without changes.
2. Which files required modifications and the specific lines updated.
