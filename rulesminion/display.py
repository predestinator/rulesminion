"""Shared Rich rendering for the CLI, demo, and tests."""

from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from rulesminion.models import CheckResult


def render_result(console: Console, result: CheckResult) -> None:
    brief = result.brief
    title = brief.title or "Untitled hackathon"
    header = Text()
    header.append(title, style="bold")
    header.append(f"\n{brief.url}", style="dim")
    if brief.organizer:
        header.append(f"\nOrganizer: {brief.organizer}")
    if brief.format:
        header.append(f"\nFormat: {brief.format}")

    prizes = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    prizes.add_column("Place")
    prizes.add_column("Amount")
    prizes.add_column("Notes")
    if brief.prize_pool:
        prizes.add_row("Pool", brief.prize_pool, "")
    for item in brief.prizes:
        prizes.add_row(item.place or "—", item.amount or "—", item.notes or "")
    if not brief.prize_pool and not brief.prizes:
        prizes.add_row("—", "not stated", "")

    deadlines = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    deadlines.add_column("Label")
    deadlines.add_column("As stated")
    deadlines.add_column("IST")
    deadlines.add_column("Confidence")
    if brief.deadlines:
        for item in brief.deadlines:
            stated = item.as_stated
            if item.timezone_as_stated:
                stated = f"{stated} ({item.timezone_as_stated})"
            deadlines.add_row(item.label, stated, item.ist or "—", item.confidence or "—")
    else:
        deadlines.add_row("—", "not stated", "—", "—")

    eligibility = Text()
    eligibility.append("India eligible: ", style="bold")
    color = {"yes": "green", "no": "red"}.get(brief.india_eligible, "yellow")
    eligibility.append(brief.india_eligible, style=f"bold {color}")
    if brief.eligibility_summary:
        eligibility.append(f"\n{brief.eligibility_summary}")
    if brief.eligibility_evidence:
        eligibility.append(f"\nEvidence: {brief.eligibility_evidence}", style="dim")

    checklist = Text()
    if brief.submission_checklist:
        for index, item in enumerate(brief.submission_checklist, start=1):
            checklist.append(f"{index}. {item}\n")
    else:
        checklist.append("No checklist items extracted.")

    changes = Text()
    changes.append(result.changes.status, style="bold")
    if result.changes.summary:
        changes.append(f" — {result.changes.summary}")
    if result.changes.previous_checked_at_ist:
        changes.append(f"\nCompared with snapshot from {result.changes.previous_checked_at_ist}", style="dim")
    for item in result.changes.changed:
        changes.append(f"\n~ {item.path}: {item.before} → {item.after}")
    for item in result.changes.added:
        changes.append(f"\n+ {item}")
    for item in result.changes.removed:
        changes.append(f"\n- {item}")

    meta = Text()
    meta.append(f"Checked {result.checked_at_ist}")
    meta.append(f"  snapshot {result.snapshot_id}", style="dim")
    meta.append(f"\nextractor={result.extractor}")
    if result.elapsed_ms is not None:
        meta.append(f"  {result.elapsed_ms} ms")
    if result.session_id:
        meta.append(f"\nsession {result.session_id}", style="dim")
    for warning in result.warnings:
        meta.append(f"\nwarning: {warning}", style="yellow")

    body = Group(
        header,
        Text(""),
        Panel(prizes, title="Prizes", border_style="gold1"),
        Panel(deadlines, title="Deadlines (IST)", border_style="cyan"),
        Panel(eligibility, title="Eligibility", border_style="green"),
        Panel(checklist, title="Submission checklist", border_style="magenta"),
        Panel(changes, title="Since last check", border_style="white"),
        Panel(meta, title="Run", border_style="dim"),
    )
    if brief.notes:
        notes = Text("\n".join(f"• {note}" for note in brief.notes))
        body = Group(body, Panel(notes, title="Notes", border_style="dim"))
    console.print(Panel(body, title="RulesMinion", border_style="bright_white"))
