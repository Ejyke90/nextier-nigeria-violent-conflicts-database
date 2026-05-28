"""
context_manager.py

Pure deterministic context management middleware. Model-agnostic.
No API calls. No model calls. No HTTP clients. No external dependencies.

Flow:
  1. call check() before sending — if too large, it logs + raises immediately.
     The call never reaches the model.
  2. Agent catches ContextTooLargeError and retries.
  3. On retry, call shrink() — returns a lean payload + healing prompt.
     Inject healing_prompt as the system message and send.

Usage:
    from context_manager import ContextManager, ContextTooLargeError

    mgr = ContextManager(safe_ceiling=136_000)

    try:
        mgr.check(messages)
        your_client.call(messages)
    except ContextTooLargeError:
        result = mgr.shrink(messages, query="summarise my emails")
        your_client.call(
            [{"role": "system", "content": result.healing_prompt}, *result.messages],
            max_tokens=result.max_tokens,
        )
"""

import json
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Claude Haiku 4.5 hard limits ─────────────────────────────────────────────
# Source: https://platform.claude.com/docs/en/about-claude/models/overview
HAIKU_4_5_CONTEXT_WINDOW = 200_000
HAIKU_4_5_MAX_OUTPUT     = 64_000

# Benchmark: the least safe input Haiku 4.5 can receive without crowding
# out its own output. Any payload above this triggers a warning + fail.
SAFE_INPUT_CEILING = HAIKU_4_5_CONTEXT_WINDOW - HAIKU_4_5_MAX_OUTPUT  # 136_000

WARNING_THRESHOLD  = int(SAFE_INPUT_CEILING * 0.85)  # warn at 85% — ~115_600
RETRY_MAX_TOKENS   = 1_000                           # tight output budget on retry


# ── Token estimation — no API call ───────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """1 token ≈ 4 characters. len // 4, no external call."""
    return len(text) // 4


def estimate_tokens_messages(messages: list[dict]) -> int:
    return estimate_tokens(json.dumps(messages))


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DateRange:
    start: str
    end: str

    @property
    def label(self) -> str:
        return f"{self.start} → {self.end}"


@dataclass
class ContextOverflowError(Exception):
    original_tokens: int
    compressed_tokens: int
    included_dates: Optional[DateRange]
    excluded_dates: list[DateRange]
    suggestion: str

    def __str__(self) -> str:
        inc = self.included_dates.label if self.included_dates else "none"
        exc = ", ".join(d.label for d in self.excluded_dates) or "none"
        return (
            f"\n[HAIKU CONTEXT OVERFLOW — unrecoverable]\n"
            f"  Original  : {self.original_tokens:,} tokens\n"
            f"  Compressed: {self.compressed_tokens:,} tokens\n"
            f"  Safe limit: {SAFE_INPUT_CEILING:,} tokens\n"
            f"  Dates kept   : {inc}\n"
            f"  Dates dropped: {exc}\n"
            f"  Suggestion: {self.suggestion}\n"
        )


@dataclass
class PrepareResult:
    messages: list[dict]
    needs_retry: bool
    healing_prompt: str
    max_tokens: int
    estimated_tokens: int
    included_dates: Optional[DateRange]
    excluded_dates: list[DateRange] = field(default_factory=list)
    strategies_applied: list[str]  = field(default_factory=list)


# ── Deterministic shrink strategies ──────────────────────────────────────────

def _parse_date(msg: dict) -> Optional[datetime]:
    """Read optional ISO date from msg['metadata']['date']. No model call."""
    try:
        return datetime.fromisoformat(msg["metadata"]["date"])
    except (KeyError, ValueError, TypeError):
        return None


def _date_window(
    messages: list[dict],
    recent_days: int = 7,
) -> tuple[list[dict], list[dict], Optional[DateRange], list[DateRange]]:
    """
    Keep messages within the most-recent `recent_days`.
    Messages without a date are always kept.
    Returns (kept, dropped, included_range, excluded_ranges).
    """
    cutoff = datetime.utcnow() - timedelta(days=recent_days)
    kept, dropped = [], []

    for msg in messages:
        dt = _parse_date(msg)
        if dt is None or dt >= cutoff:
            kept.append(msg)
        else:
            dropped.append(msg)

    kept_dates    = [d for m in kept    if (d := _parse_date(m))]
    dropped_dates = [d for m in dropped if (d := _parse_date(m))]

    included = DateRange(
        start=min(kept_dates).date().isoformat(),
        end=max(kept_dates).date().isoformat(),
    ) if kept_dates else None

    excluded = [DateRange(
        start=min(dropped_dates).date().isoformat(),
        end=max(dropped_dates).date().isoformat(),
    )] if dropped_dates else []

    return kept, dropped, included, excluded


