"""A local stand-in for the Supabase REST API, for persistence tests with isolated data.

It exists so a real app in a real browser can be tested against "the cloud" without touching
any real Supabase project: the app is pointed at it with SUITE_SUPABASE_URL / SUITE_SUPABASE_KEY
(environment only - no secrets file is read or written). Tables live in one JSON file, so the
"cloud" survives while the app server - and its local disk - is replaced, which is exactly what a
Streamlit Cloud restart or redeploy does.

It implements the subset of PostgREST the suite uses: select / filters (eq, neq, is, in, gt, gte,
lt, lte, like, ilike, JSON paths with -> and ->>), order, limit, insert, upsert
(resolution=merge-duplicates + on_conflict), PATCH, DELETE and Prefer return/count. Anything else
is answered 404 and logged, so a gap shows up instead of passing silently.

    python scripts/_fake_supabase.py <port> <db.json> <requests.jsonl>

The request log records method, table, filter NAMES, status and sizes - never row contents.
"""
from __future__ import annotations

import fnmatch
import json
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

PORT = int(sys.argv[1])
DB_PATH = Path(sys.argv[2])
LOG_PATH = Path(sys.argv[3])
LOCK = threading.Lock()
#: While this file exists, writes to the state table fail with 503 - a cloud outage, on demand.
FAIL_FLAG = Path(sys.argv[4]) if len(sys.argv) > 4 else None
#: Uploaded objects (the storage bucket) live here, beside the tables - they outlive the app server.
STORE_DIR = DB_PATH.parent / (DB_PATH.stem + "-storage")
RESERVED = {"select", "order", "limit", "offset", "on_conflict", "columns"}


def load_db() -> dict[str, list[dict]]:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8") or "{}")
    return {}


DB = load_db()


def save_db() -> None:
    tmp = DB_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(DB, sort_keys=True), encoding="utf-8")
    tmp.replace(DB_PATH)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def path_value(row: dict, expr: str):
    """Evaluate ``col``, ``col->a->b`` or ``col->a->>b`` against a row."""
    as_text = "->>" in expr
    parts = expr.replace("->>", "->").split("->")
    cur = row.get(parts[0])
    for p in parts[1:]:
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, list) and p.lstrip("-").isdigit():
            i = int(p)
            cur = cur[i] if -len(cur) <= i < len(cur) else None
        else:
            cur = None
    if as_text and cur is not None and not isinstance(cur, str):
        cur = json.dumps(cur) if isinstance(cur, (dict, list)) else str(cur).lower() if isinstance(cur, bool) else str(cur)
    return cur


def _cmp_cast(a, b: str):
    try:
        return float(a), float(b)
    except (TypeError, ValueError):
        return str(a), b


def matches(row: dict, key: str, raw: str) -> bool:
    negate = False
    if raw.startswith("not."):
        negate, raw = True, raw[4:]
    op, _, arg = raw.partition(".")
    val = path_value(row, key)
    if op == "eq":
        ok = val is not None and str(val if not isinstance(val, bool) else str(val).lower()) == arg
    elif op == "neq":
        ok = val is None or str(val) != arg
    elif op == "is":
        ok = (val is None) if arg == "null" else (val is (arg == "true"))
    elif op == "in":
        items = [x.strip().strip('"') for x in arg.strip("()").split(",") if x.strip()]
        ok = val is not None and str(val) in items
    elif op in ("gt", "gte", "lt", "lte"):
        if val is None:
            ok = False
        else:
            a, b = _cmp_cast(val, arg)
            ok = {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]
    elif op in ("like", "ilike"):
        pat = arg.replace("%", "*")
        s = "" if val is None else str(val)
        ok = fnmatch.fnmatchcase(s.lower(), pat.lower()) if op == "ilike" else fnmatch.fnmatchcase(s, pat)
    else:
        raise ValueError(f"unsupported operator {op}")
    return not ok if negate else ok


