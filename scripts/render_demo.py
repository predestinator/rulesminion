"""Render a short silent demo video from the saved live JSON results."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "demo" / "results"
FRAMES = ROOT / ".rulesminion-demo-frames"
OUT_MP4 = ROOT / "demo" / "rulesminion-demo.mp4"
OUT_GIF = ROOT / "demo" / "rulesminion-demo.gif"
WIDTH, HEIGHT = 1280, 720
BG = (16, 17, 20)
FG = (242, 239, 230)
MUTED = (168, 162, 151)
GOLD = (201, 162, 39)


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap(draw, text: str, fnt, max_width: int) -> list[str]:
    lines = []
    for raw in text.splitlines() or [""]:
        words = raw.split(" ")
        current = ""
        for word in words:
            trial = word if not current else current + " " + word
            if draw.textlength(trial, font=fnt) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_slide(title: str, body: str, footer: str = "") -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    title_font = font(34, True)
    body_font = font(22)
    footer_font = font(18)
    draw.rectangle((0, 0, WIDTH, 8), fill=GOLD)
    draw.text((48, 36), title, font=title_font, fill=GOLD)
    y = 100
    for line in wrap(draw, body, body_font, WIDTH - 96):
        draw.text((48, y), line, font=body_font, fill=FG)
        y += 32
        if y > HEIGHT - 80:
            break
    if footer:
        draw.text((48, HEIGHT - 48), footer, font=footer_font, fill=MUTED)
    return image


def load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def brief_lines(data: dict) -> str:
    brief = data["brief"]
    lines = [
        brief["title"],
        brief["url"],
        "",
        f"Organizer: {brief.get('organizer') or '—'}    Format: {brief.get('format') or '—'}",
        f"Prize pool: {brief.get('prize_pool') or '—'}",
    ]
    for prize in brief.get("prizes") or []:
        extra = f"  — {prize['notes']}" if prize.get("notes") else ""
        lines.append(f"  {prize.get('place') or '—'}: {prize.get('amount') or '—'}{extra}")
    lines.append("")
    lines.append("Deadlines (IST)")
    for item in brief.get("deadlines") or []:
        lines.append(f"  {item.get('label')}: {item.get('as_stated')}  ->  {item.get('ist')}")
    lines.append("")
    lines.append(f"India eligible: {brief.get('india_eligible')}")
    if brief.get("eligibility_summary"):
        lines.append(brief["eligibility_summary"])
    return "\n".join(lines)


def checklist_lines(data: dict) -> str:
    items = data["brief"].get("submission_checklist") or []
    lines = [data["brief"]["title"], ""]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item}")
    return "\n".join(lines)


def main() -> int:
    cortensor = load("cortensor-again.json")
    specs = load("learn-specs.json")
    docs = load("cortensor-docs.json")
    slides = [
        (draw_slide("RulesMinion", "An OpenMinion 0.1 agent that reads a hackathon page\nand extracts prizes, IST deadlines, India eligibility,\nand the submission checklist — then diffs snapshots.\n\nCortensor Hackathon #5  ·  live Gemini runs  ·  11 Nov 2026 IST", "Silent demo of real saved results"), 5),
        (draw_slide("Check 1", "$ python -m rulesminion check \\\n    https://dorahacks.io/hackathon/2418/detail\n\nFetching the page, then starting an OpenMinion extract turn...\nAgent finished: tools=1  elapsed_ms=27238\nextractor=openminion", "Real command output from 2026-11-11 22:07 IST"), 6),
        (draw_slide("Cortensor Hackathon #5", brief_lines(cortensor), "Live extract"), 10),
        (draw_slide("Submission checklist", checklist_lines(cortensor), "Matches the official Hackathon #5 requirements"), 8),
        (draw_slide("Second check of the same URL", "The snapshot store compared this run with 2026-11-11 22:01 IST.\n\nstatus: changed\nprize_pool: 1,150 USD  ->  $1,150 USD\nThe prize table and the 2026-12-19 13:29 IST deadline stayed the same.\nWording of prize notes and eligibility text shifted.\n\nThat is useful, and also a reminder that LLM phrasing can look like\na page change. The IST deadline itself did not move.", cortensor["changes"]["summary"]), 9),
        (draw_slide("Check 2", "$ python -m rulesminion check https://learn-specs.devpost.com/\n\nhttpx received a Cloudflare interstitial.\nFetched successfully via curl fallback.\nAgent finished: tools=1  elapsed_ms=11746", "Devpost page, after the bot-check fallback"), 6),
        (draw_slide("Learn AR with SPECS", brief_lines(specs), "5:00pm EST -> 2026-12-08 03:30 IST"), 10),
        (draw_slide("Check 3  ·  official docs", checklist_lines(docs) + "\n\nPrize pool: $1,150 total, paid in $COR.\nDocs date: 18 December 2026 Pacific Time.\nDoraHacks cutoff: 2026-12-19 13:29 IST.", docs["brief"]["url"]), 8),
        (draw_slide("What we learned about OpenMinion", "Worked: Agent, @tool, sessions, READ_ONLY tools,\napproval_callback, and simple structured output after a tool call.\n\nBroke: a plain Agent.run('ping') and forced fetch_hackathon_page\nboth returned \"I could not safely update the task conditions.\"\nTrivial forced tools (mark_digest_ready) ran fine.\n\nDetails and reproductions are in SDK_FEEDBACK.md.\nFindings are 25% of the official score.", "OpenMinion 0.1.20  ·  gemini-flash-lite-latest"), 10),
        (draw_slide("Not submitted yet", "Local build only.\n\nNeeds an OK before: public Predestinator repo, demo upload,\nDoraHacks BUIDL, PR to the Hackathon #5 submission repository,\nand a $COR wallet if it places.\n\npython -m rulesminion check URL", "rulesminion 0.1.0"), 6),
    ]

    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)
    concat_lines = []
    for index, (image, duration) in enumerate(slides, start=1):
        path = FRAMES / f"slide-{index:02d}.png"
        image.save(path)
        if index == 3:
            image.save(ROOT / "demo" / "cortensor.png")
        if index == 7:
            image.save(ROOT / "demo" / "learn-specs.png")
        concat_lines.append(f"file '{path}'")
        concat_lines.append(f"duration {duration}")
    concat_lines.append(f"file '{FRAMES / f'slide-{len(slides):02d}.png'}'")
    concat_path = FRAMES / "concat.txt"
    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-vsync", "vfr", "-pix_fmt", "yuv420p", str(OUT_MP4)], check=True)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(OUT_MP4), "-vf", "fps=6,scale=960:-1:flags=lanczos", str(OUT_GIF)], check=True)
    print("wrote", OUT_MP4, OUT_MP4.stat().st_size)
    print("wrote", OUT_GIF, OUT_GIF.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
