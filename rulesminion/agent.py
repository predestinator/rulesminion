"""Run one RulesMinion check through the OpenMinion 0.1 Python SDK."""

from __future__ import annotations

import json
import re
import time
import traceback
from collections.abc import Callable

from openminion import Agent, AgentOutputValidationError, ProviderError, tool

from rulesminion.config import AGENTS_JSON, gemini_key_loaded, load_env
from rulesminion.models import ChangeReport, CheckResult, HackathonBrief
from rulesminion.pages import canonical_url, fetch_page, looks_blocked
from rulesminion.snapshots import SnapshotStore, diff_briefs, first_seen_report, url_key
from rulesminion.timeutil import now_ist_label
from rulesminion.tools import fetch_hackathon_page

TASK_UPDATE_FAILURE = "I could not safely update the task conditions"

INSTRUCTIONS = """You are RulesMinion, a careful reader of hackathon rules pages.

Call fetch_hackathon_page with the given URL before answering.
Use only the page digest. Do not invent prizes, dates, or eligibility.

Then return a single JSON object, no extra keys, with:
- title (string)
- url (string)
- organizer (string)
- format: "online", "hybrid", "in-person", or "unclear"
- prize_pool (string)
- prizes: list of {place, amount, notes}
- deadlines: list of {label, as_stated, timezone_as_stated, ist, confidence}
- india_eligible: "yes", "no", or "unclear"
- eligibility_summary (string)
- eligibility_evidence (string)
- submission_checklist: list of strings
- notes: list of strings

Deadline conversion is to IST (Asia/Kolkata, UTC+5:30). Put the original wording
in as_stated and the converted value in ist as 'YYYY-MM-DD HH:MM IST'.
If the digest already includes an IST conversion, reuse it. Timestamps ending in Z are UTC, not Pacific Time.
Offsets: EST=UTC-5, EDT=UTC-4, PST=UTC-8, PDT=UTC-7.
5:00pm EST = 03:30 IST the next calendar day.

india_eligible is yes when the event is worldwide or online with no country ban.
Use no only when a rule clearly excludes India. Quote short evidence.

If a field is not stated, use an empty string, an empty list, or "unclear".
Return JSON only.
"""

FALLBACK_INSTRUCTIONS = """You are RulesMinion. A page digest is already in the user message.
Call mark_digest_ready with the URL, then return JSON only using the same schema:
title, url, organizer, format, prize_pool,
prizes (list of {place, amount, notes}),
deadlines (list of {label, as_stated, timezone_as_stated, ist, confidence}),
india_eligible (yes|no|unclear), eligibility_summary, eligibility_evidence,
submission_checklist (list of strings), notes (list of strings).
Convert deadlines to IST as 'YYYY-MM-DD HH:MM IST'. Do not invent facts.
"""


@tool(name="mark_digest_ready", min_scope="READ_ONLY", idempotent=True)
def mark_digest_ready(url: str) -> str:
    """Acknowledge that a page digest is already present in the user message."""
    return f"Digest ready for {url}."


ProgressFn = Callable[[str], None]


def allow_rulesminion_tools(name: str, _args: dict, _reason: str) -> bool:
    return name in {
        "fetch_hackathon_page",
        "recall_previous_snapshot",
        "mark_digest_ready",
    }


def check_url(url: str, *, store: SnapshotStore | None = None, progress: ProgressFn | None = None) -> CheckResult:
    load_env()
    if not gemini_key_loaded():
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Put it in .env or the environment; RulesMinion will not print it."
        )
    if not AGENTS_JSON.exists():
        raise RuntimeError(
            f"OpenMinion config not found at {AGENTS_JSON}. Run setup as described in the README."
        )

    target = url.strip()
    canonical_url(target)
    store = store or SnapshotStore()
    previous = store.latest(target)
    log = progress or (lambda _message: None)

    prompt = (
        "Read this hackathon page and extract the structured brief.\n"
        f"URL: {target}\n"
        "Return one JSON object after you fetch the page.\n"
    )
    if previous:
        prompt += (
            f"A previous snapshot from {previous.checked_at_ist} is stored locally. "
            "Extract the current page accurately; the application computes the diff.\n"
        )

    session_id = f"rulesminion-{url_key(target)}-{int(time.time())}"
    warnings: list[str] = []
    log("Starting OpenMinion agent (Gemini via the configured provider)...")
    started = time.monotonic()

    try:
        brief, extractor = _extract_brief(target, prompt, session_id, log, warnings)
    except ProviderError as exc:
        raise RuntimeError(_provider_error_message(exc)) from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)
    if not brief.url:
        brief.url = target

    record = store.save(target, brief)
    if previous is None:
        changes: ChangeReport = first_seen_report()
    else:
        changes = diff_briefs(
            previous.brief,
            brief,
            previous_checked_at_ist=previous.checked_at_ist,
        )

    return CheckResult(
        brief=brief,
        changes=changes,
        snapshot_id=record.snapshot_id,
        checked_at_ist=record.checked_at_ist or now_ist_label(),
        extractor=extractor,
        session_id=session_id,
        elapsed_ms=elapsed_ms,
        warnings=warnings,
    )


