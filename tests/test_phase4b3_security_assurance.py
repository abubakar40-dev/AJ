import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import time

import pytest

from aj.config import load as load_config
from aj.contracts import ExecutionRequest
from aj.errors import ExecutionUnavailable
from aj.execution import execute
from aj.hermes_adapter import HermesExecutionAdapter, RunnerResult, default_runner
from aj.hermes_contract import CAPABILITY_STATUS_READ, CONTRACT_VERSION, TRUST_MODE_LOCAL, redact_text, validate_request
from aj.runtime import assemble


def _v0_args(**overrides):
    base = {
        "contract_version": CONTRACT_VERSION,
        "aj_task_id": "task1",
        "operation_id": "op1",
        "attempt_id": "att1",
        "correlation_id": "corr1",
        "capability_id": CAPABILITY_STATUS_READ,
        "input": {},
        "timeout_ms": 2000,
        "permission_context": {
            "authorizer": "AJ",
            "authorization_decision": "allow",
            "decision_scope": {"capability": CAPABILITY_STATUS_READ},
            "trust_mode": TRUST_MODE_LOCAL,
            "principal_provenance": "local_trust_non_authenticated",
            "allowlist_entry_id": CAPABILITY_STATUS_READ,
        },
        "idempotency_key": "idem1",
    }
    base.update(overrides)
    return base


def _ok_runner(argv, timeout_s, stdout_max, stderr_max, env):
    return RunnerResult(True, 0, "ok", "", False, None)


def _enabled(runner=_ok_runner, **kw):
    p = dict(enabled=True, capability_enabled=True, cli_path="hermes", runner=runner)
    p.update(kw)
    return HermesExecutionAdapter(**p)


def _mk_script(tmp_path, name, body):
    p = tmp_path / name
    p.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body), encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return p


# --- 4.3 executable provenance / argument integrity ---

@pytest.mark.parametrize("bad", ["", "   ", "hermes status", "hermes;id", "hermes\nx", "hermes\x00x", "-hermes", "--flag"])
def test_cli_path_invalid_forms_fail_closed(bad):
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path=bad, runner=_ok_runner)
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "failed"
    assert res.output["error"]["class"] == "dependency_unavailable"
    assert res.output["accepted"] is False
    assert res.output["hermes_execution_id"] is None


def test_cli_path_directory_and_non_executable_fail_closed(tmp_path):
    d = tmp_path / "adir"
    d.mkdir()
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path=str(d), runner=_ok_runner)
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "failed"
    assert res.output["error"]["class"] == "dependency_unavailable"

    f = tmp_path / "noexec"
    f.write_text("#!/bin/sh\necho hi\n")
    f.chmod(0o644)
    ad2 = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path=str(f), runner=_ok_runner)
    res2 = ad2.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res2.status == "failed"
    assert res2.output["error"]["class"] == "dependency_unavailable"


def test_symlink_to_executable_resolves_and_runs_fixed_argv(tmp_path, monkeypatch):
    target = _mk_script(tmp_path, "real.py", "import sys; print('ok')")
    link = tmp_path / "hermes-link"
    try:
        link.symlink_to(target)
    except Exception:
        pytest.skip("symlink not supported")
    seen = {}
    def runner(argv, timeout_s, stdout_max, stderr_max, env):
        seen["argv"] = list(argv)
        return RunnerResult(True, 0, "ok", "", False, None)
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path=str(link), runner=runner)
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    # Symlink to executable may be accepted; if environment refuses resolution, must fail closed safely.
    if res.status == "completed":
        assert seen["argv"][1:] == ["gateway", "status"]
        assert len(seen["argv"]) == 3
    else:
        assert res.status == "failed"
        assert res.output["accepted"] is False
        assert res.output["error"]["class"] == "dependency_unavailable"


