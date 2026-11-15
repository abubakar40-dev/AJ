import json
import os
import shutil
import stat
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
from aj.hermes_contract import CAPABILITY_STATUS_READ, CONTRACT_VERSION, redact_text
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
            "trust_mode": "local_trust",
            "principal_provenance": "local_trust_non_authenticated",
            "allowlist_entry_id": CAPABILITY_STATUS_READ,
        },
        "idempotency_key": "idem1",
    }
    base.update(overrides)
    return base


def _mk_script(tmp_path, name, body):
    p = tmp_path / name
    p.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body), encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return str(p)


def test_strict_config_fail_closed_on_invalid_values():
    # strict_config rejects invalid types/bounds; adapter construction fails closed
    with pytest.raises(Exception):
        HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", strict_config=True,
                               default_timeout_ms=-1)
    with pytest.raises(Exception):
        HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", strict_config=True,
                               max_timeout_ms=0)
    with pytest.raises(Exception):
        HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", strict_config=True,
                               stdout_max_bytes=-5)
    with pytest.raises(Exception):
        HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", strict_config=True,
                               default_timeout_ms="abc")
    with pytest.raises(Exception):
        HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", strict_config=True,
                               default_timeout_ms=5000, max_timeout_ms=1000)


def test_runtime_fail_closed_on_invalid_hermes_config(tmp_path):
    # explicit enablement with invalid config must not attach adapter
    cfg = load_config(overrides={
        "core": {"data_dir": str(tmp_path), "audit_dir": str(tmp_path / "audit")},
        "runtime": {"persist_memory": False, "persist_tasks": False},
        "feature_flags": {"hermes_execution_adapter": True},
        "execution": {
            "runtime": "hermes_cli",
            "hermes": {"enabled": True, "capability_status_read_enabled": True, "cli_path": "", "default_timeout_ms": -1},
        },
    })
    aj = assemble(cfg)
    assert aj.execution.available() is False
    assert aj.execution.describe().get("integration_status") in ("NOT ATTACHED", "disabled")


def test_cli_provenance_rejects_argument_like_and_invalid_path(monkeypatch):
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="-bad", runner=lambda *a, **k: RunnerResult(True,0,"","",False))
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "failed"
    assert res.output["error"]["class"] == "dependency_unavailable"
    ad2 = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="bad path", runner=lambda *a, **k: RunnerResult(True,0,"","",False))
    res2 = ad2.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res2.status == "failed"


def test_default_runner_bounds_output_during_collection_and_reports_truncation(tmp_path):
    script = _mk_script(tmp_path, "flood.py", r"""
import sys
sys.stdout.write('A' * 20000)
sys.stdout.flush()
sys.stderr.write('B' * 12000)
sys.stderr.flush()
""")
    rr = default_runner([sys.executable, script], timeout_s=3.0, stdout_max=1024, stderr_max=512, env=os.environ.copy())
    assert rr.started is True
    assert rr.timed_out is False
    assert rr.exit_code == 0
    assert len(rr.stdout.encode('utf-8', 'replace')) <= 1200  # capped + marker
    assert len(rr.stderr.encode('utf-8', 'replace')) <= 700
    assert rr.stdout_truncated is True
    assert rr.stderr_truncated is True
    assert "[truncated]" in rr.stdout


def test_default_runner_timeout_terminates_and_collects_partial(tmp_path):
    script = _mk_script(tmp_path, "hang.py", r"""
import sys, time
print('partial-before-hang', flush=True)
time.sleep(10)
print('after', flush=True)
""")
    t0 = time.time()
    rr = default_runner([sys.executable, script], timeout_s=0.4, stdout_max=2048, stderr_max=512, env=os.environ.copy())
    dt = time.time() - t0
    assert rr.started is True
    assert rr.timed_out is True
    assert dt < 5.0
    assert "partial-before-hang" in rr.stdout
    assert "after" not in rr.stdout


def test_default_runner_nonzero_and_signal_classification(tmp_path):
    script = _mk_script(tmp_path, "fail.py", r"""
import sys
sys.stderr.write('boom\n')
sys.exit(7)
""")
    rr = default_runner([sys.executable, script], timeout_s=2.0, stdout_max=1024, stderr_max=1024, env=os.environ.copy())
    assert rr.started and rr.exit_code == 7 and rr.timed_out is False

    # simulate signal via injected runner result mapping in adapter
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes",
                                runner=lambda *a, **k: RunnerResult(True, -15, "x", "", False, None, False, False, False, 15))
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "failed"
    assert "signal 15" in res.output["error"]["message"]


def test_malformed_encoding_empty_output_and_unknown_honesty(tmp_path):
    script = _mk_script(tmp_path, "bin.py", r"""
import sys
sys.stdout.buffer.write(b'\xff\xfe\x00bad\n')
""")
    rr = default_runner([sys.executable, script], timeout_s=2.0, stdout_max=1024, stderr_max=1024, env=os.environ.copy())
    assert rr.started is True
    assert isinstance(rr.stdout, str)

    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes",
                                runner=lambda *a, **k: RunnerResult(True, 1, "", "", False, None))
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "failed"
    assert res.output["accepted"] is True


def test_redaction_patterns_best_effort():
    samples = [
        "Authorization: Bearer abc.def+ghi/jkl==",
        "api_key=sk-live-secret token: tok123 password=hunter2",
        "https://user:supersecret@example.com/path?q=1",
        "OPENAI_API_KEY=sk-test-123 SESSION_ID=sess-999",
    ]
    for s in samples:
        red = redact_text(s, limit=2000)
        assert "supersecret" not in red
        assert "hunter2" not in red
        assert "sk-live-secret" not in red
        assert "tok123" not in red or "[REDACTED]" in red
        assert "sess-999" not in red
        assert "[REDACTED]" in red


def test_repeated_bounded_probes_consistent(tmp_path, monkeypatch):
    # deterministic repeated read-only probes via injected runner (no live hermes dependency)
    calls = {"n": 0}
    def runner(argv, timeout_s, stdout_max, stderr_max, env):
        calls["n"] += 1
        return RunnerResult(True, 0, "Gateway: running\n", "", False, None)
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", runner=runner)
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    statuses = []
    for i in range(5):
        res = ad.execute(ExecutionRequest(request_id=f"r{i}", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args(operation_id=f"op{i}", attempt_id=f"att{i}", correlation_id=f"c{i}")))
        assert res.status == "completed"
        assert res.output["hermes_execution_id"] is None
        statuses.append(res.output["status"])
    assert calls["n"] == 5
    assert all(s == "completed" for s in statuses)


def test_evidence_honesty_no_false_success_no_fabricated_id(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes",
                                runner=lambda *a, **k: RunnerResult(True, None, "partial", "", True, "timeout", False, False, True, None))
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "timeout"
    assert res.ok is False
    assert res.output["status"] == "timeout"
    assert res.output["hermes_execution_id"] is None
    assert res.output["accepted"] is True
    assert res.output["result_payload"]["partial"] is True
