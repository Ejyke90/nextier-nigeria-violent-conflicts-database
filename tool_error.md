this is a much more elegant pattern. Instead of pre-emptive compression, you're building a self-healing retry loop — the model gets told exactly how to fix its own overbudget call and retries with corrected parameters. That's a tighter, more elegant architecture.
Here's the Windsurf prompt for this specific pattern:

You are a senior Python engineer working on an MCP email assistant.
Your task is to implement a self-healing retry mechanism for tool calls
that exceed the context budget. Follow steps in order. Audit before coding.

---

## THE PATTERN (implement exactly this flow)

1. LLM calls get_emails(action="browse", limit=200)
2. Service returns raw result (could be 150K tokens)
3. ResponseSizeManager.trim() reduces it (e.g. to ~95K tokens)
4. _raise_if_over_budget() checks trimmed size against ceiling (94.5K)
5. If over: raise ToolError with EXACT retry instructions for the LLM
6. LLM retries with corrected parameters (lower limit + narrowed date range)
7. Fits within budget → success

The ToolError message IS the self-healing signal. It must be specific,
not generic. The LLM needs to know exactly what to change.

---

## STEP 1 — AUDIT FIRST

Before writing any code:
1. Find where get_emails(), get_calendar() return their results
2. Find where tool errors are raised and how the LLM receives them
3. Find if ResponseSizeManager or similar already exists — if so, extend it
4. Find the current budget ceiling constants
5. Show me findings before proceeding to Step 2

---

## STEP 2 — BUILD ResponseSizeManager

Create or extend `response_size_manager.py`:

```python
class ResponseSizeManager:
    CHARS_PER_TOKEN = 4
    CEILING_TOKENS = 94_500  # leave headroom under 95K

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // ResponseSizeManager.CHARS_PER_TOKEN

    @staticmethod
    def trim(raw: str, max_tokens: int = 94_500) -> str:
        """
        Trim raw tool result to fit within max_tokens.
        Preserve structure: trim from oldest/least relevant entries first.
        Append footer: [TRIMMED: showing {k} of {n} items]
        """
        # implement here

    @staticmethod
    def _raise_if_over_budget(trimmed: str, original_limit: int,
                               start_date: str | None = None) -> None:
        """
        After trimming, if still over budget, raise ToolError with
        precise retry instructions. Never raise a vague error.
        """
        tokens = ResponseSizeManager.estimate_tokens(trimmed)
        if tokens > ResponseSizeManager.CEILING_TOKENS:
            new_limit = int(original_limit * 0.33)  # suggest 1/3 of original
            msg = (
                f"Result too large ({tokens:,} tokens, ceiling {ResponseSizeManager.CEILING_TOKENS:,}). "
                f"Retry with: limit={new_limit}"
            )
            if start_date:
                msg += f'; narrow the date range (current start_date="{start_date}")'
            else:
                msg += '; add start_date to narrow the date range'
            raise ToolError(msg)
```

---

## STEP 3 — INJECT INTO TOOL HANDLERS

For get_emails() and get_calendar():

1. After fetching raw results, call ResponseSizeManager.trim(raw)
2. Then call ResponseSizeManager._raise_if_over_budget(
       trimmed, original_limit, start_date
   )
3. If no error raised, return trimmed result normally

The method signature the LLM sees must include:
- `limit: int` — number of items to fetch
- `start_date: str | None` — ISO date string e.g. "2026-05-28"

These are the two levers the LLM uses on retry.

---

## STEP 4 — RETRY GUIDANCE IN THE SYSTEM PROMPT

Add this block to the system prompt template (near tool usage instructions):

Self-Healing Tool Calls
If a tool raises a ToolError containing "Retry with:", follow the
instructions exactly:

Adjust limit to the suggested value
Add or narrow start_date to reduce the date range
Use similarity_threshold and top_k if available to filter results
Never retry with the same parameters that caused the error
On second failure, report to the user: what was requested,
what the constraint is, and ask them to narrow the query

---

## STEP 5 — EXAMPLE FLOW TO VALIDATE

Manually trace this scenario and confirm each step fires correctly:

User: "Summarize the last 2 days by PR category"

→ LLM calls: get_emails(action="browse", limit=200)
→ trim() reduces 150K → ~95K tokens
→ _raise_if_over_budget() detects 95K > 94.5K ceiling
→ ToolError: "Retry with: limit=66; narrow the date range"
→ LLM retries: get_emails(action="browse", limit=66, start_date="2026-05-28")
→ trim() → fits within budget → success

Write a unit test that mocks get_emails to return a 150K char blob,
assert that ToolError is raised with "limit=66" in the message,
then assert the second call with limit=66 succeeds.

---

## STEP 6 — EDGE CASES TO HANDLE

1. What if limit=1 still overflows? (single email is massive)
   → Raise ToolError: "Single item exceeds budget. Ask user to be more specific."

2. What if no start_date can narrow further? (query is already 1 day)
   → Raise ToolError: "Date range at minimum. Try limit=1 or ask user to
     specify a sender or subject keyword."

3. What if the LLM retries more than 2 times?
   → Track retry_count in tool context. On 3rd attempt, raise a hard stop.

---

## OUTPUT AFTER EACH STEP

- Files created or modified
- The exact ToolError message format used
- Any changes to tool schemas the LLM sees
- Confirm the system prompt block was added

Do not proceed past Step 1 until you show me the audit findings.

The key insight your screenshot captures that makes this superior to pre-emptive compression: the error message is the instruction. The LLM doesn't need a separate planner — the ToolError string is the retry plan. That's a tight feedback loop with zero extra infrastructure.
