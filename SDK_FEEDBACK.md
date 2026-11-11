# Building Blocks Tested and What We Learned

RulesMinion was built against OpenMinion `0.1.20` on Python 3.13, using Gemini `gemini-flash-lite-latest` through the OpenAI-compatible Gemini endpoint configured as the `openai` provider (`api_key_env=GEMINI_API_KEY`, `base_url=https://generativelanguage.googleapis.com/v1beta/openai/`). We did not have Cortensor Portal or Gemma4 access.

This note is the hackathon's required "Building Blocks Tested" and "What We Learned" write-up.

## Building blocks tested

| Block | How we used it | Result |
| --- | --- | --- |
| Agent execution | `Agent(...)` as a context manager, then `agent.run(...)` | Works when the first step is a forced tool call |
| Models | Gemini Flash Lite via the OpenAI-compatible adapter | Works for tool use + JSON; weak at emitting OpenMinion's `task_update` sidecar |
| Tools | `@tool` on `fetch_hackathon_page` and `recall_previous_snapshot` | Works. `min_scope="READ_ONLY"` plus `idempotent=True` avoided approval prompts |
| Structured output | `output_type=HackathonBrief` (Pydantic) | Works **only** when combined with `forced_tools`. Parses JSON even when wrapped in `openminion:` prose and a markdown fence |
| Permissions / action policy | Default `action_policy.mode=auto` with `default_action=require_confirm` | Read-only tools ran without a prompt. We still passed an `approval_callback` that allowlists our two tools in case a write or unknown tool appears |
| Sessions | `session_id="rulesminion-<urlhash>-<unix>"` | Sessions persist (we saw leftover rows in `.openminion/state/openminion.db`). We mint a **new** session id per check to avoid the task-context failure below |
| Memory | Left enabled in the default runtime (`memory_enabled: true`) | The runtime built a memory envelope on our turns (`memory_context_reason=built`). We did not rely on it; snapshots are our durable memory |
| Tasks / task context | Implicit — OpenMinion injects `task_update` into the entry tool | **Broke** text-only and structured-output-only runs on Gemini |
| Diagnostics | `result.metadata` (`tool_calls_count`, `respond_kind`, `elapsed_ms`, `llm_call_counts_by_purpose`) and `openminion doctor` | Useful once you know to look there. A failed "ping" still reported `run_state=completed` |
| Skills, delegation, Portal, Gemma4 | Not used | Out of scope for this agent |

## What we actually shipped

The path that survived contact with Gemini is slightly different from the first design:

1. RulesMinion fetches the page in process (so a 4,000-character tool-result clip or a failed forced `fetch_hackathon_page` cannot starve the model).
2. The Agent still has to make a tool call, because a text-only or `output_type`-only turn dies on the task-context clarify below. We force a tiny `mark_digest_ready` tool and also register `fetch_hackathon_page`.
3. We parse JSON out of `result.text` (often prefixed with `openminion:` and a markdown fence). A smoke test showed `output_type=HackathonBrief` *does* work when paired with a forced tool; the shipped loop keeps the text parser as a safety net and retries a JSON-only rewrite if the first reply is prose.
4. Repeat checks mint a fresh `session_id`. Snapshot diffs compare material fields (pool, prize place+amount, IST deadlines, India flag, checklist) so a paraphrase of `eligibility_summary` is not reported as a page change.
5. Free-tier Gemini returned HTTP 429 on a fourth extract in one sitting. `_run_agent` now retries rate limits with a short backoff.


## What worked

1. The public Python API matches the examples in `examples/sdk/`. `from openminion import Agent, tool, ProviderError, AgentOutputValidationError` is the right import surface (it is lazy; `dir(openminion)` right after import does not list these names).
2. Reproducing `examples/sdk/tool_agent.py` succeeded on the first try: forced `lookup_order`, Gemini answered "Order A-104 is currently ready." (~30s).
3. Combining a forced tool with `output_type` produced a valid Pydantic object. The model replied with fenced JSON prefixed `openminion:`; OpenMinion still validated it.
4. Marking tools `READ_ONLY` and `idempotent` kept the default confirm-on-write policy out of the way. That is the right default for a fetch tool.
5. JSON-LD and DoraHacks `__NUXT_DATA__` are sitting in the HTML. Feeding those to the model (with IST already computed) made deadline extraction much more reliable than hoping the LLM parses "2026/12/19 07:59" plus a tiny "(UTC)" label.

## What broke

### 1. Text-only `Agent.run()` fails on Gemini with a task-context clarify

**Environment:** OpenMinion 0.1.20, `gemini-flash-lite-latest`, fresh `session_id`.

**Steps:**

```python
from openminion import Agent

with Agent(
    config_path=".openminion/agents.json",
    agent_id="openminion",
    instructions="Reply with exactly the single word pong and nothing else.",
    session_id="rulesminion-smoke",
) as agent:
    result = agent.run("ping", timeout_seconds=120)
print(result.text)
```

**Expected:** a model reply, ideally `pong`.

