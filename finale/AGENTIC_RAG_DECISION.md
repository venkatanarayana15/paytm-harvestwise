# Agentic Reasoning Decision — CoT / ReAct / RAG Graph for HarvestWise

## Question
Should the copilot use Chain-of-Thought (CoT), ReAct, or a full agentic RAG graph?

## Answer (senior-dev, 20y)

### Appendix: what each technique actually buys

| Technique | What it does | Cost | When it helps here |
|-----------|--------------|------|--------------------|
| **CoT** | LLM emits step-by-step reasoning before the answer. | +tokens, +latency, more hallucination surface. | Only when the answer requires multi-step synthesis over already-fetched observations. |
| **ReAct** | Loop: Thought → Action (tool) → Observation → repeat. | Multiple LLM calls, tool orchestration. | When the agent must CHOOSE which tools to call. |
| **Agentic RAG graph** | Route → Retrieve (Cognee) → Grade → Generate → Ground → Learn, with bounded retry. | Retrieval latency (Cognee measured 12.3s), graph build cost. | When answers must be grounded in long-term memory, not just live engine data. |

### Measured facts about THIS codebase (evidence, not opinion)

- **Deterministic engine owns every quantity** (doctrine 08, `engine/restock.py`). The LLM is explicitly forbidden from originating numbers; `llm.py::_grounded` rejects any Tamil ask that drops a quantity. This is the correct source of truth for a money-moving copilot.
- **Sarvam fast model ≈ 0.3–1.0s, clean JSON. Deep reasoning model ≈ 32.5s + 10k reasoning chars** (measured 2026-09-18, `engine/llm.py` header). A 30s pause is dead air in a live pitch.
- **Cognee recall ≈ 12.3s** (`engine/cognee_client.py` header). Putting it on the hot path would destroy the low-latency requirement.
- **Current copilot already IS a ReAct loop**, just without an LLM in the loop: Observe (message) → Think (rules intent + Sarvam P1 fast) → Act (engine.recommendation / dispatch_order) → Observe (stock movement) → Learn (memory + Cognee). Formalizing it as a graph adds structure, not capability.

### Decision

**Adopt a bounded hybrid: deterministic-picker + async RAG + one-shot CoT only for `why`**

1. **Deterministic-picker (default, 90% of traffic)**: rules intent → engine quantities → deterministic Tamil template. Zero LLM latency. The LLM "commits" (proposes a warm sentence via P3) but Python "decides" (grounding gate discards it if any qty missing). This is the `all-agentic-architectures` pattern and it is the right one for a kirana copilot where a dropped coriander bunch means a wrong approval.

2. **Async RAG (every turn, off hot path)**: every merchant message is `remember_async(add_text→cognify)` (graph grows — "more Cognee knowledge"). A background thread `recall`s the query and warms `_COGNEE_CTX_CACHE` (5-min TTL). The NEXT turn reads the cache ( <1ms). No reply ever blocks on 12s recall. This satisfies "more Cognee knowledge + low latency" simultaneously. Exposed at `GET /cognee/context`.

3. **One-shot CoT/ReAct (only for `why` / growth advice)**: `engine/llm.py::reason()` already implements a ReAct-style prompt: ENGINE OUTPUT (single source of truth) + OBSERVATIONS (already fetched) → JSON {reasoning, memory_note, needs_human_review}. It runs on the **deep model only when the judge presses "Reason"** (opt-in, narrated wait), otherwise on the fast model (~1s). Bounded retry = max 1, never loops. This is where CoT is feasible: the observations are pre-fetched, so the LLM cannot hallucinate new tool calls.

### What we DO NOT do

- No multi-agent (measurable gain = zero for a single-merchant copilot; cost = 3×).
- No LLM-generated tool calls in the hot loop (the engine is the only tool that can move money).
- No RAG on the hot path (would violate the low-latency requirement the user explicitly set).

### Verification plan

- `GET /cognee/context?phone=...` shows the cache the copilot actually sees.
- `POST /cognee/remember` + `POST /cognee/recall` prove the graph is live.
- `/llm/diag` shows which model made the last call and whether the grounding gate fired.

### One-line sign-off

Decision: deterministic-picker + async RAG + one-shot CoT for why.  
Evidence: `engine/llm.py:9-22` (timings), `engine/cognee_client.py:9` (12.3s recall), `api/main.py:_grounded` (gate).  
Verification: `GET /cognee/context`, `GET /llm/diag`, latency badge in UI.  
Next action: keep the hot path deterministic; let the graph learn in the background.
