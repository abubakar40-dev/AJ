"""Lightweight local inbox inspection surface (stdlib HTTP server)."""
from __future__ import annotations

import html
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

from .inbox import InboxStore, inbox_summary, process_capture, retry_failed


def _h(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def render_index(store: InboxStore, status: str = "", msg: str = "") -> str:
    rows = store.list(status=(status or None), include_archived=(status == "archived"), limit=200)
    summ = inbox_summary(store)
    opts = ["", "ready", "queued", "processing", "failed", "archived", "incoming", "processed"]
    filter_html = "".join(
        f'<option value="{_h(o)}" {"selected" if o==status else ""}>{_h(o or "active/all")}</option>' for o in opts
    )
    trs = []
    for r in rows:
        cid = r.get("capture_id", "")
        trs.append(
            "<tr>"
            f"<td><a href='/item/{_h(cid)}'>{_h(cid)}</a></td>"
            f"<td>{_h(r.get('status'))}</td>"
            f"<td>{_h(r.get('source_kind'))}</td>"
            f"<td>{_h(r.get('source_platform'))}</td>"
            f"<td>{_h(r.get('original_filename') or r.get('source_url') or '')}</td>"
            f"<td>{_h(r.get('captured_at'))}</td>"
            f"<td>{_h(r.get('processed_at') or '')}</td>"
            f"<td>{_h((r.get('error_details') or '')[:80])}</td>"
            "</tr>"
        )
    msg_html = f'<div class="msg">{_h(msg)}</div>' if msg else ""
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>AJ Knowledge Inbox</title>
<style>
body{{font-family:sans-serif;margin:16px;background:#111;color:#eee}} a{{color:#8cf}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #333;padding:6px;vertical-align:top}}
th{{background:#222}} .bar{{margin:8px 0}} .pill{{display:inline-block;margin-right:8px;padding:2px 8px;background:#222;border-radius:10px}}
.msg{{background:#243;padding:8px;margin:8px 0;border:1px solid #456}} input,select,button{{padding:4px 8px}}
</style></head><body>
<h2>AJ Knowledge Inbox</h2>
<div class="bar">Root: <code>{_h(summ['root'])}</code></div>
<div class="bar">
{''.join(f'<span class="pill">{_h(k)}: {_h(v)}</span>' for k,v in summ['counts'].items())}
</div>
{msg_html}
<form method="get" action="/" class="bar">
  <label>Status: <select name="status">{filter_html}</select></label>
  <button type="submit">Filter</button>
  <a href="/">Refresh</a>
</form>
<table><thead><tr><th>ID</th><th>Status</th><th>Kind</th><th>Platform</th><th>Source</th><th>Captured</th><th>Processed</th><th>Error</th></tr></thead>
<tbody>{''.join(trs) if trs else '<tr><td colspan="8">No captures.</td></tr>'}</tbody></table>
</body></html>"""


def render_item(store: InboxStore, capture_id: str, msg: str = "") -> str:
    r = store.get(capture_id)
    if not r:
        return f"<html><body><h3>Not found</h3><p>{_h(capture_id)}</p><a href='/'>Back</a></body></html>"
    extracted = ""
    if r.get("extracted_text_path"):
        try:
            txt = Path(r["extracted_text_path"]).read_text(encoding="utf-8", errors="replace")
            extracted = txt[:20000]
        except Exception as e:
            extracted = f"[could not read extracted text: {e}]"
    meta_json = ""
    if r.get("extracted_meta_path"):
        try:
            meta_json = Path(r["extracted_meta_path"]).read_text(encoding="utf-8", errors="replace")
        except Exception:
            meta_json = ""
    msg_html = f'<div class="msg">{_h(msg)}</div>' if msg else ""
    actions = f"""
<form method="post" action="/action/retry/{_h(capture_id)}" style="display:inline"><button>Retry/Process</button></form>
<form method="post" action="/action/archive/{_h(capture_id)}" style="display:inline"><button>Archive</button></form>
<form method="post" action="/action/open/{_h(capture_id)}" style="display:inline"><button>Open original</button></form>
<form method="post" action="/action/open_folder/{_h(capture_id)}" style="display:inline"><button>Open inbox folder</button></form>
"""
    fields = []
    for k in ["capture_id","status","source_kind","source_url","source_path","original_filename","source_platform","mime_type","file_size","capture_method","captured_at","processing_started_at","processed_at","content_hash","canonical_ref","duplicate_of","extractor_version","extracted_text_path","extracted_meta_path","error_details","user_annotations","tags","extra_json"]:
        v = r.get(k)
        if v is None or v == "":
            continue
        fields.append(f"<tr><th>{_h(k)}</th><td><pre style='white-space:pre-wrap;margin:0'>{_h(v)}</pre></td></tr>")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Capture {_h(capture_id)}</title>
<style>
body{{font-family:sans-serif;margin:16px;background:#111;color:#eee}} a{{color:#8cf}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #333;padding:6px;vertical-align:top;text-align:left}}
th{{background:#222;width:220px}} pre{{white-space:pre-wrap}} .msg{{background:#243;padding:8px;margin:8px 0;border:1px solid #456}}
.panel{{background:#181818;border:1px solid #333;padding:10px;margin:10px 0}}
</style></head><body>
<p><a href="/">← Back to inbox</a></p>
<h2>Capture {_h(capture_id)}</h2>
{msg_html}
<div class="bar">{actions}</div>
<table>{''.join(fields)}</table>
<div class="panel"><h3>Extracted text preview</h3><pre>{_h(extracted) if extracted else '(none)'}</pre></div>
<div class="panel"><h3>Extracted metadata JSON</h3><pre>{_h(meta_json) if meta_json else '(none)'}</pre></div>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    store: InboxStore

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            qs = urllib.parse.parse_qs(parsed.query)
            status = (qs.get("status") or [""])[0]
            msg = (qs.get("msg") or [""])[0]
            body = render_index(self.store, status=status, msg=msg).encode("utf-8")
            self._send(200, body)
            return
        if parsed.path.startswith("/item/"):
            cid = parsed.path.split("/item/", 1)[1]
            qs = urllib.parse.parse_qs(parsed.query)
            msg = (qs.get("msg") or [""])[0]
            body = render_item(self.store, cid, msg=msg).encode("utf-8")
            self._send(200, body)
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "action":
            action, cid = parts[1], parts[2]
            msg = ""
            try:
                if action == "retry":
                    rec = retry_failed(self.store, cid)
                    msg = f"retry -> {rec.get('status')}"
                elif action == "archive":
                    rec = self.store.archive(cid)
                    msg = "archived" if rec else "not found"
                elif action == "open":
                    import subprocess
                    rec = self.store.get(cid)
                    path = (rec or {}).get("source_path")
                    if path and Path(path).exists():
                        subprocess.Popen(["xdg-open", path])
                        msg = "opened original"
                    else:
                        msg = "original not found"
                elif action == "open_folder":
                    import subprocess
                    subprocess.Popen(["xdg-open", str(self.store.root)])
                    msg = "opened inbox folder"
                else:
                    msg = "unknown action"
            except Exception as e:
                msg = f"error: {e}"
            loc = f"/item/{urllib.parse.quote(cid)}?msg={urllib.parse.quote(msg)}"
            self.send_response(303)
            self.send_header("Location", loc)
            self.end_headers()
            return
        self._send(404, b"not found", "text/plain")

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quiet
        return


def serve(store: InboxStore, host: str = "127.0.0.1", port: int = 8766):
    Handler.store = store
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd
