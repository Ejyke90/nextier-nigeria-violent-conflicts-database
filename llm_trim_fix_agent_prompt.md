# Agent Prompt: Two-Threshold Gate Fix

---

## Persona & Mindset

You are a **Principal Software Engineer** specializing in AI/ML pipeline engineering, RAG systems,
and production Python services. You write correct code the first time, you do not over-engineer,
and you do not make changes outside the stated scope. Every line you touch has a reason.

---

## Context: What Broke and Why

The `trim()` function in `llm_trimming_service.py` currently uses a **single threshold gate**:

```
if tokens > CLEAN_THRESHOLD (72K):
    → call _llm_summarize() unconditionally
```

This means a 386K token payload — far beyond what Cohere can process within its time budget —
is handed directly to the LLM HTTP call. The result is a **30-second timeout**, a
`RESPONSE_TOO_LARGE` error propagated upstream, and a fallback to deterministic trim that
should have been the planned path all along.

The deterministic fallback (`_det_manager` with S1–S5) works correctly and produces safe output
(confirmed: 1,969 tokens final, well under the 90K ceiling). The LLM call for oversized payloads
is pure latency cost with no benefit.

### Current (broken) flow:

```
estimate_tokens(text)
  └─ if > CLEAN_THRESHOLD → _llm_summarize(full payload)   ← no upper bound check
       └─ COHERE HTTP CALL (30s timeout on 386K tokens)
            └─ timeout → fall through to _det_manager
```

### Target (correct) flow:

```
estimate_tokens(text)
  ├─ if <= CLEAN_THRESHOLD        → return text as-is
  ├─ if > LLM_TRIM_CEILING        → return _det_manager.trim(text)   ← skip LLM entirely
  └─ else (sweet spot)            → return _llm_summarize(text)
```

---

## Your Task

Implement the two-threshold gate described above. Nothing more, nothing less.

---

## Implementation Specification

### 1. Add the new constant

In the constants block at the top of `llm_trimming_service.py`, add:

```python
LLM_TRIM_CEILING: int = 150_000  # tokens above which LLM trim is skipped; go straight to deterministic
```

Place it **after** `CLEAN_THRESHOLD` and **before** `SOFT_CEILING` to preserve logical ordering.
Use the same style as existing constants (type-annotated, inline comment explaining the unit and intent).

### 2. Modify `trim()` — add the upper bound check

Locate the conditional block inside `trim()` that checks `estimate_tokens(text)` against
`CLEAN_THRESHOLD`. Insert the new upper bound check **immediately after** the existing
`CLEAN_THRESHOLD` check and **before** the `_llm_summarize()` call:

```python
tokens = estimate_tokens(text)

if tokens <= CLEAN_THRESHOLD:
    return text

if tokens > LLM_TRIM_CEILING:
    logger.info(
        "[TRIM] Payload too large for LLM trim (tokens=%d > LLM_TRIM_CEILING=%d). "
        "Routing directly to deterministic trim.",
        tokens,
        LLM_TRIM_CEILING,
    )
    return _det_manager.trim(text)

return _llm_summarize(text)
```

**Constraints:**
- Use the existing `logger` instance — do not introduce a new one.
- Use `len(text) // 4` for token estimation — consistent with the rest of the file. Do not
  import or call any model-based tokenizer.
- Do not modify `_llm_summarize()`, `_det_manager`, or any S1–S5 strategy internals.
- Do not change the function signature of `trim()`.

### 3. Log format consistency

The log line must follow the existing `[TRIM_*]` prefix convention already used in this file
so that OCP log filters and dashboards pick it up correctly. Use `[TRIM]` as the prefix
(not `[TRIM_LLM_SKIP]` or any other variant) unless the file already defines a more specific
prefix for routing decisions — in that case, match it exactly.

---

## Tests

Create or extend the test file for `llm_trimming_service.py`. If a test file already exists
(e.g. `tests/test_llm_trimming_service.py`), add the new cases to it. If not, create it.

Write the following test cases using `pytest`. Use `unittest.mock.patch` for all external
dependencies (`_llm_summarize`, `_det_manager`, `logger`). Do not make real HTTP calls or
instantiate real Cohere clients in tests.

---

### Test cases (all required)

#### TC-1: Below `CLEAN_THRESHOLD` — no trim, no external call