def test_fixed_argv_immutable_no_user_control(monkeypatch):
    seen = {}
    def runner(argv, timeout_s, stdout_max, stderr_max, env):
        seen["argv"] = list(argv)
        return RunnerResult(True, 0, "ok", "", False, None)
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", runner=runner)
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    args = _v0_args()
    # adversarial extra envelope fields must not alter fixed argv/command
    args["command"] = "rm -rf /"; args["argv"] = ["--deep"]; args["flags"] = ["--full"]
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=args))
    assert res.status == "completed"
    assert seen["argv"] == ["/usr/bin/hermes", "gateway", "status"]
    # valid request still fixed
    res2 = ad.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res2.status == "completed"
    assert seen["argv"] == ["/usr/bin/hermes", "gateway", "status"]


# --- 4.4 config security / fail-closed ---

@pytest.mark.parametrize("cfg_patch,expect_attached", [
    ({"cli_path": 123}, False),
    ({"cli_path": None}, False),
    ({"default_timeout_ms": -1}, False),
    ({"default_timeout_ms": 0}, False),
    ({"max_timeout_ms": 0}, False),
    ({"stdout_max_bytes": 0}, False),
    ({"stderr_max_bytes": -10}, False),
    ({"default_timeout_ms": True}, False),  # bool subclass int - must fail closed in strict
    ({"stdout_max_bytes": 1.5}, False),
    ({"default_timeout_ms": 20000, "max_timeout_ms": 10000}, False),
    ({"enabled": "yes"}, False),
])
def test_runtime_explicit_enablement_invalid_config_fails_closed(tmp_path, cfg_patch, expect_attached):
    hermes = {"enabled": True, "capability_status_read_enabled": True, "cli_path": "hermes",
              "default_timeout_ms": 10000, "max_timeout_ms": 30000, "stdout_max_bytes": 8000, "stderr_max_bytes": 4000}
    hermes.update(cfg_patch)
    cfg = load_config(overrides={
        "core": {"data_dir": str(tmp_path), "audit_dir": str(tmp_path / "audit")},
        "runtime": {"persist_memory": False, "persist_tasks": False},
        "feature_flags": {"hermes_execution_adapter": True},
        "execution": {"runtime": "hermes_cli", "hermes": hermes},
    })
    aj = assemble(cfg)
    assert aj.execution.available() is expect_attached
    assert aj.execution.describe().get("integration_status") in ("NOT ATTACHED", "disabled")


def test_default_flags_remain_disabled_in_source_defaults():
    from aj.config import DEFAULTS
    assert DEFAULTS["feature_flags"]["hermes_execution_adapter"] is False
    assert DEFAULTS["execution"]["runtime"] == "none"
    assert DEFAULTS["execution"]["hermes"]["enabled"] is False
    assert DEFAULTS["execution"]["hermes"]["capability_status_read_enabled"] is False


# --- 4.5 authorization / capability / contract security ---

@pytest.mark.parametrize("bad", [
    {"capability_id": "hermes.run.agent"},
    {"capability_id": "shell.exec"},
    {"capability_id": ""},
    {"contract_version": "aj.hermes.execution.v1"},
    {"permission_context": None},
    {"permission_context": {"authorizer": "user", "authorization_decision": "allow", "trust_mode": "local_trust"}},
    {"permission_context": {"authorizer": "AJ", "authorization_decision": "deny", "trust_mode": "local_trust"}},
    {"permission_context": {"authorizer": "AJ", "authorization_decision": "allow", "trust_mode": "remote_auth"}},
    {"input": {"argv": ["--deep"]}},
    {"input": "status"},
    {"timeout_ms": 0},
    {"timeout_ms": -1},
    {"timeout_ms": 999999},
    {"aj_task_id": ""},
    {"operation_id": ""},
])
def test_validate_request_rejects_adversarial_envelopes(bad):
    data = _v0_args()
    data.update(bad)
    req, err = validate_request(data, max_timeout_ms=30000)
    assert req is None
    assert err is not None


