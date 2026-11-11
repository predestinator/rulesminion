# Building Blocks Tested and What We Learned

OpenMinion `0.1.20`, Python 3.13, Gemini `gemini-flash-lite-latest` through the OpenAI-compatible adapter at `https://generativelanguage.googleapis.com/v1beta/openai/`. Credential via `GEMINI_API_KEY` only; nothing secret is checked in.

RulesMinion is a documentation / monitoring style agent: read a hackathon page, extract a typed brief, snapshot it, and say what changed. That is close to the “research brief” and “monitoring agent” ideas in the Hackathon #5 brief.

## Building blocks tested

| Block | How we used it | Result |
| --- | --- | --- |
| Agent execution | `Agent` context manager and `agent.run(..., timeout_seconds=180)` | Works once a first tool call succeeds. |
| Models | Gemini Flash Lite Latest via `providers.openai` + `api_key_env=GEMINI_API_KEY` | Good at extraction when it sees a live digest. Weak at emitting a valid entry `task_update`. |
| Tools | `@tool` on `fetch_hackathon_page`, `recall_previous_snapshot`, `mark_digest_ready` | Decorator and READ_ONLY / idempotent flags work. See tool-forcing bugs below. |
| Permissions | Default `action_policy.mode=auto` with `default_action=require_confirm`; `approval_callback(name, args, reason) -> bool` | READ_ONLY tools do not prompt. We still pass a callback so a future write tool would not hang a headless run. |
| Sessions | Unique `session_id` per check (`rulesminion-{urlhash}-{unix}`) | Sessions persist in the local SQLite store. Reusing a session for a short new prompt was not needed after we switched to unique IDs. |
| Memory | Default `runtime.memory_enabled=true`; we also store our own snapshot files | Smoke-test metadata showed `memory_enabled=true` and an envelope being built. We do not rely on it for diffs. |
| Tasks / task context | Implicit: every entry turn must attach a `task_update` sidecar | This is the main friction. Documented below with reproductions. |
| Freshness / diagnostics | `result.metadata` (`tool_calls_count`, `elapsed_ms`, `llm_call_counts_by_purpose`, `respond_kind`) | Useful. A freshness classifier also blocked one date-heavy turn when no tool had run. |
| Structured output | `output_type=Review` (two strings) vs `output_type=HackathonBrief` (nested lists) | Simple schema plus a working forced tool parsed JSON out of markdown fences. Nested schema plus a failing first tool returned the canned task-update message and raised `AgentOutputValidationError`. We now parse JSON from `result.text` ourselves. |

Portal and Gemma4 were not tested; we do not have that access. Participants without access are not penalized per the official page.

## What worked

1. The public recipe in `examples/sdk/tool_agent.py` works on this setup. `forced_tools=["lookup_order"]` called the tool and returned “Order A-104 is currently ready” in about 30 seconds.

2. `examples/sdk/structured_output.py`’s shape also works if a trivial tool is forced first. With `note_tests` forced and `output_type=Review`, Gemini returned fenced JSON and OpenMinion parsed it (`decision='approve'`). That run took 64 seconds.

3. `@tool(min_scope="READ_ONLY", idempotent=True)` is a clear API. Our fetch function is a normal Python function with a docstring; the SDK exposes it.

4. `AgentRunResult.metadata` is detailed enough to debug a failed turn: `tool_calls_count=0`, `llm_call_counts_by_purpose={"entry":1,"freshness_classify":1,"reflect":1}`, `elapsed_ms`, `brain_status`.

5. Application-owned `APIRuntime` / `config_path` let us pin the project-local `agents.json` without guessing `~/.openminion`.

6. Once a live digest is in the user message and `mark_digest_ready` is forced, Gemini extracts prizes, IST deadlines, India eligibility, and checklists well enough to be useful. Real results:

   - Cortensor on DoraHacks: pool $1,150 USD; 1st–5th $500/$300/$200/$100/$50; submission **2026-12-19 13:29 IST** from `2026/12/19 07:59 UTC`; India yes; five-item official checklist.
   - Learn AR with SPECS: pool $2,500; places $1,250/$750/$500; submission **2026-12-08 03:30 IST** from `Dec 7, 2026 @ 5:00pm EST`; India yes (all countries except standard exceptions).
   - Official docs page: same prize table and the documented submission checklist.

## What did not work

### 1. A plain text `Agent.run()` can fail the task-context protocol

Reproduction:

```python
with Agent(
    config_path=str(AGENTS_JSON),
    agent_id="openminion",
    instructions="Reply with exactly the single word pong and nothing else.",
    session_id="rulesminion-smoke",
) as agent:
    result = agent.run("ping", timeout_seconds=120)
```

Expected (from `docs/task-context.md`): a first non-clarification response may omit `task_update`; the runtime keeps the original input as a verbatim objective.

Actual: `result.text` is

`openminion: I could not safely update the task conditions. Please restate the current task and its required conditions.`

`tool_calls_count` was 0. `llm_calls_count` was 1 (`entry`). `elapsed_ms` was about 30,243. The same canned string is raised from `resolve_entry_task_update` in `openminion/modules/brain/loop/context/task_entry.py` when validation raises `ValueError`.

This was a fresh session, not leftover state. An earlier leftover `t1` session from the official tool example had completed successfully.