def _keyword_score(text: str, query_terms: set[str]) -> float:
    """
    Jaccard-style keyword overlap. Fully deterministic — no embeddings,
    no model, no API. Good enough for top-k filtering at this scale.
    """
    if not query_terms:
        return 1.0
    words = set(text.lower().split())
    if not words:
        return 0.0
    return len(query_terms & words) / len(query_terms | words)


def _top_k_filter(
    messages: list[dict],
    query: str,
    top_k: int = 20,
    similarity_threshold: float = 0.72,
) -> list[dict]:
    """
    Keep the top-k messages most relevant to the query by keyword overlap.
    Messages without scorable content are kept unconditionally.
    """
    query_terms = set(query.lower().split())

    scored = []
    for msg in messages:
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content)
        score = _keyword_score(content, query_terms)
        scored.append((score, msg))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        msg for score, msg in scored[:top_k]
        if score >= similarity_threshold or not query_terms
    ]


def _sliding_window(
    messages: list[dict],
    verbatim_turns: int = 5,
) -> list[dict]:
    """
    Keep the most-recent `verbatim_turns` messages verbatim.
    Older messages are each trimmed to a 120-char snippet and
    collapsed into one synthetic system message.
    No model call — pure string manipulation.
    """
    if len(messages) <= verbatim_turns:
        return messages

    older  = messages[:-verbatim_turns]
    recent = messages[-verbatim_turns:]

    snippets = []
    for m in older:
        role    = m.get("role", "?")
        content = m.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content)
        snippets.append(f"[{role}]: {content[:120].replace(chr(10), ' ')}…")

    collapsed = {
        "role": "system",
        "content": (
            "PRIOR CONTEXT (collapsed to save tokens):\n" +
            "\n".join(snippets)
        ),
    }
    return [collapsed] + recent


