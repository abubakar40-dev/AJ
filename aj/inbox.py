"""AJ Personal Knowledge Inbox.

A local, capture-first inbox for URLs, files, text and media dropped on the AJ
orb or submitted via the CLI/API. Originals are preserved; derived artifacts are
stored separately. Processing is asynchronous-capable, retryable and idempotent.

This module is dependency-light (stdlib by default). Optional extractors use
third-party libraries when installed and degrade gracefully when absent.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    from . import errors
except Exception:  # pragma: no cover - standalone fallback
    class _E(Exception):
        pass
    class errors:  # type: ignore
        AjError = _E
        ConfigError = _E

# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------
INCOMING = "incoming"
QUEUED = "queued"
PROCESSING = "processing"
PROCESSED = "processed"
READY = "ready"          # processed and notification-ready
FAILED = "failed"
ARCHIVED = "archived"    # soft-delete / removed from active view

ACTIVE_STATES = {INCOMING, QUEUED, PROCESSING, PROCESSED, READY, FAILED}
TERMINAL_OK = {READY, PROCESSED, ARCHIVED}
TERMINAL_BAD = {FAILED}

CAPTURE_METHODS = {"drag_file", "drag_url", "drag_text", "paste", "cli", "api", "context_menu"}

# ---------------------------------------------------------------------------
# Paths / layout
# ---------------------------------------------------------------------------

def default_data_dir() -> Path:
    """Legacy AJ data dir (home). Used only when no config/explicit root applies."""
    base = Path(os.environ.get("AJ_DATA_DIR") or os.path.expanduser("~/.local/share/aj"))
    return base.expanduser()

def default_inbox_root() -> Path:
    """Legacy default inbox location (home). Not a silent fallback for configured roots."""
    return default_data_dir() / "knowledge-inbox"

_NULL_PATH_TEXT = {"none", "null"}


def _validated_inbox_root_value(value: Any, *, source: str) -> Optional[Path]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise errors.ConfigError(f"{source} must be a path string, not a boolean")
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in _NULL_PATH_TEXT:
        raise errors.ConfigError(f"{source} must be a filesystem path, not {text!r}")
    return Path(text).expanduser()


def resolve_inbox_root(
    explicit: Optional[Path | str] = None,
    config: Any = None,
    *,
    require_configured: bool = False,
) -> Path:
    """Resolve canonical inbox root.

    Precedence: explicit arg > AJ_INBOX_ROOT env > config core.inbox_root
    > config core.data_dir/knowledge-inbox > legacy home default.
    """
    explicit_path = _validated_inbox_root_value(explicit, source="inbox root")
    if explicit_path is not None:
        return explicit_path

    env_root = os.environ.get("AJ_INBOX_ROOT")
    if env_root is not None and str(env_root).strip() != "":
        env_path = _validated_inbox_root_value(env_root, source="AJ_INBOX_ROOT")
        if env_path is not None:
            return env_path

    if config is not None:
        # Explicit inbox root override if configured.
        try:
            inbox_override = config.get("core.inbox_root", "")
        except Exception:
            inbox_override = ""
        override_path = _validated_inbox_root_value(inbox_override, source="core.inbox_root")
        if override_path is not None:
            return override_path
        try:
            data_dir = config.get("core.data_dir", "")
        except Exception:
            data_dir = ""
        data_path = _validated_inbox_root_value(data_dir, source="core.data_dir")
        if data_path is not None:
            return data_path / "knowledge-inbox"
        if require_configured:
            raise errors.ConfigError("AJ config does not define core.data_dir for inbox storage")

    return default_inbox_root()

def inbox_root(data_dir: Optional[Path | str] = None, config: Any = None) -> Path:
    """Back-compat: explicit path is treated as the inbox root; otherwise resolve canonically."""
    if data_dir is not None:
        return Path(data_dir).expanduser()
    return resolve_inbox_root(config=config)

def ensure_layout(root: Path, *, require_writable: bool = False) -> Dict[str, Path]:
    paths = {
        "root": root,
        "incoming": root / "incoming",
        "processing": root / "processing",
        "processed": root / "processed",
        "failed": root / "failed",
        "originals": root / "originals",
        "extracted": root / "extracted",
        "metadata": root / "metadata",
        "thumbnails": root / "thumbnails",
        "index": root / "index",
    }
    try:
        for p in paths.values():
            p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        if require_writable:
            raise errors.ConfigError(f"inbox storage unavailable or not writable: {root}: {e}") from e
        raise
    if require_writable and not os.access(root, os.W_OK):
        raise errors.ConfigError(f"inbox storage is not writable: {root}")
    return paths

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def new_capture_id() -> str:
    return f"cap_{uuid.uuid4().hex}"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def canonical_url(url: str) -> str:
    return (url or "").strip()

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

def looks_like_url(text: str) -> bool:
    return bool(_URL_RE.match((text or "").strip()))

def detect_platform(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return "unknown"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "instagram.com" in host:
        return "instagram"
    if host:
        return host
    return "unknown"

def safe_filename(name: str) -> str:
    name = os.path.basename(name or "capture")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or "capture"

# ---------------------------------------------------------------------------
# Metadata DB
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS captures (
  capture_id TEXT PRIMARY KEY,
  content_hash TEXT,
  canonical_ref TEXT,
  source_kind TEXT,            -- file|url|text
  source_url TEXT,
  source_path TEXT,
  original_filename TEXT,
  source_platform TEXT,
  mime_type TEXT,
  file_size INTEGER,
  capture_method TEXT,
  captured_at TEXT,
  processing_started_at TEXT,
  processed_at TEXT,
  status TEXT,
  extractor_version TEXT,
  extracted_text_path TEXT,
  extracted_meta_path TEXT,
  thumbnail_path TEXT,
  error_details TEXT,
  user_annotations TEXT,
  tags TEXT,
  duplicate_of TEXT,
  notified_at TEXT,
  archived INTEGER DEFAULT 0,
  extra_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_captures_status ON captures(status);
CREATE INDEX IF NOT EXISTS idx_captures_hash ON captures(content_hash);
CREATE INDEX IF NOT EXISTS idx_captures_ref ON captures(canonical_ref);
CREATE INDEX IF NOT EXISTS idx_captures_captured ON captures(captured_at);
"""