### 2. `forced_tools=["fetch_hackathon_page"]` did not invoke the tool

We expected `forced_tools` to make the first step a real HTTP fetch. Across several sessions (short and long instructions, with and without `output_type=HackathonBrief`, alone or next to `recall_previous_snapshot`) the turn ended in 5–27 seconds with `tool_calls_count=0` and the same canned task-update message.

The fetch function itself works when called from Python: it returns a ~10k character digest that already includes `1,150` and `2026-12-19 13:29 IST`.

Trivial forced tools on the same runtime *do* run: `lookup_order`, `note_tests`, and `mark_digest_ready`. So this is not “Gemini cannot call tools.” It looks like the entry/orchestrator step sometimes fails `task_update` validation *before* the forced user tool is executed, and that failure is not retried.

A later date-heavy turn without a live tool result also returned a freshness refusal:

`I couldn't provide a grounded current general answer because Missing live-data evidence for a freshness-sensitive answer.; Missing exact-date evidence for an exact-date freshness answer.`

That is reasonable policy *if* no page was fetched. It is a dead end when `forced_tools` did not run.

### 3. Nested `output_type` plus a failed first tool raises `AgentOutputValidationError`

`output_type=HackathonBrief` with no successful tool produced the canned sentence, which is not valid `HackathonBrief` JSON. OpenMinion then raised `AgentOutputValidationError`. The SDK docs say 0.1.x accepts schema-valid JSON wrapped in provider prose; that path works (see the `Review` run) only when the model actually answers.

We now treat `result.text` as prose and parse the first JSON object ourselves. That matches what at least one other Hackathon #5 project reported independently.

### 4. Default `agent_loop_tool_result_max_chars` is 4000

Cortensor’s cleaned visible text is about 8,100 characters; the useful checklist and “December 18” language sit past the first 4,000. We raised the local config to 20,000 and also put JSON-LD / NUXT timestamps at the top of the digest. This limit should be documented next to `@tool` examples, or the default should be higher for research-style tools.

### 5. Console-rendered replies

Every `result.text` we saw is prefixed with `openminion: `. Fine for a terminal, easy to trip a strict JSON parser. The repair helper strips fences and takes the first `{...}`.

### 6. Token overhead on a trivial turn

The failed `ping` used about 10,824 tokens (`total_tokens_used` in metadata). Identity, memory, and task-update instructions are always in the overlay. A cheap model still pays that fixed cost, which matters on a free Gemini quota.

### 7. Host quirks (not OpenMinion, but they affected the agent)

- DoraHacks returns HTTP 405 “Human Verification” unless the User-Agent starts with `Mozilla/5.0`.
- This environment’s DNS maps public names to `198.18.0.1`, so a naive “resolved IP must be global” SSRF check blocks every website. We now reject local/metadata *names* and IP literals, not proxied resolutions.
- Devpost intermittently serves Cloudflare to `httpx` and the real page to `curl` with the same User-Agent. `fetch_page` falls back to curl when it sees a bot-check.

## Actionable product feedback

1. **If `forced_tools` is set, run that tool even when the entry `task_update` sidecar is missing or invalid.** Then ask for a corrected task update on the next model call. Today a validation error abandons the turn and the forced tool never happens.

2. **Return the underlying `ValueError` (revision mismatch, quote not in user input, missing start objective) to the application**, at least in `result.metadata`. The canned sentence is friendly in a chat UI and opaque in an SDK. `reason_code` was `None` on the stored smoke-test outbound message even though the runtime used `invalid_task_context_update` internally.

3. **Keep the documented compatibility rule:** a first text answer with no tools may omit `task_update`. We hit the opposite behaviour with Gemini. If the rule now depends on the provider producing an internal entry tool call, say so in the Python SDK examples.

4. **Do not fire the freshness classifier on a turn that already has a live tool result or an explicit pasted digest** labelled as page content. Date extraction from a just-fetched page is the whole job of a rules watcher.

5. **Document `agent_loop_tool_result_max_chars`** in the tool example and consider 16–32k as the default for READ_ONLY fetch tools.

6. **Expose `result.output` JSON without the `openminion:` prefix**, or document that `result.text` is a console rendering. SDK callers want the model payload.

7. **Publish the Hackathon #5 submission repository URL.** The official docs still say it “will be added before kickoff” (kickoff was 16 October 2026). Builders currently have a DoraHacks BUIDL form and no PR target.

8. **Date-only timezone labels are ambiguous.** The docs say “December 18, 2026” Pacific Time; DoraHacks gives `2026-12-19T07:59:00.000Z`. RulesMinion prefers structured timestamps when the page has them. A page helper that always emits both the original string and a converted IST value (as our digest already does) should be part of the recommended research-agent starter.

## Suggested fix for (1) and (2)

I did not open an upstream issue or fix PR; the hackathon bonus path asks builders to wait for acknowledgement first. The smallest useful change is: when `forced_tools` is non-empty and `resolve_entry_task_update` raises, log the validation error, synthesize a verbatim `start` update from the user input (the already-implemented compatibility branch), and continue into the forced tool. I can file that as an issue with this write-up if you want it tracked upstream.

## Security notes

Findings above are functional, not security issues. Tool HTTP fetches refuse `localhost`, `*.internal`, metadata hosts, and private IP literals. Snapshots and `.env` are gitignored.