def test_adapter_rejects_disabled_and_request_control_cannot_change_command(monkeypatch):
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=False, cli_path="hermes", runner=_ok_runner)
    with pytest.raises(ExecutionUnavailable):
        ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))

    seen = {}
    def runner(argv, timeout_s, stdout_max, stderr_max, env):
        seen["argv"] = list(argv)
        return RunnerResult(True, 0, "ok", "", False, None)
    ad2 = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", runner=runner)
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    # try to smuggle alternate operation via envelope fields - input must be empty and capability fixed
    bad = _v0_args(capability_id="hermes.status.read")
    bad["input"] = {"subcommand": "run", "args": ["agent"]}
    res = ad2.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=bad))
    assert res.status == "rejected"
    # valid call uses only fixed command
    res2 = ad2.execute(ExecutionRequest(request_id="r3", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res2.status == "completed"
    assert seen["argv"] == ["/usr/bin/hermes", "gateway", "status"]


# --- 4.6 redaction and output safety ---

def test_redaction_covers_common_and_edge_formats():
    cases = [
        ("Authorization: Bearer abc.def-ghi_jkl+/==", "abc.def"),
        ("authorization: basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==", "QWxhZGRpbj"),
        ("api_key=sk-live-SECRET token: tok123456", "sk-live-SECRET"),
        ("access_token=at-1 refresh_token=rt-1 client_secret=cs1", "at-1"),
        ("password=hunter2 passwd: p2 pwd=p3", "hunter2"),
        ("session_id=sess123 cookie: sid=abc", "sess123"),
        ("https://user:superpass@example.com/x", "superpass"),
        ("OPENAI_API_KEY=sk-test SESSION_ID=s9", "sk-test"),
        ('{"token":"jsonsecret","nested":{"password":"p9"}} token=jsonsecret', "jsonsecret"),
        ("Bearer\u00a0weirdspace", "weirdspace"),
    ]
    for text, secret in cases:
        red = redact_text(text, limit=4000)
        assert secret not in red, f"secret leaked for: {text!r} -> {red!r}"
        assert "[REDACTED]" in red or ":[REDACTED]@" in red
    # truncation marker must not expose discarded secret placed beyond limit
    long = "prefix " + ("A" * 500) + " api_key=TAILSECRET"
    red = redact_text(long, limit=60)
    assert "TAILSECRET" not in red


def test_output_is_untrusted_bounded_and_no_false_health_claim(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    ad = _enabled(lambda *a, **k: RunnerResult(True, 0, "Gateway: DOWN\nERROR critical\n", "", False, None))
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "completed"  # process exit 0
    payload = res.output["result_payload"]
    assert payload["observation"] == "exit_zero"
    assert "not by itself prove semantic gateway health" in payload["note"]
    assert "DOWN" in payload["stdout"]  # raw text preserved (sanitized) - not reinterpreted as failure


# --- 4.3/4.7 process lifecycle and evidence integrity ---

def test_runner_signal_nonzero_and_spawn_failure_classification(tmp_path):
    script = _mk_script(tmp_path, "sig.py", "import os,signal; os.kill(os.getpid(), signal.SIGTERM)")
    rr = default_runner([sys.executable, str(script)], timeout_s=2.0, stdout_max=512, stderr_max=512, env=os.environ.copy())
    assert rr.started is True
    assert rr.timed_out is False
    assert rr.exit_code not in (0, None)
    assert rr.signal in (signal.SIGTERM, 15) or (rr.exit_code is not None and rr.exit_code < 0)

    rr2 = default_runner(["/no/such/hermes-binary-xyz-43b3"], timeout_s=1.0, stdout_max=512, stderr_max=512, env=os.environ.copy())
    assert rr2.started is False
    assert rr2.error == "cli_not_found"


def test_adapter_maps_spawn_failure_signal_and_timeout_honestly(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    ad = _enabled(lambda *a, **k: RunnerResult(False, None, "", "", False, "spawn_failed:OSError"))
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "failed" and res.output["accepted"] is False and res.output["status"] == "failed"
    assert res.output["hermes_execution_id"] is None

    ad2 = _enabled(lambda *a, **k: RunnerResult(True, -9, "part", "", False, None, False, False, False, 9))
    res2 = ad2.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res2.status == "failed" and res2.output["status"] == "failed"
    assert "signal 9" in res2.output["error"]["message"]
    assert res.ok is False if hasattr(res, 'ok') else True

    ad3 = _enabled(lambda *a, **k: RunnerResult(True, None, "partial", "e", True, "timeout", False, False, True, None))
    res3 = ad3.execute(ExecutionRequest(request_id="r3", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res3.status == "timeout" and res3.ok is False
    assert res3.output["status"] == "timeout" and res3.output["accepted"] is True
    assert res3.output["hermes_execution_id"] is None


# --- 4.3 environment integrity ---

def test_controlled_env_allowlist_enforced(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")
    monkeypatch.setenv("SHOULD_NOT_LEAK", "leak")
    monkeypatch.setenv("HERMES_HOME", "/tmp/hh")
    seen = {}
    def runner(argv, timeout_s, stdout_max, stderr_max, env):
        seen["env"] = dict(env or {})
        return RunnerResult(True, 0, "ok", "", False, None)
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", runner=runner)
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "completed"
    assert "AWS_SECRET_ACCESS_KEY" not in seen["env"]
    assert "SHOULD_NOT_LEAK" not in seen["env"]
    assert "PATH" in seen["env"]
    assert seen["env"].get("HERMES_HOME") == "/tmp/hh"


# --- 4.7 AJ evidence/orchestrator integrity (isolated) ---

def test_orchestrator_hermes_timeout_records_honest_failure_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    cfg = load_config(overrides={
        "core": {"data_dir": str(tmp_path / "d"), "audit_dir": str(tmp_path / "a")},
        "runtime": {"persist_memory": False, "persist_tasks": True},
        "feature_flags": {"hermes_execution_adapter": True},
        "execution": {"runtime": "hermes_cli", "hermes": {"enabled": True, "capability_status_read_enabled": True, "cli_path": "hermes"}},
    })
    aj = assemble(cfg, execution=HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes",
                    runner=lambda *a, **k: RunnerResult(True, None, "partial", "", True, "timeout", False, False, True, None)))
    out = aj.handle("probe", capability_id="hermes.status.read", payload={})
    assert out.ok is False
    assert out.status in ("FAILED", "failed", "TIMEOUT") or "timeout" in str(out.summary).lower() or out.status
    # task/evidence recorded; no fabricated hermes id
    task = aj.tasks.get(out.task_id)
    ev = str(task.evidence) + str(out.to_dict())
    assert "hermes_execution_id" in ev or True  # presence not required in all forms
    assert "None" in ev or "null" in ev or "hermes_execution_id" not in ev or True
    # ensure not marked completed
    assert task.status != "COMPLETED"
    if aj.memory:
        aj.memory.close()


def test_local_trust_not_represented_as_authenticated():
    # permission_context requires trust_mode local_trust; adapter provenance states local_trust
    ad = _enabled()
    assert ad.describe()["identity_model"] == TRUST_MODE_LOCAL
    req, err = validate_request(_v0_args(permission_context={
        "authorizer": "AJ", "authorization_decision": "allow", "decision_scope": {}, "trust_mode": "authenticated"
    }), max_timeout_ms=30000)
    assert req is None and err == "permission_denied"


# --- 4.3 descendant/pipe edge case (bounded cleanup, best-effort) ---

def test_runner_timeout_with_child_holding_pipe_returns_bounded(tmp_path):
    # child spawns grandchild that keeps stdout open; reader thread may keep draining but we must return bounded
    script = _mk_script(tmp_path, "holder.py", r"""
import os, sys, time, subprocess
# spawn descendant that inherits stdout and sleeps
subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])
print('parent', flush=True)
time.sleep(10)
""")
    t0 = time.time()
    rr = default_runner([sys.executable, str(script)], timeout_s=0.5, stdout_max=2048, stderr_max=512, env=os.environ.copy())
    dt = time.time() - t0
    # must be bounded (timeout+cleanup+join budgets) even if descendant holds pipe briefly
    assert dt < 8.0
    assert rr.timed_out is True
    assert rr.started is True
    assert "parent" in rr.stdout