**Actual:** `run_state=completed`, `result.text` =

```
openminion: I could not safely update the task conditions. Please restate the current task and its required conditions.
```

Metadata from that turn: `tool_calls_count=0`, `llm_calls_count=1`, purpose `entry` only, `model=brain-orchestrator`, `respond_kind=assistant`, about 10.8k tokens used for the word "ping".

The same canned message is returned for `output_type=SomeModel` with no tools, and then `AgentOutputValidationError` fires because that sentence is not valid schema JSON.

**Why (from reading the runtime):** `openminion/modules/brain/loop/context/task_entry.py` requires a valid `task_update` sidecar on the entry tool in several cases. If the model returns plain text (or a malformed `task_update`), `resolve_entry_task_update` raises `ValueError` and the user sees the clarify string above. A first tool-using turn can skip this because the tool call gives the runtime something to attach `task_update` to — or because `forced_tools` changes the entry path.

**Workaround we shipped:** always pass `tools=[...]` and `forced_tools=["fetch_hackathon_page"]`, and use a fresh `session_id` per check. Do not reuse a session for a later, unrelated prompt if you need the run to succeed on Gemini.

**Suggested product fix:** if the model returns plain text on a brand-new session with no `task_update`, fall back to the documented compatibility path (verbatim objective) instead of failing the turn. Surface `reason_code=invalid_task_context_update` in `result.text` less often; it currently masquerades as a successful assistant message.

### 2. Default tool results are truncated at 4,000 characters

`runtime.agent_loop_tool_result_max_chars` defaults to `4000`. A cleaned Cortensor DoraHacks page is ~8k characters; the detailed prize tiers and the official submission checklist sit after that cutoff. We raised the local value to `20,000` and also put structured metadata *first* in the digest.

**Suggestion:** document this limit next to `@tool`, or raise the default for read-only fetch tools. Silently clipping a tool result is a quiet accuracy bug.

### 3. `result.text` is console-rendered

Successful answers arrive as `openminion: …`. That is fine for a terminal, easy to miss when you parse `result.text` yourself. Prefer `result.output` when `output_type` is set. We still keep a JSON-repair helper for the fenced-prose case.

### 4. Config and process surprises

- Gemini is configured as provider id `openai` plus a `gemini` model connection. It works, but `doctor` output saying `provider=openai` / `model=brain-orchestrator` is confusing when the actual network call is Gemini.
- `daemon_auto_start: true` and `process_mode: "daemon"` mean the first `Agent()` can take several seconds while local state databases come up. Subsequent calls in the same process are faster; each full extract still took ~30–90s.
- Default `gateway.api_turn_timeout_seconds` is 45 and `chat_turn_timeout_seconds` is 90. A structured extract regularly exceeded 45s. We passed `timeout_seconds=180` into `Agent.run` and raised the local config values.
- `import openminion` followed by `dir(openminion)` does not show `Agent` or `tool` until first attribute access. Harmless, but it looks like the package exported nothing.

### 5. Default action policy will pause write tools

`default_action=require_confirm` is correct for a desktop agent and a trap for a headless one. A `save_snapshot` write tool would have stopped the run with a policy prompt (`respond_kind=policy_confirmation_prompt` in the SDK docs). We kept writes in application code and left the fetch tool read-only. If you need the model to write, pass `approval_callback` or set `action_policy.mode=bypass` on that agent only.

## What we learned (actionable)

1. **Treat `forced_tools` as part of the Gemini compatibility story**, not just a demo trick. A Getting Started note that says "if `Agent.run` returns the task-conditions clarify, add a real tool or force one" would have saved an hour.
2. **Publish a first-class Gemini setup path** that does not rename the provider to `openai`. `openminion setup --list-providers` already mentions Gemini; the saved config should keep `provider_identity.service_vendor=gemini` in status output.
3. **Put tool-result size and turn timeouts in the SDK README.** Both defaults are too tight for "fetch a page and extract JSON".
4. **Do not count a clarify-as-assistant reply as a successful extract.** `run_state=completed` plus a canned question burned a Gemini call and looked like application error until we grepped the runtime.
5. **Snapshot memory belonged in the application.** OpenMinion sessions are a poor store for "what did this URL look like yesterday" because reusing the session can trip task-context updates. A JSON file per URL is boring and correct.
6. **Page fetch should not be left entirely to the model.** DoraHacks embeds a useful record (`timelineEnd`, `venueForm`, `mandatoryGitRepoLink`) that a 20-line parser can IST-convert before the LLM ever sees it. The model should interpret eligibility language, not arithmetic.

## Bonus-report status

The task-context failure looks like a real Gemini + entry-tool incompatibility, not a RulesMinion bug. We have not opened a GitHub issue or a fix PR — this repo is still private and local, and the hackathon bonus requires waiting for acknowledgement before a fix PR. If this project is published, the next step is to file the reproduction above against OpenMinion with version `0.1.20` and this environment note.

No security issues found. API keys stay in `.env`; fetch refuses private networks.
