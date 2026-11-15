#!/usr/bin/env python3
"""S0 Part 2C: SQLite/WAL experiment matrix (no changes to aj/memory.py).

Variants:
  1. 4 forked processes, WAL not pre-created
  2. WAL pre-created once in the parent before forking
  3. 1 process
  4. spawn instead of fork

Path types:
  - /tmp (tmpfs on this host; recorded factually)
  - temp dir on ext4 under ~
  - /dev/shm
  - NTFS workspace under repo

20 runs per cell.
Records pass/fail, first failing traceback/line, error text, journal_mode readback,
findmnt, sqlite version. Facts and clearly-labelled HYPOTHESES only.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aj.memory import MemoryStore  # noqa: E402

WORKERS = 4
PER_WORKER = 20
RUNS = 20


def memory_writer(path: str, count: int, q=None):
    try:
        store = MemoryStore(path)
        try:
            for i in range(count):
                store.append_event("probe", f"event {i}", source="worker")
        finally:
            store.close()
        if q is not None:
            q.put({"ok": True})
    except Exception as e:
        tb = traceback.format_exc()
        if q is not None:
            q.put({"ok": False, "error": f"{type(e).__name__}: {e}", "traceback": tb})
        else:
            raise


def run_variant(path: str, variant: str):
    """Run one experiment instance. Returns result dict."""
    res = {"ok": False, "error": None, "traceback": None, "first_failing_line": None,
           "journal_mode": None, "integrity": None, "events": None}
    ctx_name = "fork"
    procs = 1
    precreate = False
    if variant == "v1_fork4_no_precreate":
        ctx_name, procs, precreate = "fork", 4, False
    elif variant == "v2_fork4_precreate":
        ctx_name, procs, precreate = "fork", 4, True
    elif variant == "v3_1proc":
        ctx_name, procs, precreate = "fork", 1, False
    elif variant == "v4_spawn4_no_precreate":
        ctx_name, procs, precreate = "spawn", 4, False
    else:
        raise ValueError(variant)

    try:
        if precreate:
            # pre-create WAL in parent before forking
            s = MemoryStore(path)
            s.append_event("probe", "parent-precreate", source="parent")
            s.close()

        if procs == 1:
            memory_writer(path, PER_WORKER)
        else:
            ctx = mp.get_context(ctx_name)
            qs = [ctx.Queue() for _ in range(procs)]
            processes = [ctx.Process(target=memory_writer, args=(path, PER_WORKER, qs[i])) for i in range(procs)]
            for p in processes:
                p.start()
            child_results = []
            for i, p in enumerate(processes):
                p.join(30)
                # collect queue
                try:
                    while not qs[i].empty():
                        child_results.append(qs[i].get_nowait())
                except Exception:
                    pass
                if p.exitcode != 0:
                    child_results.append({"ok": False, "error": f"exitcode={p.exitcode}", "traceback": None})
            bad = [r for r in child_results if not r.get("ok", False)]
            if bad:
                # pick first failure info
                b = bad[0]
                res["error"] = b.get("error")
                res["traceback"] = b.get("traceback")
            elif any(p.exitcode != 0 for p in processes):
                res["error"] = f"nonzero exitcodes: {[p.exitcode for p in processes]}"
            else:
                res["ok"] = True
        # verify readable and count if init/writes seemed ok so far for single-proc path
        if procs == 1:
            # verify
            store = MemoryStore(path)
            try:
                events = store.events(limit=10_000)
                res["events"] = len(events)
                # parent precreate in v2 not used here; expected count PER_WORKER
                expected = PER_WORKER + (1 if precreate else 0)
                if len(events) != expected:
                    res["ok"] = False
                    res["error"] = res["error"] or f"count_mismatch expected={expected} got={len(events)}"
                else:
                    res["ok"] = True
            finally:
                store.close()
        elif res["ok"]:
            store = MemoryStore(path)
            try:
                events = store.events(limit=10_000)
                res["events"] = len(events)
                expected = procs * PER_WORKER + (1 if precreate else 0)
                if len(events) != expected:
                    res["ok"] = False
                    res["error"] = f"count_mismatch expected={expected} got={len(events)}"
            finally:
                store.close()
    except Exception as e:
        res["ok"] = False
        res["error"] = res["error"] or f"{type(e).__name__}: {e}"
        res["traceback"] = res["traceback"] or traceback.format_exc()

    # journal_mode readback / integrity if possible
    try:
        conn = sqlite3.connect(path, timeout=5.0)
        try:
            res["journal_mode"] = conn.execute("PRAGMA journal_mode").fetchone()[0]
            res["integrity"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
    except Exception as e:
        res["journal_mode"] = res.get("journal_mode") or f"read_error:{type(e).__name__}:{e}"

    tb = res.get("traceback") or ""
    if tb:
        for line in tb.splitlines():
            if "memory.py" in line or "PRAGMA journal_mode" in line:
                res["first_failing_line"] = line.strip()
                break
        if not res["first_failing_line"]:
            # include first non-empty traceback line
            for line in tb.splitlines():
                if line.strip():
                    res["first_failing_line"] = line.strip()
                    break
    if not res.get("first_failing_line") and res.get("error") and "journal_mode" in str(res.get("error")):
        res["first_failing_line"] = "expected: aj/memory.py:116 (PRAGMA journal_mode=WAL) [inferred from error text]"
    return res


def findmnt(path: Path):
    try:
        out = subprocess.check_output(["findmnt", "-T", str(path)], text=True, stderr=subprocess.STDOUT)
        return out.strip()
    except Exception as e:
        return f"findmnt_error:{e}"


def main():
    ws = Path("/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ")
    ntfs_dir = ws / "ENGINEERING_AUDIT" / "S0_CLOSURE" / "_sqlite_exp_ntfs"
    ntfs_dir.mkdir(parents=True, exist_ok=True)

    home_ext4 = Path.home() / "aj_s0_sqlite_ext4"
    home_ext4.mkdir(parents=True, exist_ok=True)

    shm_dir = Path("/dev/shm/aj_s0_sqlite")
    shm_dir.mkdir(parents=True, exist_ok=True)

    tmp_base = Path(tempfile.mkdtemp(prefix="aj_s0_sqlite_", dir="/tmp"))

    path_types = {
        "tmp_tmpfs_or_tmp": {"dir": tmp_base, "note": "/tmp tempdir (filesystem recorded by findmnt/stat)"},
        "home_ext4": {"dir": home_ext4, "note": "temp dir on ext4 under ~"},
        "dev_shm": {"dir": shm_dir, "note": "/dev/shm tmpfs"},
        "ntfs_workspace": {"dir": ntfs_dir, "note": "NTFS workspace path under AJ/ENGINEERING_AUDIT/S0_CLOSURE"},
    }
    variants = ["v1_fork4_no_precreate", "v2_fork4_precreate", "v3_1proc", "v4_spawn4_no_precreate"]

    meta = {
        "sqlite_version": sqlite3.sqlite_version,
        "python": sys.version,
        "pid": os.getpid(),
        "cwd": os.getcwd(),
        "findmnt": {k: findmnt(v["dir"]) for k, v in path_types.items()},
        "df_T": {},
    }
    for k, v in path_types.items():
        try:
            meta["df_T"][k] = subprocess.check_output(["df", "-T", str(v["dir"])], text=True, stderr=subprocess.STDOUT).strip()
        except Exception as e:
            meta["df_T"][k] = str(e)

    # real AJ memory location
    try:
        from aj.config import load as load_config
        cfg = load_config(None, env={})
        meta["real_memory_config"] = {
            "core.memory_path": cfg.get("core.memory_path", ""),
            "core.data_dir": cfg.get("core.data_dir", ""),
        }
    except Exception as e:
        meta["real_memory_config_error"] = str(e)

    results = {"meta": meta, "cells": {}}
    total = len(path_types) * len(variants) * RUNS
    done = 0
    t0 = time.time()
    for pk, pinfo in path_types.items():
        for var in variants:
            cell = {"path_type": pk, "variant": var, "runs": [], "pass": 0, "fail": 0, "first_failure": None}
            for i in range(RUNS):
                db = Path(pinfo["dir"]) / f"{pk}__{var}__run{i}.sqlite3"
                # cleanup previous
                for suf in ("", "-wal", "-shm"):
                    try:
                        os.remove(str(db) + suf)
                    except FileNotFoundError:
                        pass
                r = run_variant(str(db), var)
                run_rec = {
                    "run": i,
                    "ok": r.get("ok"),
                    "error": r.get("error"),
                    "first_failing_line": r.get("first_failing_line"),
                    "journal_mode": r.get("journal_mode"),
                    "integrity": r.get("integrity"),
                    "events": r.get("events"),
                }
                if r.get("traceback"):
                    # keep traceback compact but present in per-run record (facts)
                    run_rec["traceback_tail"] = "\n".join((r.get("traceback") or "").splitlines()[-12:])
                cell["runs"].append(run_rec)
                if r.get("ok"):
                    cell["pass"] += 1
                else:
                    cell["fail"] += 1
                    if cell["first_failure"] is None:
                        cell["first_failure"] = run_rec
                done += 1
                # cleanup db files to reduce clutter
                for suf in ("", "-wal", "-shm"):
                    try:
                        os.remove(str(db) + suf)
                    except FileNotFoundError:
                        pass
            results["cells"][f"{pk}::{var}"] = cell
            print(f"CELL {pk}::{var} pass={cell['pass']} fail={cell['fail']}", flush=True)

    results["meta"]["elapsed_seconds"] = round(time.time() - t0, 3)
    out_json = ws / "ENGINEERING_AUDIT" / "S0_CLOSURE" / "sqlite_wal_matrix_results.json"
    out_txt = ws / "ENGINEERING_AUDIT" / "S0_CLOSURE" / "sqlite_wal_matrix_summary.txt"
    out_json.write_text(json.dumps(results, indent=2, default=str))
    # text summary
    lines = []
    lines.append(f"sqlite_version={meta['sqlite_version']}")
    lines.append(f"elapsed_seconds={results['meta']['elapsed_seconds']}")
    lines.append("FINDMNT:")
    for k, v in meta["findmnt"].items():
        lines.append(f"[{k}]\n{v}\n")
    lines.append("CELLS:")
    for k, c in results["cells"].items():
        lines.append(f"{k}: pass={c['pass']} fail={c['fail']}")
        if c["first_failure"]:
            ff = c["first_failure"]
            lines.append(f"  first_failure run={ff['run']} error={ff.get('error')} line={ff.get('first_failing_line')} journal_mode={ff.get('journal_mode')}")
    out_txt.write_text("\n".join(lines))
    print("WROTE", out_json)
    print("WROTE", out_txt)


if __name__ == "__main__":
    # safer start method availability handled per-variant
    main()