def _get_latest_user_query(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            return content if isinstance(content, str) else json.dumps(content)
    return ""


# ── Healing prompt builder ────────────────────────────────────────────────────

def _build_healing_prompt(
    original_tokens: int,
    retry_tokens: int,
    included: Optional[DateRange],
    excluded: list[DateRange],
    dropped_count: int,
    strategies: list[str],
) -> str:
    """
    Pure string construction. Tells the model on retry exactly what happened,
    what data was trimmed, and how to keep its own output compact.
    No API call. No model call.
    """
    inc_str = included.label if included else "all available data"
    exc_str = ", ".join(d.label for d in excluded) or "none"

    return f"""
[RETRY CONTEXT — read before responding]

This is a retry. The previous attempt exceeded the Haiku context window.

TOKEN AUDIT (estimated via len // 4):
  Original payload : {original_tokens:,} tokens
  This payload     : {retry_tokens:,} tokens
  Safe ceiling     : {SAFE_INPUT_CEILING:,} tokens

DATA SCOPE:
  Dates included   : {inc_str}
  Dates excluded   : {exc_str}
  Items dropped    : {dropped_count}
  Strategies used  : {', '.join(strategies)}

IMPORTANT — tell the user:
  - Which dates are included in this response
  - Which dates were excluded and why (oldest-first truncation)

RESPONSE RULES (mandatory on retry):
  - Maximum output: {RETRY_MAX_TOKENS} tokens
  - Use bullet points, not prose paragraphs
  - Do not reproduce full email or event bodies — summarise in one line each
  - If the user asks about excluded dates, say explicitly those dates are
    outside your current context window
  - Lead with the answer, not with preamble
""".strip()


# ── Main interface ────────────────────────────────────────────────────────────

class HaikuContextManager:
    """
    Pure deterministic middleware. Owns zero model or API calls.
    Call .prepare() before every Haiku request.
    Plug the result into your own model client.
    """

    def __init__(
        self,
        # Default = Haiku 4.5 safe input ceiling (most conservative baseline).
        # The manager never trims unless the payload exceeds THIS number,
        # so larger models simply never trigger the shrink path.
        #
        # Override safe_ceiling per model:
        #   Claude Haiku 4.5   → 136_000  (200K ctx − 64K output)   ← default
        #   Claude Sonnet 4.5  → 136_000  (200K ctx − 64K output)
        #   Claude Sonnet 4.6  → 936_000  (1M ctx  − 64K output)
        #   Claude Opus 4.7    → 872_000  (1M ctx  − 128K output)
        #   Cohere Command A   → 252_000  (256K ctx − 4K output)
        #   Cohere Command A+  →  64_000  (128K input − 64K output)
        safe_ceiling: int       = SAFE_INPUT_CEILING,
        warning_threshold: int  = WARNING_THRESHOLD,
        date_window_days: int   = 7,
        top_k: int              = 20,
        similarity_threshold: float = 0.72,
        verbatim_turns: int     = 5,
        retry_max_tokens: int   = RETRY_MAX_TOKENS,
    ):
        self.safe_ceiling         = safe_ceiling
        self.warning_threshold    = warning_threshold
        self.date_window_days     = date_window_days
        self.top_k                = top_k
        self.similarity_threshold = similarity_threshold
        self.verbatim_turns       = verbatim_turns
        self.retry_max_tokens     = retry_max_tokens

    def prepare(self, messages: list[dict], query: str = "") -> PrepareResult:
        """
        Estimates tokens, warns if needed, shrinks if needed.
        Returns a PrepareResult the caller uses to drive the model call.
        Raises ContextOverflowError if unrecoverable after all strategies.
        """
        original_tokens = estimate_tokens_messages(messages)
        char_size       = len(json.dumps(messages))
        q               = query or _get_latest_user_query(messages)

        # ── Happy path ────────────────────────────────────────────────────
        if original_tokens <= self.warning_threshold:
            logger.info(
                "[CONTEXT_OK] tokens=%d chars=%d pct=%.1f%%",
                original_tokens, char_size,
                original_tokens / self.safe_ceiling * 100,
            )
            return PrepareResult(
                messages=messages,
                needs_retry=False,
                healing_prompt="",
                max_tokens=HAIKU_4_5_MAX_OUTPUT,
                estimated_tokens=original_tokens,
                included_dates=None,
            )

        # ── Warning log ───────────────────────────────────────────────────
        logger.warning(
            "[CONTEXT_WARNING] tokens=%d chars=%d pct=%.1f%% overflow=%d — shrinking",
            original_tokens, char_size,
            original_tokens / self.safe_ceiling * 100,
            max(0, original_tokens - self.safe_ceiling),
        )

        # ── Strategy 1: date window ───────────────────────────────────────
        working, dropped_msgs, included, excluded = _date_window(
            messages, recent_days=self.date_window_days
        )
        dropped_count = len(dropped_msgs)
        strategies    = ["date_window"]

        # ── Strategy 2: top-k keyword filter ─────────────────────────────
        working    = _top_k_filter(working, q, self.top_k, self.similarity_threshold)
        strategies.append("top_k_keyword")

        # ── Strategy 3: sliding window collapse ───────────────────────────
        working    = _sliding_window(working, self.verbatim_turns)
        strategies.append("sliding_window")

        retry_tokens = estimate_tokens_messages(working)

        logger.warning(
            "[CONTEXT_SHRUNK] original=%d retry=%d dropped_items=%d "
            "included=%s excluded=%s strategies=%s",
            original_tokens, retry_tokens, dropped_count,
            included.label if included else "N/A",
            [d.label for d in excluded],
            strategies,
        )

        # ── Unrecoverable ─────────────────────────────────────────────────
        if retry_tokens > self.safe_ceiling:
            raise ContextOverflowError(
                original_tokens=original_tokens,
                compressed_tokens=retry_tokens,
                included_dates=included,
                excluded_dates=excluded,
                suggestion=(
                    "Switch to a model with a larger context window (e.g. Sonnet 4.6 "
                    "at 1M tokens), or apply a stricter date_window_days."
                ),
            )

        # ── Retry payload ready ───────────────────────────────────────────
        healing = _build_healing_prompt(
            original_tokens=original_tokens,
            retry_tokens=retry_tokens,
            included=included,
            excluded=excluded,
            dropped_count=dropped_count,
            strategies=strategies,
        )

        return PrepareResult(
            messages=working,
            needs_retry=True,
            healing_prompt=healing,
            max_tokens=self.retry_max_tokens,
            estimated_tokens=retry_tokens,
            included_dates=included,
            excluded_dates=excluded,
            strategies_applied=strategies,
        )


# ── Example (no model call — just shows the prepare contract) ─────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    mgr = HaikuContextManager()

    messages = [
        {
            "role": "user",
            "content": "Summarise my emails from the last two weeks.",
            "metadata": {"date": "2026-05-28"},
        },
        {
            "role": "user",
            "content": "OOGASHOOGAOOGASHOO " * 6_000,   # simulate bloated email
            "metadata": {"date": "2026-04-01"},
        },
    ]

    try:
        result = mgr.prepare(messages, query="summarise emails")

        if result.needs_retry:
            print("=== RETRY NEEDED ===")
            print(f"Shrunk tokens  : {result.estimated_tokens:,}")
            print(f"Dates included : {result.included_dates.label if result.included_dates else 'N/A'}")
            print(f"Dates excluded : {[d.label for d in result.excluded_dates]}")
            print(f"max_tokens cap : {result.max_tokens}")
            print("\n--- healing_prompt (inject as system message) ---")
            print(result.healing_prompt)
            # caller does:
            # your_client.call(
            #     [{"role": "system", "content": result.healing_prompt}, *result.messages],
            #     max_tokens=result.max_tokens,
            # )
        else:
            print("=== HAPPY PATH — send as-is ===")
            print(f"Tokens: {result.estimated_tokens:,}")

    except ContextOverflowError as e:
        print(e)
