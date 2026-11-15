"""Regression tests for fail-closed path configuration handling."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aj import errors
from aj.config import load, memory_path, validate
from aj.runtime import assemble

AJ_ROOT = Path(__file__).resolve().parent.parent


def _isolated_env(tmp_path, **extra):
    env = {
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "AJ_CORE__DATA_DIR": str(tmp_path / "data"),
    }
    env.update({k: str(v) for k, v in extra.items()})
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tmp").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    return env


def _cli(tmp_path, *argv, env_extra=None):
    env = os.environ.copy()
    env.update(_isolated_env(tmp_path, **(env_extra or {})))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "aj", *argv],
        cwd=str(AJ_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize("value", ["none", "null", "None", "NULL"])
def test_invalid_audit_dir_fails_closed_before_write(tmp_path, value):
    env = _isolated_env(tmp_path, AJ_CORE__AUDIT_DIR=value)
    cfg = load(None, env=env)
    issues = validate(cfg)
    assert any("core.audit_dir" in issue for issue in issues)

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    with pytest.raises(errors.ConfigError):
        assemble(cfg)
    # Isolated execution directory must not receive unintended audit output.
    for root in (cwd, tmp_path):
        assert not (root / "None").exists()
        assert not (root / "none").exists()
        assert not (root / "null").exists()
        assert list(root.glob("**/events-*.jsonl")) == []
        assert list(root.glob("**/events-*.jsonl.lock")) == []


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_audit_dir_fails_closed(tmp_path, value):
    env = _isolated_env(tmp_path, AJ_CORE__AUDIT_DIR=value)
    cfg = load(None, env=env)
    issues = validate(cfg)
    assert any("core.audit_dir" in issue for issue in issues)
    with pytest.raises(errors.ConfigError):
        assemble(cfg)


def test_valid_explicit_audit_dir_still_works(tmp_path):
    audit_dir = tmp_path / "ok-audit"
    env = _isolated_env(tmp_path, AJ_CORE__AUDIT_DIR=str(audit_dir))
    cfg = load(None, env=env)
    assert validate(cfg) == []
    aj = assemble(cfg)
    try:
        outcome = aj.handle("hello", capability_id="aj.echo",
                            payload={"text": "hi"}, requester="test")
        assert outcome.ok
    finally:
        if aj.memory is not None:
            aj.memory.close()
    assert audit_dir.is_dir()
    assert any(audit_dir.glob("events-*.jsonl"))


@pytest.mark.parametrize("basename", ["none", "null"])
def test_valid_audit_dir_basename_literal_token_works(tmp_path, basename):
    audit_dir = tmp_path / basename
    env = _isolated_env(tmp_path, AJ_CORE__AUDIT_DIR=str(audit_dir))
    cfg = load(None, env=env)
    assert validate(cfg) == []
    aj = assemble(cfg)
    try:
        outcome = aj.handle("hello", capability_id="aj.echo",
                            payload={"text": "hi"}, requester="test")
        assert outcome.ok
    finally:
        if aj.memory is not None:
            aj.memory.close()
    assert audit_dir.is_dir()
    assert audit_dir.name == basename
    assert any(audit_dir.glob("events-*.jsonl"))


@pytest.mark.parametrize("field,env_key", [
    ("core.data_dir", "AJ_CORE__DATA_DIR"),
])
@pytest.mark.parametrize("value", ["none", "null", "", "   "])
def test_invalid_required_path_fields_fail_closed(tmp_path, field, env_key, value):
    base = _isolated_env(tmp_path)
    base[env_key] = value
    cfg = load(None, env=base)
    issues = validate(cfg)
    assert any(field in issue for issue in issues)
    with pytest.raises(errors.ConfigError):
        assemble(cfg)


@pytest.mark.parametrize("value", ["none", "null"])
def test_invalid_explicit_memory_path_fails_closed(tmp_path, value):
    env = _isolated_env(tmp_path, AJ_CORE__MEMORY_PATH=value)
    cfg = load(None, env=env)
    issues = validate(cfg)
    assert any("core.memory_path" in issue for issue in issues)
    with pytest.raises(errors.ConfigError):
        memory_path(cfg)


def test_empty_memory_path_still_derives_from_data_dir(tmp_path):
    env = _isolated_env(tmp_path)
    cfg = load(None, env=env)
    path = memory_path(cfg)
    assert path == Path(env["AJ_CORE__DATA_DIR"]) / "memory.sqlite3"


def test_cli_run_rejects_invalid_audit_dir_without_creating_none(tmp_path):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    env = os.environ.copy()
    env.update(_isolated_env(tmp_path, AJ_CORE__AUDIT_DIR="none"))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Run from an arbitrary cwd to assert no unintended audit output is created there,
    # but ensure the source-tree package is importable in the subprocess environment.
    env["PYTHONPATH"] = str(AJ_ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    proc = subprocess.run(
        [sys.executable, "-m", "aj", "--json", "run",
         "--capability", "aj.echo", "--text", "repro"],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "config_invalid"
    assert "core.audit_dir" in payload["error"]["message"]
    assert "path" in payload["error"]["message"].lower() or "null" in payload["error"]["message"].lower()
    assert not (cwd / "None").exists()
    assert not (cwd / "none").exists()
    assert list(cwd.glob("**/events-*.jsonl")) == []
    assert list(cwd.glob("**/events-*.jsonl.lock")) == []


def test_cli_config_check_reports_invalid_audit_dir(tmp_path):
    proc = _cli(tmp_path, "config", "--check", "--json",
                env_extra={"AJ_CORE__AUDIT_DIR": "none"})
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert any("core.audit_dir" in issue for issue in payload["issues"])
    assert proc.returncode == 5
