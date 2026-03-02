Yes, this is absolutely possible. In fact, this exact workflow—contextualizing an issue, analyzing the codebase, and breaking down the implementation into atomic, spec-driven steps—is the sweet spot for modern agentic coding platforms.

To get the best results from an AI agent, you need to provide a highly structured prompt that constraints its behavior, establishes strict engineering standards, and clearly defines the expected output format. Agents perform best when instructions are modular and separated into clear sections.

Here is the ideal, battle-tested prompt structure to achieve this. You can drop this into an advanced coding assistant (like Cursor, GitHub Copilot Workspace, or a custom agentic platform) along with the relevant context.

---

### The Ideal Agent Prompt

```markdown
**Role & Objective**
You are an expert Principal Software Engineer. Your task is to analyze an attached Jira ticket, review the existing codebase context, and design a detailed, end-to-end implementation plan. 

**Core Engineering Constraints (STRICTLY ENFORCED)**
1. **Spec-Driven Development:** We strictly follow an API-first/Open Spec methodology. Any changes to interfaces, endpoints, or data models MUST be defined in the OpenAPI/AsyncAPI specification first before any business logic is written.
2. **Atomic Commits:** I require small, incremental, and highly focused commits. Each step in your plan must represent a single, testable, and independent logical change. Do not bundle multiple concerns into one step.
3. **End-to-End Completeness:** Your review and plan must span the entire stack affected by the ticket (e.g., spec -> database migrations -> backend logic -> API layer -> frontend integration -> tests).

**Input Data**
* **Jira Ticket:** [Insert/Attach Jira Ticket text or link here]
* **Target Codebase/Directory:** [Insert context or let the agent read the workspace]
* **Current Open Spec:** [Attach existing OpenAPI/Swagger file if applicable]

**Execution Steps**

**Phase 1: Codebase Review & Impact Analysis**
Review the provided context and map out the exact files, functions, and specs that need modification.
* Identify the root cause or the exact insertion points for the new feature.
* List any potential side-effects or breaking changes this ticket might introduce.

**Phase 2: The Implementation Plan**
Provide a step-by-step implementation plan. Format each step as a standalone, actionable task that I can execute (or you can execute) in a single small commit.

Use the following format for your plan:

* **Step 1: [Update Spec/Contract]**
    * **Action:** (e.g., Add new `POST /v1/resource` endpoint to `openapi.yaml`)
    * **Files Affected:** `...`
    * **Acceptance Criteria:** Spec validates successfully.
* **Step 2: [Scaffolding / Data Layer]**
    * **Action:** (e.g., Generate database migration or update DTOs based on the spec)
    * **Files Affected:** `...`
* **Step N: [Business Logic / Integration / Tests]**
    * **Action:** ...

**Output Requirements**
Do not write the actual code yet. First, output the Impact Analysis and the Step-by-Step Implementation Plan for my review. Once I approve the plan, we will execute it step by step.

```

---

### Why this specific structure works:

1. **Prevents the "Big Bang" PR:** By explicitly demanding "Atomic Commits" and a step-by-step plan, you prevent the agent from trying to generate 500 lines of code across 12 files in a single, unreviewable chunk.
2. **Enforces Spec-First Architecture:** AI agents are notorious for drifting from the API contract if they start writing business logic first. Forcing the agent to update the OpenAPI spec in "Step 1" anchors the rest of the generated code to a strict contract.
3. **Approval Gate:** The instruction *"Do not write the actual code yet"* is crucial. It forces the agent to act as an architect first. You get to review the blueprint, correct any misunderstandings of the Jira ticket, and then prompt it to "Execute Step 1."

### Is this even possible today?

Yes. If you are using an agent with codebase-wide visibility (like Cursor with its `@codebase` feature, Devin, or a custom RAG-enabled agentic platform), it can parse the Jira ticket, search the repository for the relevant domains, and construct this exact plan.

The main limitation you will run into is the **context window limit** and the agent's ability to accurately find all cross-file dependencies. To mitigate this, it helps to point the agent to the specific directory or core files related to the ticket rather than making it search a massive monorepo entirely blind.

Would you like to paste a specific Jira ticket in here so we can run a mock analysis and see what kind of implementation plan it generates?
