"""Tiny local web UI. No extra web framework — stdlib only."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from rulesminion.agent import check_url, format_exception
from rulesminion.models import CheckResult

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RulesMinion</title>
  <style>
    :root {{
      --bg: #12110f;
      --card: #1c1a17;
      --fg: #f3ead8;
      --muted: #b5aa94;
      --line: #3a342c;
      --accent: #e0b144;
    }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
      background: var(--bg);
      color: var(--fg);
    }}
    main {{ max-width: 820px; margin: 48px auto; padding: 0 20px 80px; }}
    h1 {{ font-size: 2.1rem; letter-spacing: -0.03em; margin: 0 0 8px; }}
    p.lead {{ color: var(--muted); margin-top: 0; }}
    form {{ display: flex; gap: 8px; margin: 24px 0 32px; }}
    input[type=url] {{
      flex: 1;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--card);
      color: var(--fg);
      font-size: 1rem;
    }}
    button {{
      padding: 12px 18px;
      border: 0;
      border-radius: 8px;
      background: var(--accent);
      color: #1a1406;
      font-weight: 700;
      cursor: pointer;
    }}
    section {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 18px 20px;
      margin: 16px 0;
    }}
    h2 {{ margin: 0 0 10px; font-size: 1.15rem; }}
    .muted {{ color: var(--muted); }}
    .yes {{ color: #8fce7a; font-weight: 700; }}
    .no {{ color: #ee7a6b; font-weight: 700; }}
    .unclear {{ color: var(--accent); font-weight: 700; }}
    ol {{ margin: 0; padding-left: 1.2rem; }}
    li {{ margin: 6px 0; }}
    .error {{ color: #ee7a6b; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.92em; }}
  </style>
</head>
<body>
<main>
  <h1>RulesMinion</h1>
  <p class="lead">Paste a hackathon URL. The OpenMinion agent reads the page, extracts the prize, IST deadlines, India eligibility and the submission checklist, then diffs it against the last snapshot. A run usually takes about a minute.</p>
  <form method="post" action="/">
    <input type="url" name="url" placeholder="https://dorahacks.io/hackathon/2418/detail" value="{url}" required>
    <button type="submit">Check</button>
  </form>
  {body}
</main>
</body>
</html>
"""


def render_page(url: str = "", body: str = "") -> bytes:
    return PAGE.format(url=html.escape(url), body=body).encode("utf-8")


def render_result_html(result: CheckResult) -> str:
    brief = result.brief
    india_class = {"yes": "yes", "no": "no"}.get(brief.india_eligible, "unclear")
    prizes = ""
    if brief.prize_pool:
        prizes += f"<p><strong>Pool:</strong> {html.escape(brief.prize_pool)}</p>"
    if brief.prizes:
        prizes += "<ul>" + "".join(
            f"<li>{html.escape(item.place + ': ' if item.place else '')}"
            f"{html.escape(item.amount)}"
            f"{html.escape(' — ' + item.notes if item.notes else '')}</li>"
            for item in brief.prizes
        ) + "</ul>"
    if not prizes:
        prizes = "<p class='muted'>No prize details extracted.</p>"

    if brief.deadlines:
        deadlines = "<ul>" + "".join(
            f"<li><strong>{html.escape(item.label)}</strong>: "
            f"{html.escape(item.as_stated)}"
            f"{html.escape(' (' + item.timezone_as_stated + ')' if item.timezone_as_stated else '')}"
            f" → <code>{html.escape(item.ist or '—')}</code></li>"
            for item in brief.deadlines
        ) + "</ul>"
    else:
        deadlines = "<p class='muted'>No deadlines extracted.</p>"

    if brief.submission_checklist:
        checklist = "<ol>" + "".join(
            f"<li>{html.escape(item)}</li>" for item in brief.submission_checklist
        ) + "</ol>"
    else:
        checklist = "<p class='muted'>No checklist items extracted.</p>"

    changes = f"<p><strong>{html.escape(result.changes.status)}</strong> — {html.escape(result.changes.summary)}</p>"
    for item in result.changes.changed:
        changes += f"<p>~ {html.escape(item.path)}: {html.escape(item.before or '')} → {html.escape(item.after or '')}</p>"
    for item in result.changes.added:
        changes += f"<p>+ {html.escape(item)}</p>"
    for item in result.changes.removed:
        changes += f"<p>- {html.escape(item)}</p>"

    return f"""
    <section>
      <h2>{html.escape(brief.title)}</h2>
      <p class="muted">{html.escape(brief.url)}<br>
      {html.escape(brief.organizer)} · {html.escape(brief.format)}</p>
    </section>
    <section><h2>Prizes</h2>{prizes}</section>
    <section><h2>Deadlines (IST)</h2>{deadlines}</section>
    <section>
      <h2>Eligibility</h2>
      <p>India eligible: <span class="{india_class}">{html.escape(brief.india_eligible)}</span></p>
      <p>{html.escape(brief.eligibility_summary)}</p>
      <p class="muted">{html.escape(brief.eligibility_evidence)}</p>
    </section>
    <section><h2>Submission checklist</h2>{checklist}</section>
    <section><h2>Since last check</h2>{changes}</section>
    <section>
      <h2>Run</h2>
      <p class="muted">Checked {html.escape(result.checked_at_ist)} · snapshot {html.escape(result.snapshot_id)} · extractor {html.escape(result.extractor)}</p>
    </section>
    """


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        sys_stderr = __import__("sys").stderr
        sys_stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send(200, b"ok\n", "text/plain; charset=utf-8")
            return
        if parsed.path == "/api/check":
            query = parse_qs(parsed.query)
            url = (query.get("url") or [""])[0].strip()
            self._api_check(url)
            return
        if parsed.path != "/":
            self._send(404, render_page(body="<p class='error'>Not found.</p>"))
            return
        self._send(200, render_page())

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        if parsed.path == "/api/check":
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = parse_qs(raw)
            url = str((payload.get("url") if isinstance(payload, dict) else "") or "")
            if isinstance(url, list):
                url = url[0] if url else ""
            self._api_check(url.strip())
            return
        form = parse_qs(raw)
        url = (form.get("url") or [""])[0].strip()
        try:
            result = check_url(url)
            body = render_result_html(result)
            self._send(200, render_page(url, body))
        except Exception as exc:
            body = f"<p class='error'>{html.escape(format_exception(exc))}</p>"
            self._send(200, render_page(url, body))

    def _api_check(self, url: str) -> None:
        if not url:
            payload = {"error": "url is required"}
            self._send(400, json.dumps(payload).encode(), "application/json")
            return
        try:
            result = check_url(url)
        except Exception as exc:
            payload = {"error": format_exception(exc)}
            self._send(400, json.dumps(payload).encode(), "application/json")
            return
        self._send(200, result.model_dump_json(indent=2).encode(), "application/json")


def serve(host: str = "127.0.0.1", port: int = 8066) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"RulesMinion UI on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        server.server_close()