class InboxStore:
    def __init__(self, root: Optional[Path | str] = None, config: Any = None):
        # Explicit root (including temp/test dirs) is treated as the inbox root.
        # When omitted, resolve canonically from config/env/defaults.
        self.config = config
        self.root = inbox_root(root, config=config)
        self.paths = ensure_layout(self.root)
        self.db_path = self.paths["index"] / "inbox.sqlite3"
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(SCHEMA)
                conn.commit()
            finally:
                conn.close()

    def add_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        cols = [
            "capture_id","content_hash","canonical_ref","source_kind","source_url","source_path",
            "original_filename","source_platform","mime_type","file_size","capture_method",
            "captured_at","processing_started_at","processed_at","status","extractor_version",
            "extracted_text_path","extracted_meta_path","thumbnail_path","error_details",
            "user_annotations","tags","duplicate_of","notified_at","archived","extra_json",
        ]
        values = [record.get(c) for c in cols]
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    f"INSERT INTO captures ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})",
                    values,
                )
                conn.commit()
            finally:
                conn.close()
        return record

    def get(self, capture_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def list(self, status: Optional[str] = None, include_archived: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        q = "SELECT * FROM captures"
        args: List[Any] = []
        clauses = []
        if status:
            clauses.append("status=?")
            args.append(status)
        if not include_archived:
            clauses.append("archived=0")
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY captured_at DESC, rowid DESC LIMIT ?"
        args.append(max(1, int(limit or 100)))
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(q, args).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def find_duplicates(self, content_hash: Optional[str] = None, canonical_ref: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses, args = [], []
        if content_hash:
            clauses.append("content_hash=?"); args.append(content_hash)
        if canonical_ref:
            clauses.append("canonical_ref=?"); args.append(canonical_ref)
        if not clauses:
            return []
        q = "SELECT * FROM captures WHERE (" + " OR ".join(clauses) + ") AND archived=0 ORDER BY captured_at DESC"
        with self._lock:
            conn = self._connect()
            try:
                return [dict(r) for r in conn.execute(q, args).fetchall()]
            finally:
                conn.close()

    def update_status(self, capture_id: str, status: str, **fields: Any) -> Optional[Dict[str, Any]]:
        sets = ["status=?"]
        args: List[Any] = [status]
        for k, v in fields.items():
            sets.append(f"{k}=?")
            args.append(v)
        args.append(capture_id)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(f"UPDATE captures SET {', '.join(sets)} WHERE capture_id=?", args)
                conn.commit()
            finally:
                conn.close()
        return self.get(capture_id)

    def annotate(self, capture_id: str, notes: Optional[str] = None, tags: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        rec = self.get(capture_id)
        if not rec:
            return None
        fields: Dict[str, Any] = {}
        if notes is not None:
            fields["user_annotations"] = notes
        if tags is not None:
            fields["tags"] = json.dumps(tags, ensure_ascii=False)
        if not fields:
            return rec
        sets = [f"{k}=?" for k in fields]
        args = list(fields.values()) + [capture_id]
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(f"UPDATE captures SET {', '.join(sets)} WHERE capture_id=?", args)
                conn.commit()
            finally:
                conn.close()
        return self.get(capture_id)

    def archive(self, capture_id: str) -> Optional[Dict[str, Any]]:
        return self.update_status(capture_id, ARCHIVED, archived=1)

# ---------------------------------------------------------------------------
# Capture operations
# ---------------------------------------------------------------------------

def _write_metadata_json(paths: Dict[str, Path], capture_id: str, record: Dict[str, Any]) -> Path:
    meta_path = paths["metadata"] / f"{capture_id}.json"
    tmp = meta_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, meta_path)
    return meta_path


def _record_base(**kw: Any) -> Dict[str, Any]:
    base = {
        "capture_id": kw.get("capture_id") or new_capture_id(),
        "content_hash": kw.get("content_hash"),
        "canonical_ref": kw.get("canonical_ref"),
        "source_kind": kw.get("source_kind"),
        "source_url": kw.get("source_url"),
        "source_path": kw.get("source_path"),
        "original_filename": kw.get("original_filename"),
        "source_platform": kw.get("source_platform"),
        "mime_type": kw.get("mime_type"),
        "file_size": kw.get("file_size"),
        "capture_method": kw.get("capture_method", "api"),
        "captured_at": kw.get("captured_at") or utc_now(),
        "processing_started_at": None,
        "processed_at": None,
        "status": kw.get("status", QUEUED),
        "extractor_version": None,
        "extracted_text_path": None,
        "extracted_meta_path": None,
        "thumbnail_path": None,
        "error_details": None,
        "user_annotations": None,
        "tags": None,
        "duplicate_of": None,
        "notified_at": None,
        "archived": 0,
        "extra_json": None,
    }
    base.update({k: v for k, v in kw.items() if k in base})
    return base


def capture_file(store: InboxStore, file_path: str | Path, capture_method: str = "drag_file",
                 allow_duplicate: bool = True) -> Dict[str, Any]:
    src = Path(file_path).expanduser()
    if not src.exists() or not src.is_file():
        raise errors.AjError(f"capture file not found: {src}", code="capture_not_found")
    content_hash = sha256_file(src)
    canonical_ref = str(src.resolve())
    dups = store.find_duplicates(content_hash=content_hash, canonical_ref=canonical_ref)
    mime, _ = mimetypes.guess_type(src.name)
    capture_id = new_capture_id()
    dest_name = f"{capture_id}_{safe_filename(src.name)}"
    dest = store.paths["originals"] / dest_name
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)
    record = _record_base(
        capture_id=capture_id,
        content_hash=content_hash,
        canonical_ref=canonical_ref,
        source_kind="file",
        source_url=None,
        source_path=str(dest),
        original_filename=src.name,
        source_platform="local_file",
        mime_type=mime or "application/octet-stream",
        file_size=dest.stat().st_size,
        capture_method=capture_method if capture_method in CAPTURE_METHODS else "drag_file",
        status=QUEUED,
        duplicate_of=(dups[0]["capture_id"] if dups else None),
        extra_json=json.dumps({"duplicate_detected": bool(dups), "original_input_path": str(src)}, ensure_ascii=False),
    )
    _write_metadata_json(store.paths, capture_id, record)
    store.add_record(record)
    return record


def capture_url(store: InboxStore, url: str, capture_method: str = "drag_url",
                allow_duplicate: bool = True) -> Dict[str, Any]:
    url = canonical_url(url)
    if not looks_like_url(url):
        raise errors.AjError(f"invalid URL: {url}", code="capture_invalid")
    canonical_ref = url
    content_hash = sha256_bytes(url.encode("utf-8"))
    dups = store.find_duplicates(canonical_ref=canonical_ref)
    capture_id = new_capture_id()
    platform = detect_platform(url)
    orig_path = store.paths["originals"] / f"{capture_id}.url.txt"
    orig_path.write_text(url + "\n", encoding="utf-8")
    record = _record_base(
        capture_id=capture_id,
        content_hash=content_hash,
        canonical_ref=canonical_ref,
        source_kind="url",
        source_url=url,
        source_path=str(orig_path),
        original_filename=f"{platform or 'link'}.url",
        source_platform=platform,
        mime_type="text/uri-list",
        file_size=len(url.encode("utf-8")),
        capture_method=capture_method if capture_method in CAPTURE_METHODS else "drag_url",
        status=QUEUED,
        duplicate_of=(dups[0]["capture_id"] if dups else None),
        extra_json=json.dumps({"duplicate_detected": bool(dups)}, ensure_ascii=False),
    )
    _write_metadata_json(store.paths, capture_id, record)
    store.add_record(record)
    return record


def capture_text(store: InboxStore, text: str, capture_method: str = "paste",
                 allow_duplicate: bool = True) -> Dict[str, Any]:
    text = str(text or "")
    if not text.strip():
        raise errors.AjError("empty text capture", code="capture_invalid")
    stripped = text.strip()
    if looks_like_url(stripped) and "\n" not in stripped and len(stripped) < 2048:
        return capture_url(store, stripped, capture_method=capture_method, allow_duplicate=allow_duplicate)
    content_hash = sha256_bytes(text.encode("utf-8"))
    dups = store.find_duplicates(content_hash=content_hash)
    capture_id = new_capture_id()
    orig_path = store.paths["originals"] / f"{capture_id}.txt"
    orig_path.write_text(text, encoding="utf-8")
    embedded = [m.group(0) for m in re.finditer(r"https?://\S+", text)]
    record = _record_base(
        capture_id=capture_id,
        content_hash=content_hash,
        canonical_ref=f"text:{content_hash[:16]}",
        source_kind="text",
        source_url=None,
        source_path=str(orig_path),
        original_filename="captured_text.txt",
        source_platform="text",
        mime_type="text/plain",
        file_size=len(text.encode("utf-8")),
        capture_method=capture_method if capture_method in CAPTURE_METHODS else "paste",
        status=QUEUED,
        duplicate_of=(dups[0]["capture_id"] if dups else None),
        extra_json=json.dumps({"duplicate_detected": bool(dups), "embedded_urls": embedded[:20]}, ensure_ascii=False),
    )
    _write_metadata_json(store.paths, capture_id, record)
    store.add_record(record)
    return record

# ---------------------------------------------------------------------------
# Processing / extraction (basic, pluggable-friendly)
# ---------------------------------------------------------------------------
EXTRACTOR_VERSION = "aj-inbox-basic/1"


def _write_extracted(store: InboxStore, capture_id: str, text: str, meta: Dict[str, Any]) -> Tuple[str, str]:
    txt_path = store.paths["extracted"] / f"{capture_id}.txt"
    meta_path = store.paths["extracted"] / f"{capture_id}.meta.json"
    tmp = txt_path.with_suffix(".tmp")
    tmp.write_text(text or "", encoding="utf-8")
    os.replace(tmp, txt_path)
    tmpm = meta_path.with_suffix(".tmp")
    tmpm.write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmpm, meta_path)
    return str(txt_path), str(meta_path)


def _extract_text_from_pdf(path: Path) -> Tuple[str, Dict[str, Any]]:
    errors_list = []
    available = {"pypdf": False, "pymupdf": False}
    try:
        from pypdf import PdfReader  # type: ignore
        available["pypdf"] = True
        reader = PdfReader(str(path))
        pages = []
        for i, pg in enumerate(reader.pages):
            try:
                pages.append(pg.extract_text() or "")
            except Exception as e:
                pages.append("")
                errors_list.append(f"page {i+1}: {e}")
        text = "\n\n".join(f"[Page {i+1}]\n{t}" for i, t in enumerate(pages)).strip()
        return text, {"extractor": "pypdf", "pages": len(reader.pages), "warnings": errors_list, "dependencies": available}
    except Exception as e:
        errors_list.append(f"pypdf: {e}")
    try:
        import fitz  # type: ignore
        available["pymupdf"] = True
        doc = fitz.open(str(path))
        pages = []
        for i in range(len(doc)):
            pages.append(doc.load_page(i).get_text() or "")
        text = "\n\n".join(f"[Page {i+1}]\n{t}" for i, t in enumerate(pages)).strip()
        return text, {"extractor": "pymupdf", "pages": len(doc), "warnings": errors_list, "dependencies": available}
    except Exception as e:
        errors_list.append(f"pymupdf: {e}")
    raise RuntimeError("Optional PDF extraction dependency unavailable (install pypdf or pymupdf). " + "; ".join(errors_list))


def _extract_youtube(url: str) -> Tuple[str, Dict[str, Any]]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Optional YouTube transcript dependency unavailable (install youtube-transcript-api): {e}")
    vid = None
    m = re.search(r"[?&]v=([^&]+)", url)
    if m:
        vid = m.group(1)
    if not vid:
        m = re.search(r"youtu\.be/([^?&/]+)", url)
        if m:
            vid = m.group(1)
    if not vid:
        raise RuntimeError("Could not determine YouTube video id")
    try:
        transcript = YouTubeTranscriptApi.get_transcript(vid)
    except Exception as e:
        try:
            transcript = YouTubeTranscriptApi().fetch(vid)
            transcript = [{"text": getattr(t,'text',str(t)), "start": getattr(t,'start',0), "duration": getattr(t,'duration',0)} for t in transcript]
        except Exception:
            raise RuntimeError(f"Transcript unavailable: {e}")
    lines = []
    for seg in transcript:
        start = seg.get("start", 0)
        text = seg.get("text", "")
        lines.append(f"[{start:.2f}s] {text}")
    return "\n".join(lines).strip(), {"extractor": "youtube_transcript_api", "video_id": vid, "segments": len(transcript)}


def process_capture(store: InboxStore, capture_id: str) -> Dict[str, Any]:
    rec = store.get(capture_id)
    if not rec:
        raise errors.AjError(f"capture not found: {capture_id}", code="capture_not_found")
    if rec.get("status") == ARCHIVED or rec.get("archived"):
        return rec
    if rec.get("status") in (READY, PROCESSED):
        return rec
    store.update_status(capture_id, PROCESSING, processing_started_at=utc_now(), error_details=None)
    rec = store.get(capture_id) or rec
    try:
        text, meta = "", {"note": "no extractor ran"}
        kind = rec.get("source_kind")
        platform = rec.get("source_platform") or ""
        mime = (rec.get("mime_type") or "").lower()
        src_path = Path(rec.get("source_path") or "") if rec.get("source_path") else None
        url = rec.get("source_url")

        if kind == "url" and url:
            if platform == "youtube":
                text, meta = _extract_youtube(url)
            elif platform == "instagram":
                meta = {"platform": "instagram", "status": "limited", "note": "Instagram media/transcript extraction not implemented; URL preserved."}
                text = f"[Instagram link captured]\n{url}\n\nExtraction of media/captions is unavailable via supported unauthenticated methods in this environment."
            else:
                try:
                    import urllib.request
                    req = urllib.request.Request(url, headers={"User-Agent": "AJ-Inbox/1.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        raw = resp.read(2_000_000)
                        ctype = resp.headers.get("Content-Type", "")
                    try:
                        body = raw.decode("utf-8", errors="replace")
                    except Exception:
                        body = raw.decode("latin-1", errors="replace")
                    body_text = re.sub(r"<script[\s\S]*?</script>", " ", body, flags=re.I)
                    body_text = re.sub(r"<style[\s\S]*?</style>", " ", body_text, flags=re.I)
                    body_text = re.sub(r"<[^>]+>", " ", body_text)
                    body_text = re.sub(r"\s+", " ", body_text).strip()
                    title_m = re.search(r"<title>(.*?)</title>", body, flags=re.I|re.S)
                    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
                    text = (f"Title: {title}\nURL: {url}\n\n{body_text[:50000]}").strip()
                    meta = {"extractor": "basic_web_fetch", "content_type": ctype, "bytes": len(raw), "title": title}
                except Exception as e:
                    text = f"[Webpage captured]\n{url}\n\nContent could not be fetched/extracted: {e}"
                    meta = {"extractor": "basic_web_fetch", "status": "failed", "error": str(e)}
        elif kind == "file" and src_path and src_path.exists():
            if mime == "application/pdf" or src_path.suffix.lower() == ".pdf":
                text, meta = _extract_text_from_pdf(src_path)
            elif mime.startswith("text/") or src_path.suffix.lower() in {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".log"}:
                try:
                    text = src_path.read_text(encoding="utf-8", errors="replace")
                    meta = {"extractor": "text_file"}
                except Exception as e:
                    raise RuntimeError(f"Could not read text file: {e}")
            elif mime.startswith("image/") or src_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
                text = f"[Image captured]\n{rec.get('original_filename')}\nPath: {src_path}\n"
                meta = {"extractor": "image_metadata_only", "note": "OCR/vision extraction not configured; original preserved.", "dependencies": {"ocr": False, "vision_provider": False}}
            else:
                text = f"[File captured]\n{rec.get('original_filename')}\nMIME: {mime}\nPath: {src_path}\n"
                meta = {"extractor": "generic_file", "note": "No specialized extractor for this type; original preserved."}
        elif kind == "text":
            text = (src_path.read_text(encoding="utf-8", errors="replace") if src_path and src_path.exists() else "")
            meta = {"extractor": "plain_text"}

        txt_path, meta_path = _write_extracted(store, capture_id, text, meta)
        store.update_status(
            capture_id, READY,
            processed_at=utc_now(),
            extractor_version=EXTRACTOR_VERSION,
            extracted_text_path=txt_path,
            extracted_meta_path=meta_path,
            error_details=None,
        )
        final = store.get(capture_id)
        if final:
            _write_metadata_json(store.paths, capture_id, final)
        return final or rec
    except Exception as e:
        store.update_status(capture_id, FAILED, processed_at=utc_now(), extractor_version=EXTRACTOR_VERSION, error_details=str(e))
        final = store.get(capture_id)
        if final:
            _write_metadata_json(store.paths, capture_id, final)
        return final or rec


def process_pending(store: InboxStore, limit: int = 20) -> List[Dict[str, Any]]:
    pending = store.list(status=QUEUED, limit=limit) + store.list(status=INCOMING, limit=limit)
    seen = set()
    ordered = []
    for r in pending:
        if r["capture_id"] not in seen:
            seen.add(r["capture_id"])
            ordered.append(r)
    results = []
    for r in ordered[:limit]:
        results.append(process_capture(store, r["capture_id"]))
    return results


def retry_failed(store: InboxStore, capture_id: str) -> Dict[str, Any]:
    rec = store.get(capture_id)
    if not rec:
        raise errors.AjError(f"capture not found: {capture_id}", code="capture_not_found")
    store.update_status(capture_id, QUEUED, error_details=None, processing_started_at=None, processed_at=None)
    return process_capture(store, capture_id)


def inbox_summary(store: InboxStore) -> Dict[str, Any]:
    counts = {}
    for st in [INCOMING, QUEUED, PROCESSING, READY, PROCESSED, FAILED, ARCHIVED]:
        counts[st] = len(store.list(status=st, include_archived=True, limit=10000))
    active = sum(counts[s] for s in [INCOMING, QUEUED, PROCESSING, READY, PROCESSED, FAILED])
    return {"counts": counts, "active": active, "root": str(store.root)}
