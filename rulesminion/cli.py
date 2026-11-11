"""Command-line interface for RulesMinion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console

from rulesminion import __version__
from rulesminion.agent import check_url, format_exception
from rulesminion.config import AGENTS_JSON, OPENMINION_DIR, gemini_key_loaded, load_env
from rulesminion.display import render_result
from rulesminion.models import CheckResult
from rulesminion.snapshots import SnapshotStore
from rulesminion.web import serve

DEFAULT_DEMO_URLS = [
    "https://dorahacks.io/hackathon/2418/detail",
    "https://learn-specs.devpost.com/",
    "https://docs.cortensor.network/community-and-ecosystem/hackathon/hackathon-5",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rulesminion",
        description="Extract hackathon prizes, IST deadlines, eligibility and checklists, then diff snapshots.",
    )
    parser.add_argument("--version", action="version", version=f"rulesminion {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser("check", help="Fetch a page and extract a structured brief")
    check_p.add_argument("url", help="Public hackathon page URL")
    check_p.add_argument("--json", action="store_true", dest="as_json", help="Print JSON instead of a table")
    check_p.add_argument("--save", type=Path, default=None, help="Also write JSON to this path")

    hist_p = sub.add_parser("history", help="Show stored snapshots for a URL")
    hist_p.add_argument("url")
    hist_p.add_argument("--json", action="store_true", dest="as_json")

    demo_p = sub.add_parser("demo", help="Check the sample hackathon pages")
    demo_p.add_argument("urls", nargs="*", default=DEFAULT_DEMO_URLS)
    demo_p.add_argument("--repeat-first", action="store_true", help="Re-check the first URL to show the diff")
    demo_p.add_argument("--out-dir", type=Path, default=None, help="Write each result as JSON")

    web_p = sub.add_parser("web", help="Start a tiny local web UI")
    web_p.add_argument("--host", default="127.0.0.1")
    web_p.add_argument("--port", type=int, default=8066)

    sub.add_parser("doctor", help="Check local config without printing secrets")

    args = parser.parse_args(argv)
    console = Console()
    try:
        if args.command == "check":
            return _cmd_check(console, args.url, as_json=args.as_json, save=args.save)
        if args.command == "history":
            return _cmd_history(console, args.url, as_json=args.as_json)
        if args.command == "demo":
            return _cmd_demo(console, args.urls, repeat_first=args.repeat_first, out_dir=args.out_dir)
        if args.command == "web":
            serve(host=args.host, port=args.port)
            return 0
        if args.command == "doctor":
            return _cmd_doctor(console)
    except Exception as exc:
        console.print(f"[red]{format_exception(exc)}[/red]")
        return 1
    return 1


def _cmd_check(console: Console, url: str, *, as_json: bool, save: Path | None) -> int:
    result = check_url(url, progress=lambda message: console.print(f"[dim]{message}[/dim]"))
    _emit(console, result, as_json=as_json, save=save)
    return 0


def _cmd_history(console: Console, url: str, *, as_json: bool) -> int:
    rows = SnapshotStore().history(url)
    payload = [
        {
            "snapshot_id": row.snapshot_id,
            "checked_at_ist": row.checked_at_ist,
            "title": row.brief.title,
            "prize_pool": row.brief.prize_pool,
            "path": row.path,
        }
        for row in rows
    ]
    if as_json:
        console.print_json(json.dumps(payload))
        return 0
    if not payload:
        console.print("No snapshots stored for that URL yet.")
        return 0
    for row in payload:
        console.print(f"{row['checked_at_ist']}  {row['snapshot_id']}  {row['title']}  {row['prize_pool']}")
    return 0


def _cmd_demo(console: Console, urls: list[str], *, repeat_first: bool, out_dir: Path | None) -> int:
    sequence = list(urls)
    if repeat_first and urls:
        sequence.append(urls[0])
    results: list[CheckResult] = []
    for index, url in enumerate(sequence, start=1):
        console.rule(f"Check {index}/{len(sequence)}")
        result = check_url(url, progress=lambda message: console.print(f"[dim]{message}[/dim]"))
        _emit(console, result, as_json=False, save=_demo_save_path(out_dir, url, index))
        results.append(result)
    console.rule("Summary")
    for result in results:
        console.print(
            f"{result.changes.status:11}  {result.brief.title}  "
            f"{result.brief.prize_pool or 'no pool'}  "
            f"India={result.brief.india_eligible}"
        )
    return 0


def _demo_save_path(out_dir: Path | None, url: str, index: int) -> Path | None:
    if out_dir is None:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = url.split("//", 1)[-1].replace("/", "-").strip("-")[:80]
    return out_dir / f"{index:02d}-{slug}.json"


def _emit(console: Console, result: CheckResult, *, as_json: bool, save: Path | None) -> None:
    payload = json.loads(result.model_dump_json())
    if save:
        save.parent.mkdir(parents=True, exist_ok=True)
        save.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        console.print(f"[dim]Wrote {save}[/dim]")
    if as_json:
        console.print_json(json.dumps(payload))
        return
    render_result(console, result)


def _cmd_doctor(console: Console) -> int:
    load_env()
    console.print(f"rulesminion {__version__}")
    try:
        import openminion

        console.print(f"openminion {openminion.__version__}")
    except Exception as exc:
        console.print(f"[red]openminion import failed: {exc}[/red]")
        return 1
    console.print(f"OPENMINION_HOME dir exists: {OPENMINION_DIR.exists()}")
    console.print(f"agents.json exists: {AGENTS_JSON.exists()}")
    console.print(f"GEMINI_API_KEY loaded: {gemini_key_loaded()}")
    if AGENTS_JSON.exists():
        data = json.loads(AGENTS_JSON.read_text(encoding="utf-8"))
        provider = (data.get("providers") or {}).get("openai") or {}
        model = provider.get("model")
        base = provider.get("base_url")
        env_name = provider.get("api_key_env")
        console.print(f"configured model: {model}")
        console.print(f"configured base_url: {base}")
        console.print(f"configured api_key_env: {env_name}")
        console.print(f"default_agent: {data.get('default_agent')}")
    if not gemini_key_loaded() or not AGENTS_JSON.exists():
        return 1
    console.print("doctor: ready (no secrets printed)")
    return 0