```python
def test_trim_clean_text_returns_as_is(monkeypatch):
    """Text under 72K tokens must be returned unchanged without calling LLM or det manager."""
    short_text = "a" * (72_000 * 4 - 4)  # just under threshold using len//4 estimation
    with patch("llm_trimming_service._llm_summarize") as mock_llm, \
         patch.object(_det_manager, "trim") as mock_det:
        result = trim(short_text)
    assert result == short_text
    mock_llm.assert_not_called()
    mock_det.assert_not_called()
```

#### TC-2: Above `LLM_TRIM_CEILING` — deterministic path, no LLM call

```python
def test_trim_oversized_payload_routes_to_deterministic(monkeypatch):
    """Payload over 150K tokens must skip LLM and go straight to deterministic trim."""
    large_text = "a" * (150_001 * 4)  # just over LLM_TRIM_CEILING
    expected = "deterministic_result"
    with patch("llm_trimming_service._llm_summarize") as mock_llm, \
         patch.object(_det_manager, "trim", return_value=expected) as mock_det:
        result = trim(large_text)
    assert result == expected
    mock_llm.assert_not_called()
    mock_det.assert_called_once_with(large_text)
```

#### TC-3: In the sweet spot — LLM path taken

```python
def test_trim_sweet_spot_calls_llm_summarize():
    """Payload between CLEAN_THRESHOLD and LLM_TRIM_CEILING must call _llm_summarize."""
    mid_text = "a" * (100_000 * 4)  # 100K tokens — between 72K and 150K
    expected = "llm_trimmed_result"
    with patch("llm_trimming_service._llm_summarize", return_value=expected) as mock_llm, \
         patch.object(_det_manager, "trim") as mock_det:
        result = trim(mid_text)
    assert result == expected
    mock_llm.assert_called_once()
    mock_det.assert_not_called()
```

#### TC-4: Exact boundary — `LLM_TRIM_CEILING` value itself routes to LLM

```python
def test_trim_at_exact_ceiling_uses_llm():
    """Text at exactly LLM_TRIM_CEILING tokens must still use LLM (boundary is exclusive)."""
    boundary_text = "a" * (150_000 * 4)  # exactly 150K tokens
    with patch("llm_trimming_service._llm_summarize", return_value="ok") as mock_llm, \
         patch.object(_det_manager, "trim") as mock_det:
        trim(boundary_text)
    mock_llm.assert_called_once()
    mock_det.assert_not_called()
```

#### TC-5: Log is emitted on deterministic routing

```python
def test_trim_oversized_logs_routing_decision(caplog):
    """A routing log must be emitted when the deterministic path is taken due to size."""
    import logging
    large_text = "a" * (200_000 * 4)
    with patch("llm_trimming_service._llm_summarize"), \
         patch.object(_det_manager, "trim", return_value="x"), \
         caplog.at_level(logging.INFO, logger="llm_trimming_service"):
        trim(large_text)
    assert "[TRIM]" in caplog.text
    assert "LLM_TRIM_CEILING" in caplog.text
```

---

## Acceptance Criteria

Before marking this done, verify:

- [ ] `LLM_TRIM_CEILING = 150_000` is defined as a module-level constant with a type annotation
- [ ] `trim()` returns early to `_det_manager.trim()` for any payload where `len(text) // 4 > 150_000`
- [ ] `_llm_summarize()` is **never called** when the payload exceeds `LLM_TRIM_CEILING`
- [ ] All 5 test cases pass with `pytest -v`
- [ ] No existing tests are broken
- [ ] No changes made outside `llm_trimming_service.py` and its test file
- [ ] Token estimation uses only `len(text) // 4` — no SDK imports, no model calls

---

## Out of Scope — Do Not Touch

- `response_size_manager.py` — the parsing fix is already shipped
- `_det_manager` internals (S1–S5 strategies)
- `_llm_summarize()` implementation
- `MCP_DET_TOP_K` or any configuration values
- Any other file in the pipeline not named above

---

## Threshold Tuning Note (for the record, not for implementation)

`LLM_TRIM_CEILING = 150_000` is the initial value. It should be tuned based on observed Cohere
p95 latency at different payload sizes under production load. The constant is intentionally
externalized so it can be moved to environment config in a follow-up if needed. Do not
implement that follow-up now.
