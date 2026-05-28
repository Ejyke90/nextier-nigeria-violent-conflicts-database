# Agent Instructions

## Before you write a single line of code

You must complete the following steps **in order**. Do not skip ahead.

---

### Step 1 — Review the codebase

Read every relevant file in the project. At minimum:

- `context_manager.py`
- Any file that imports or calls `ContextManager`
- Any file that handles model calls (email, calendar, MCP integrations)
- Config or constants files that define model names or limits

---

### Step 2 — Share your implementation plan

Before making any changes, write out your plan in plain language covering:

1. **What you found** — summarise what the existing code does and how `ContextManager` is currently used
2. **What needs to change** — list every file and every function you intend to modify or create
3. **Why** — explain the reason for each change
4. **What you will not touch** — explicitly list files or logic you are leaving alone
5. **Risk** — flag anything that could break existing behaviour

Format it clearly so it can be reviewed at a glance.

---

### Step 3 — Wait for explicit approval

Do not proceed until the user replies with an explicit approval such as:

- "looks good, go ahead"
- "approved"
- "yes, proceed"

A lack of objection is not approval. If the user asks a question or requests a change to the plan, revise and resubmit the plan before proceeding.

---

### Step 4 — Implement exactly the approved plan

Only make the changes that were approved. If you discover something unexpected during implementation that requires a deviation, **stop**, describe what you found, and ask for approval on the deviation before continuing.

---

## Key context for this project

- Token estimation is `len(text) // 4` — no API calls for counting
- The model call is owned by the caller — `ContextManager` never makes HTTP requests
- Default `safe_ceiling` is `136_000` (Haiku 4.5). Other models override this at construction
- The fail-fast path (warn + raise) runs before the model call — the model is never called with an oversized payload on the first attempt
- Shrink strategies run only on retry, in this order: date window → top-k keyword filter → sliding window collapse
