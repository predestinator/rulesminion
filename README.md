# RulesMinion

An [OpenMinion](https://github.com/OpenMinion/openminion) 0.1 agent that reads a hackathon page and extracts a structured brief: prize pool, deadlines converted to IST, whether someone in India can enter, and the submission checklist. It stores a snapshot after every check and reports what changed.

Built for [Cortensor Hackathon #5](https://dorahacks.io/hackathon/2418/detail) on OpenMinion `0.1.20`, with Gemini `gemini-flash-lite-latest` through the SDK’s OpenAI-compatible adapter.

This is a small, repeatable workflow rather than a multi-agent product. The valuable part is a grounded brief you can diff.

## What it does

```bash
python -m rulesminion check https://dorahacks.io/hackathon/2418/detail
```

1. Fetches the public page (JSON-LD and DoraHacks embedded timestamps are converted to IST up front).
2. Runs an OpenMinion `Agent` turn with registered tools and a forced first tool call.
3. Parses a structured `HackathonBrief`.
4. Writes a snapshot under `state/snapshots/` and diffs it against the previous one.

A tiny local web UI is also included:

```bash
python -m rulesminion web --port 8066
```

## Live example

These figures come from real model-backed runs on 11 November 2026 (IST):

| Page | Prize pool | Headline deadline (IST) | India |
| --- | --- | --- | --- |
| [Cortensor Hackathon #5](https://dorahacks.io/hackathon/2418/detail) | $1,150 USD (paid in $COR; 50% liquid / 50% one-month stake) | Submission 2026-12-19 13:29 IST (page: 2026/12/19 07:59 UTC) | yes, virtual / worldwide |
| [Learn AR with SPECS](https://learn-specs.devpost.com/) | $2,500 ($1,250 / $750 / $500) | Submission 2026-12-08 03:30 IST (page: Dec 7, 2026 @ 5:00pm EST) | yes, all countries except standard exceptions |
| [Hackathon #5 docs](https://docs.cortensor.network/community-and-ecosystem/hackathon/hackathon-5) | $1,150 total | Docs state 18 December 2026 Pacific Time; DoraHacks has the exact cutoff | yes |

The Cortensor checklist the agent pulled matches the official submission requirements: public repo and README, a short SDK workflow note, one working example plus a 1–5 minute demo, Building Blocks Tested, and What We Learned.

Saved JSON from those runs lives in `demo/results/` and `examples/`. The demo recording is `demo/rulesminion-demo.mp4`.

## Setup

Python 3.11+, a virtualenv, and a Gemini API key. Free-tier Gemini works with `gemini-flash-lite-latest`.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a `.env` file (never commit it):

```
GEMINI_API_KEY=your_key_here
```

Point OpenMinion at this project and reuse the checked-in example config, which already selects Gemini through the OpenAI-compatible endpoint:

```bash
export OPENMINION_HOME="$PWD"
export OPENMINION_DATA_ROOT="$PWD/.openminion"
mkdir -p .openminion
cp config/agents.example.json .openminion/agents.json
```

Or run `openminion setup --no-chat` and choose the Gemini preset yourself. The example config reads the key from `GEMINI_API_KEY`; it does not store the secret.

Check the wiring without printing secrets:

```bash
python -m rulesminion doctor
```

## Commands

```bash
python -m rulesminion check URL
python -m rulesminion check URL --json --save out.json
python -m rulesminion history URL
python -m rulesminion demo
python -m rulesminion web --port 8066
python -m rulesminion doctor
```

`demo` checks the three sample pages above.

## OpenMinion SDK workflow

RulesMinion uses the public Python API from `examples/sdk/` in the OpenMinion repo:

- `Agent(...)` as a context manager, with `session_id`, `instructions`, `tools`, `forced_tools`, and `approval_callback`.
- `@tool` functions: `fetch_hackathon_page` (HTTP digest) and `mark_digest_ready` (ack that a live digest is in the prompt). `recall_previous_snapshot` is also registered.
- Application-owned snapshot memory under `state/snapshots/` so diffs do not depend on session leftovers.
- Unique `session_id`s per check. Reusing a session for a short follow-up prompt was not reliable with this model (see `SDK_FEEDBACK.md`).

The path that actually completed real extracts with Gemini was: prefetch a live digest, force a small tool call so the entry/task-update protocol succeeds, then parse JSON from the model reply. Forcing `fetch_hackathon_page` as the first tool repeatedly produced `tools=0` and the canned message “I could not safely update the task conditions.” That investigation is written up in `SDK_FEEDBACK.md` because findings are 25% of the official score.

## Tests

```bash
python -m pytest tests/test_timeutil.py tests/test_pages.py tests/test_snapshots.py
python -m pytest -m live   # real pages + the configured model; needs GEMINI_API_KEY
```

Offline tests cover IST conversion (including `2026-12-19 07:59 UTC → 2026-12-19 13:29 IST` and `5:00pm EST → 03:30 IST next day`), HTML digesting, SSRF guards, and snapshot diffs.

## Submission materials

- `SDK_FEEDBACK.md` — Building Blocks Tested and What We Learned
- `SUBMISSION.md` — exact publish steps (public Predestinator repo, DoraHacks BUIDL, PR to the Hackathon #5 repo, demo, $COR wallet)
- `demo/rulesminion-demo.mp4` and `demo/rulesminion-demo.gif`
- `examples/` — real JSON briefs

Do not commit `.env`, `.openminion/`, or `state/`.