def project(row: dict, select: str) -> dict:
    if not select or select.strip() == "*":
        return dict(row)
    out = {}
    for col in [c.strip() for c in select.split(",") if c.strip()]:
        alias = None
        if ":" in col:
            alias, col = col.split(":", 1)
        name = alias or col.replace("->>", "->").split("->")[-1]
        out[name] = path_value(row, col)
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a):  # quiet
        pass

    def _log(self, status: int, table: str, params: list, body_len: int, out_len: int, note: str = ""):
        rec = {
            "t": round(time.time(), 3),
            "method": self.command,
            "table": table,
            "filters": sorted({k for k, _ in params if k not in RESERVED}),
            "status": status,
            "bytes_in": body_len,
            "bytes_out": out_len,
        }
        if note:
            rec["note"] = note
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    def _send(self, status: int, payload, headers: dict | None = None):
        data = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if data:
            self.wfile.write(data)
        return len(data)

    def _storage(self, path: str, raw_body: bytes, params: list) -> None:
        """/storage/v1/object[/authenticated]/<bucket>/<key>: bytes kept under STORE_DIR."""
        rest = path[len("/storage/v1/object/"):]
        for prefix in ("authenticated/", "public/"):
            if rest.startswith(prefix):
                rest = rest[len(prefix):]
        bucket, _, key = rest.partition("/")
        target = STORE_DIR / bucket / key
        if self.command in ("POST", "PUT"):
            data = raw_body
            ctype = self.headers.get("Content-Type") or ""
            if ctype.startswith("multipart/form-data"):
                from email.parser import BytesParser
                from email.policy import HTTP

                msg = BytesParser(policy=HTTP).parsebytes(
                    b"Content-Type: " + ctype.encode() + bytes([13, 10, 13, 10]) + raw_body)
                for part in msg.iter_parts():
                    if part.get_filename() or part.get_param("name", header="content-disposition") == "file":
                        data = part.get_payload(decode=True) or b""
                        break
            if target.exists() and "true" not in str(self.headers.get("x-upsert") or "").lower():
                n = self._send(400, {"statusCode": "409", "error": "Duplicate", "message": "exists"})
                self._log(400, "storage:" + bucket, params, len(raw_body), n, "duplicate")
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            n = self._send(200, {"Key": f"{bucket}/{key}", "Id": str(uuid.uuid4()), "path": key})
            self._log(200, "storage:" + bucket, params, len(raw_body), n, f"stored {len(data)} bytes")
            return
        if self.command == "GET":
            if not target.is_file():
                n = self._send(400, {"statusCode": "404", "error": "not_found", "message": "Object not found"})
                self._log(400, "storage:" + bucket, params, 0, n, "missing")
                return
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            self._log(200, "storage:" + bucket, params, 0, len(data), "served")
            return
        n = self._send(405, {"message": "method"})
        self._log(405, "storage:" + bucket, params, len(raw_body), n)

    def _handle(self):
        parts = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length) if length else b""
        params = parse_qsl(parts.query, keep_blank_values=True)
        if parts.path.startswith("/storage/v1/object/list/"):
            bucket = parts.path[len("/storage/v1/object/list/"):].strip("/")
            req = json.loads(raw_body.decode("utf-8") or "{}") if raw_body else {}
            folder = STORE_DIR / bucket / str(req.get("prefix") or "")
            search = str(req.get("search") or "")
            items = []
            if folder.is_dir() and not (FAIL_FLAG is not None and FAIL_FLAG.exists()):
                for f in sorted(folder.iterdir()):
                    if f.is_file() and (not search or search in f.name):
                        items.append({"name": f.name, "id": f.name, "metadata": {"size": f.stat().st_size}})
            n = self._send(200, items)
            self._log(200, "storage-list:" + bucket, params, len(raw_body), n, f"{len(items)} item(s)")
            return
        if (parts.path.startswith("/storage/v1/object/") and FAIL_FLAG is not None and FAIL_FLAG.exists()
                and self.command != "GET"):
            n = self._send(503, {"message": "simulated outage"})
            self._log(503, "storage", params, len(raw_body), n, "simulated outage")
            return
        if parts.path.startswith("/storage/v1/object/"):
            self._storage(parts.path, raw_body, params)
            return
        if not parts.path.startswith("/rest/v1/") or parts.path.startswith("/rest/v1/rpc/"):
            n = self._send(404, {"message": "not implemented by the fake"})
            self._log(404, parts.path[:40], params, len(raw_body), n, "unsupported path")
            return
        table = parts.path[len("/rest/v1/"):].strip("/")
        prefer = self.headers.get("Prefer") or ""
        q = dict(params)
        filters = [(k, v) for k, v in params if k not in RESERVED]
        if (FAIL_FLAG is not None and FAIL_FLAG.exists() and self.command != "GET"
                and table == "suite_app_current_state"):
            n = self._send(503, {"message": "simulated outage"})
            self._log(503, table, params, len(raw_body), n, "simulated outage")
            return
        with LOCK:
            rows = DB.setdefault(table, [])
            try:
                hit = [r for r in rows if all(matches(r, k, v) for k, v in filters)]
            except ValueError as exc:
                n = self._send(400, {"message": str(exc)})
                self._log(400, table, params, len(raw_body), n, str(exc))
                return
            if self.command == "GET":
                if q.get("order"):
                    for spec in reversed(q["order"].split(",")):
                        col, _, direction = spec.partition(".")
                        hit.sort(key=lambda r: (path_value(r, col) is None, str(path_value(r, col) or "")),
                                 reverse=direction.startswith("desc"))
                total = len(hit)
                off = int(q.get("offset") or 0)
                if q.get("limit"):
                    hit = hit[off: off + int(q["limit"])]
                else:
                    hit = hit[off:]
                out = [project(r, q.get("select", "*")) for r in hit]
                hdr = {"Content-Range": f"0-{max(len(out) - 1, 0)}/{total}"} if "count=" in prefer else {}
                n = self._send(200, out, hdr)
                self._log(200, table, params, 0, n)
                return
            body = json.loads(raw_body.decode("utf-8") or "null") if raw_body else None
            changed: list[dict] = []
            if self.command == "POST":
                items = body if isinstance(body, list) else [body or {}]
                conflict = [c for c in (q.get("on_conflict") or "").split(",") if c]
                for item in items:
                    item = dict(item)
                    existing = None
                    if "merge-duplicates" in prefer:
                        keys = conflict or ["id"]
                        for r in rows:
                            if all(r.get(k) == item.get(k) for k in keys):
                                existing = r
                                break
                    if existing is not None:
                        existing.update(item)
                        existing.setdefault("updated_at", now_iso())
                        changed.append(existing)
                    else:
                        item.setdefault("id", str(uuid.uuid4()))
                        item.setdefault("created_at", now_iso())
                        rows.append(item)
                        changed.append(item)
                status = 201
            elif self.command == "PATCH":
                for r in hit:
                    r.update(body or {})
                    changed.append(r)
                status = 200
            elif self.command == "DELETE":
                for r in hit:
                    rows.remove(r)
                    changed.append(r)
                status = 200
            else:
                n = self._send(405, {"message": "method"})
                self._log(405, table, params, len(raw_body), n)
                return
            save_db()
        payload = [dict(r) for r in changed] if "return=representation" in prefer else None
        hdr = {"Content-Range": f"0-{max(len(changed) - 1, 0)}/{len(changed)}"} if "count=" in prefer else {}
        if payload is None and status == 200:
            status = 204
        n = self._send(status, payload, hdr)
        self._log(status, table, params, len(raw_body), n, f"rows={len(changed)}")

    do_GET = do_POST = do_PATCH = do_DELETE = _handle


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"fake supabase on 127.0.0.1:{PORT} db={DB_PATH}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