def _extract_brief(
    target: str,
    prompt: str,
    session_id: str,
    log: ProgressFn,
    warnings: list[str],
) -> tuple[HackathonBrief, str]:
    """Prefetch the page, then extract through OpenMinion.

    Forcing fetch_hackathon_page as the first tool consistently failed the
    OpenMinion entry/task-update protocol with Gemini (tools=0, a canned
    clarify message, or a freshness refusal). A trivial forced tool plus the
    live digest in the user message is the combination that actually runs.
    """
    del prompt
    log("Fetching the page, then starting an OpenMinion extract turn...")
    page = fetch_page(target)
    if looks_blocked(page):
        raise RuntimeError(
            f"The page at {target} returned a bot-check or HTTP {page.status_code} "
            f"({page.title or 'no title'}). Try again, or open the URL in a browser."
        )
    digest = page.digest if len(page.digest) <= 9000 else page.digest[:9000] + "\n[truncated]"
    extract_prompt = (
        f"URL: {target}\n"
        "Call mark_digest_ready with this URL, then extract the brief from this live digest.\n\n"
        f"{digest}\n"
    )
    raw = _run_agent(
        extract_prompt,
        session_id=session_id,
        instructions=FALLBACK_INSTRUCTIONS,
        tools=[mark_digest_ready, fetch_hackathon_page],
        forced_tools=["mark_digest_ready"],
    )
    try:
        return repair_brief(raw, target), "openminion"
    except Exception:
        warnings.append(
            "Model replied with facts but not JSON; requesting a JSON-only rewrite."
        )
        log("Asking OpenMinion to rewrite the last answer as JSON...")
        rewrite_prompt = (
            "Call mark_digest_ready with the URL, then rewrite the following as JSON only "
            "using the RulesMinion schema. Do not use markdown prose.\n\n"
            f"URL: {target}\n\n{raw}\n"
        )
        raw2 = _run_agent(
            rewrite_prompt,
            session_id=session_id + "-json",
            instructions=FALLBACK_INSTRUCTIONS,
            tools=[mark_digest_ready],
            forced_tools=["mark_digest_ready"],
        )
        return repair_brief(raw2, target), "openminion-json-retry"


def _is_rate_limit(exc: BaseException) -> bool:
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", "") or exc)
    blob = f"{code} {message}".lower()
    return "rate_limit" in blob or "rate limited" in blob or "429" in blob or "quota" in blob


def _run_agent(
    prompt: str,
    *,
    session_id: str,
    instructions: str,
    tools: list,
    forced_tools: list[str],
) -> str:
    last_error: BaseException | None = None
    for attempt in range(4):
        try:
            with Agent(
                config_path=str(AGENTS_JSON),
                agent_id="openminion",
                instructions=instructions,
                tools=tools,
                forced_tools=forced_tools,
                session_id=session_id if attempt == 0 else f"{session_id}-retry{attempt}",
            ) as agent:
                result = agent.run(
                    prompt,
                    timeout_seconds=180,
                    approval_callback=allow_rulesminion_tools,
                )
        except AgentOutputValidationError as exc:
            return getattr(exc, "raw_text", "") or str(exc)
        except ProviderError as exc:
            last_error = exc
            if _is_rate_limit(exc) and attempt < 3:
                wait = 20 * (attempt + 1)
                print(f"Provider rate-limited; retrying in {wait}s...", flush=True)
                time.sleep(wait)
                continue
            raise

        text = result.text or ""
        tool_calls = (result.metadata or {}).get("tool_calls_count")
        elapsed = (result.metadata or {}).get("elapsed_ms")
        print(f"Agent finished: session={result.session_id} tools={tool_calls} elapsed_ms={elapsed}", flush=True)
        return text
    assert last_error is not None
    raise last_error


def repair_brief(raw_text: str, fallback_url: str) -> HackathonBrief:
    """Parse a JSON object out of model prose."""
    text = raw_text or ""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    blob = match.group(1) if match else _first_object(text)
    if not blob:
        raise ValueError("Could not repair structured output from the model reply.")
    data = json.loads(blob)
    if fallback_url and not data.get("url"):
        data["url"] = fallback_url
    return HackathonBrief.model_validate(data)


def _first_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _provider_error_message(exc: ProviderError) -> str:
    code = getattr(exc, "code", None) or "provider_error"
    message = getattr(exc, "message", None) or str(exc)
    return f"OpenMinion provider failed ({code}): {message}"


def format_exception(exc: BaseException) -> str:
    return "".join(traceback.format_exception_only(type(exc), exc)).strip()
