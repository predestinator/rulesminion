"""Tiny local web UI so a check can be demoed without extra dependencies."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from rulesminion.agent import check_url, format_exception
from rulesminion.models import CheckResult

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RulesMinion</title>
  <style>
    :root { color-scheme: dark; --bg:#101114; --card:#1a1c21; --fg:#f2efe6; --muted:#a8a297; --line:#2c2f36; --ok:#8bd48b; --warn:#e6c36a; --bad:#e07a7a; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif; background: var(--bg); color: var(--fg); }
    main { max-width: 860px; margin: 0 auto; padding: 48px 20px 80px; }
    h1 { font-size: 2rem; margin: 0 0 8px; letter-spacing: -0.03em; }
    .lede { color: var(--muted); margin: 0 0 28px; line-height: 1.45; }
    form { display: flex; gap: 10px; margin-bottom: 28px; }
    input[type=url] { flex: 1; padding: 12px 14px; border-radius: 10px; border: 1px solid var(--line); background: var(--card); color: var(--fg); font: inherit; }
    button { padding: 12px 18px; border: 0; border-radius: 10px; background: #f2efe6; color: #111; font: inherit; cursor: pointer; }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 20px 22px; margin: 0 0 16px; }
    .card h2 { margin: 0 0 12px; font-size: 1.05rem; }
    a { color: inherit; }
    .muted { color: var(--muted); }
    .yes { color: var(--ok); } .no { color: var(--bad); } .unclear { color: var(--warn); }
    ol { margin: 0; padding-left: 1.2em; }
    li { margin: 0 0 6px; }
    table { width: 100%; border-collapse: collapse; }
    td, th { text-align: left; vertical-align: top; padding: 6px 8px 6px 0; border-bottom: 1px solid var(--line); }
    .error { color: var(--bad); }
  </style>
</head>
<body>
  <main>
    <h1>RulesMinion</h1>
    <p class="lede">Paste a hackathon URL. The OpenMinion agent reads the page, extracts the prize, IST deadlines, India eligibility and submission checklist, then stores a snapshot and reports what changed.</p>
    <form method="post" action="/">
      <input type="url" name="url" required placeholder="https://dorahacks.io/hackathon/2418/detail" value="{url}">
      <button type="submit">Check</button>
    </form>
    {body}
  </main>
</body>
</html>
"""


def serve(host: str = "127.0.0.1", port: int = 8066) -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            sys_stderr_write = __import__("sys").stderr.write
            sys_stderr_write("%s - %s\n" % (self.address_string(), format % args))

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send(200, b"ok\n", "text/plain")
                return
            if parsed.path == "/api/check":
                url = (parse_qs(parsed.query).get("url") or [""])[0]
                self._json_check(url)
                return
            self._send(200, PAGE.format(url="", body="").encode(), "text/html")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8")
            if parsed.path == "/api/check":
                try:
                    payload = json.loads(raw) if raw.strip().startswith("{") else parse_qs(raw)
                    url = payload.get("url") if isinstance(payload, dict) else ""
                    if isinstance(url, list):
                        url = url[0] if url else ""
                except json.JSONDecodeError:
                    url = (parse_qs(raw).get("url") or [""])[0]
                self._json_check(str(url or ""))
                return
            url = (parse_qs(raw).get("url") or [""])[0]
            try:
                result = check_url(url)
                body = _render_html_result(result)
                status = 200
            except Exception as exc:
                body = f'<div class="card error">{html.escape(format_exception(exc))}</div>'
                status = 200
            self._send(status, PAGE.format(url=html.escape(url), body=body).encode(), "text/html")

        def _json_check(self, url: str) -> None:
            try:
                result = check_url(url)
                self._send(200, result.model_dump_json(indent=2).encode() + b"\n", "application/json")
            except Exception as exc:
                payload = json.dumps({"error": format_exception(exc)}).encode()
                self._send(400, payload, "application/json")

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"RulesMinion UI on http://{host}:{port}", flush=True)
    server.serve_forever()


def _render_html_result(result: CheckResult) -> str:
    brief = result.brief
    prize_rows = ""
    if brief.prize_pool:
        prize_rows += f"<tr><th>Pool</th><td>{html.escape(brief.prize_pool)}</td><td></td></tr>"
    for item in brief.prizes:
        prize_rows += (
            f"<tr><td>{html.escape(item.place or '—')}</td>"
            f"<td>{html.escape(item.amount or '—')}</td>"
            f"<td>{html.escape(item.notes or '')}</td></tr>"
        )
    deadline_rows = ""
    for item in brief.deadlines:
        stated = item.as_stated
        if item.timezone_as_stated:
            stated += f" ({item.timezone_as_stated})"
        deadline_rows += (
            f"<tr><td>{html.escape(item.label)}</td>"
            f"<td>{html.escape(stated)}</td>"
            f"<td>{html.escape(item.ist or '—')}</td></tr>"
        )
    checks = "".join(f"<li>{html.escape(item)}</li>" for item in brief.submission_checklist) or "<li>None extracted</li>"
    change_bits = [f"<p><strong>{html.escape(result.changes.status)}</strong> — {html.escape(result.changes.summary)}</p>"]
    for item in result.changes.changed:
        change_bits.append(f"<p>~ {html.escape(item.path)}: {html.escape(item.before or '')} → {html.escape(item.after or '')}</p>")
    for item in result.changes.added:
        change_bits.append(f"<p>+ {html.escape(item)}</p>")
    for item in result.changes.removed:
        change_bits.append(f"<p>- {html.escape(item)}</p>")
    return f"""
    <article class="card">
      <h2>{html.escape(brief.title)}</h2>
      <p><a href="{html.escape(brief.url)}">{html.escape(brief.url)}</a></p>
      <p class="muted">{html.escape(brief.organizer or '')} {html.escape(brief.format or '')}</p>
    </article>
    <article class="card">
      <h2>Prizes</h2>
      <table>{prize_rows or '<tr><td>not stated</td></tr>'}</table>
    </article>
    <article class="card">
      <h2>Deadlines in IST</h2>
      <table>{deadline_rows or '<tr><td>not stated</td></tr>'}</table>
    </article>
    <article class="card">
      <h2>Eligibility</h2>
      <p>India eligible: <strong class="{html.escape(brief.india_eligible)}">{html.escape(brief.india_eligible)}</strong></p>
      <p>{html.escape(brief.eligibility_summary)}</p>
      <p class="muted">{html.escape(brief.eligibility_evidence)}</p>
    </article>
    <article class="card">
      <h2>Submission checklist</h2>
      <ol>{checks}</ol>
    </article>
    <article class="card">
      <h2>Since last check</h2>
      {''.join(change_bits)}
    </article>
    <article class="card muted">
      <p>Checked {html.escape(result.checked_at_ist)} · snapshot {html.escape(result.snapshot_id)} · {html.escape(result.extractor)}</p>
    </article>
    """
