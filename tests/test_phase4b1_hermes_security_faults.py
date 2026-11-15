import shutil

from aj.contracts import ExecutionRequest
from aj.hermes_adapter import HermesExecutionAdapter, RunnerResult
from aj.hermes_contract import CAPABILITY_STATUS_READ, CONTRACT_VERSION


def _v0_args(**overrides):
    base = {
        "contract_version": CONTRACT_VERSION,
        "aj_task_id": "task1",
        "operation_id": "op1",
        "attempt_id": "att1",
        "correlation_id": "corr1",
        "capability_id": CAPABILITY_STATUS_READ,
        "input": {},
        "timeout_ms": 5000,
        "permission_context": {
            "authorizer": "AJ",
            "authorization_decision": "allow",
            "decision_scope": {"capability": CAPABILITY_STATUS_READ},
            "trust_mode": "local_trust",
            "principal_provenance": "local_trust_non_authenticated",
            "allowlist_entry_id": CAPABILITY_STATUS_READ,
        },
    }
    base.update(overrides)
    return base


def _enabled(runner):
    return HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", runner=runner)


def _ok(argv, timeout_s, stdout_max, stderr_max, env):
    return RunnerResult(True, 0, "ok", "", False, None)


def test_rejects_shell_injection_and_arbitrary_cli_path(monkeypatch):
    # cli_path with spaces/args is invalid (prevents injection via config)
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes; rm -rf /", runner=_ok)
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "failed"
    assert res.output["error"]["class"] == "dependency_unavailable"
    # even if caller tries to smuggle args in input/capability, validation rejects
    ad2 = _enabled(_ok)
    smuggle = _v0_args()
    smuggle["input"] = {"argv": ["bash", "-c", "echo pwned"]}
    res2 = ad2.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=smuggle))
    assert res2.status == "rejected"


def test_unknown_capability_permission_bypass_and_feature_bypass(monkeypatch):
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", runner=_ok)
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    for cap in ["shell.exec", "hermes.tool.run", "filesystem.write", "messaging.send"]:
        res = ad.execute(ExecutionRequest(request_id="r", capability_id=cap, arguments=_v0_args(capability_id=cap)))
        assert res.status == "rejected"
        assert res.output["error"]["class"] in ("capability_not_allowed", "request_invalid", "contract_version_unsupported")
    # capability flag off => adapter unavailable (cannot execute)
    ad_off = HermesExecutionAdapter(enabled=True, capability_enabled=False, cli_path="hermes", runner=_ok)
    assert ad_off.available() is False


def test_malformed_empty_and_partial_outputs_are_honest(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    # malformed/unstructured text is still captured as untrusted bounded output, not interpreted as success semantics beyond exit
    def weird(argv, timeout_s, stdout_max, stderr_max, env):
        return RunnerResult(True, 0, "\x00\x01not-json<<<>>>", "", False, None)
    ad = _enabled(weird)
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "completed"  # read-only probe completed (exit 0) but payload is treated as untrusted text
    assert "result_payload" in res.output

    def empty(argv, timeout_s, stdout_max, stderr_max, env):
        return RunnerResult(True, 1, "", "", False, None)
    res2 = _enabled(empty).execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res2.status == "failed"

    def partial(argv, timeout_s, stdout_max, stderr_max, env):
        return RunnerResult(True, None, "Gateway: starting", "", True, "timeout")
    res3 = _enabled(partial).execute(ExecutionRequest(request_id="r3", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res3.status == "timeout"
    assert res3.output["status"] == "timeout"


def test_timeout_bound_and_missing_ids_not_invented(monkeypatch):
    seen = {}
    def runner(argv, timeout_s, stdout_max, stderr_max, env):
        seen["timeout_s"] = timeout_s
        return RunnerResult(True, 0, "ok", "", False, None)
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", runner=runner, max_timeout_ms=5000)
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    # request over max should be rejected by validation (fail closed)
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args(timeout_ms=999999)))
    assert res.status == "rejected"
    res2 = ad.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args(timeout_ms=4000)))
    assert res2.status == "completed"
    assert seen["timeout_s"] <= 5.0
    assert res2.output["hermes_execution_id"] is None  # never invented
