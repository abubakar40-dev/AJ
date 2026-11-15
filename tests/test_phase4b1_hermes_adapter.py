import json
import os
import time

import pytest

from aj.capability import CapabilitySpec
from aj.config import Config
from aj.contracts import ExecutionRequest
from aj.errors import ExecutionUnavailable
from aj.execution import execute
from aj.hermes_adapter import HermesExecutionAdapter, RunnerResult
from aj.hermes_contract import CAPABILITY_STATUS_READ, CONTRACT_VERSION
from aj.orchestrator import Aj
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
        "timeout_ms": 5000,
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


def _ok_runner(argv, timeout_s, stdout_max, stderr_max, env):
    assert argv[-2:] == ["gateway", "status"]
    return RunnerResult(True, 0, "Gateway: running\nProfiles: default\n", "", False, None)


def _enabled_adapter(**kw):
    params = dict(enabled=True, capability_enabled=True, cli_path="hermes", runner=_ok_runner)
    params.update(kw)
    return HermesExecutionAdapter(**params)


def test_disabled_adapter_unavailable_and_rejects_execute():
    ad = HermesExecutionAdapter(enabled=False, capability_enabled=False, runner=_ok_runner)
    assert ad.available() is False
    assert ad.describe()["integration_status"] == "disabled"
    req = ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args(), task_id="t1")
    with pytest.raises(ExecutionUnavailable):
        ad.execute(req)


def test_valid_status_read_success_and_contract_mapping():
    ad = _enabled_adapter()
    req = ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args(), task_id="task1")
    res = execute(ad, req)
    assert res.status == "completed"
    assert res.ok is True
    assert res.verified is True
    env = res.output
    assert env["contract_version"] == CONTRACT_VERSION
    assert env["capability_id"] == CAPABILITY_STATUS_READ
    assert env["aj_task_id"] == "task1"
    assert env["operation_id"] == "op1"
    assert env["attempt_id"] == "att1"
    assert env["correlation_id"] == "corr1"
    assert env["hermes_execution_id"] is None
    assert env["accepted"] is True
    assert env["status"] == "completed"
    assert "Gateway: running" in env["result_payload"]["stdout"]
    assert env["evidence"]["argv_template"] == ["<hermes>", "gateway", "status"]
    assert env["evidence"]["exit_code"] == 0


def test_rejects_unknown_capability_and_invalid_contract():
    ad = _enabled_adapter()
    bad_cap = _v0_args(capability_id="hermes.run.agent")
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id="hermes.run.agent", arguments=bad_cap))
    assert res.status == "rejected"
    assert res.output["error"]["class"] == "capability_not_allowed"
    bad_ver = _v0_args(contract_version="aj.hermes.execution.v999")
    res2 = ad.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=bad_ver))
    assert res2.status == "rejected"
    assert res2.output["error"]["class"] == "contract_version_unsupported"


def test_rejects_invalid_input_missing_authz_and_bad_trust():
    ad = _enabled_adapter()
    args = _v0_args(input={"cmd": "rm -rf /"})
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=args))
    assert res.status == "rejected"
    args2 = _v0_args(permission_context={"authorizer": "user", "authorization_decision": "allow", "trust_mode": "local_trust"})
    res2 = ad.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=args2))
    assert res2.status == "rejected"
    assert res2.output["error"]["class"] == "permission_denied"
    args3 = _v0_args(permission_context={"authorizer": "AJ", "authorization_decision": "deny", "trust_mode": "local_trust"})
    res3 = ad.execute(ExecutionRequest(request_id="r3", capability_id=CAPABILITY_STATUS_READ, arguments=args3))
    assert res3.status == "rejected"
    args4 = _v0_args(permission_context={"authorizer": "AJ", "authorization_decision": "allow", "trust_mode": "remote"})
    res4 = ad.execute(ExecutionRequest(request_id="r4", capability_id=CAPABILITY_STATUS_READ, arguments=args4))
    assert res4.status == "rejected"


def test_nonzero_exit_maps_failed_and_timeout_maps_timeout():
    def fail_runner(argv, timeout_s, stdout_max, stderr_max, env):
        return RunnerResult(True, 2, "", "boom", False, None)
    ad = _enabled_adapter(runner=fail_runner)
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "failed"
    assert res.output["accepted"] is True
    assert res.output["status"] == "failed"

    def to_runner(argv, timeout_s, stdout_max, stderr_max, env):
        return RunnerResult(True, None, "partial", "late", True, "timeout")
    ad2 = _enabled_adapter(runner=to_runner)
    res2 = ad2.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res2.status == "timeout"
    assert res2.output["status"] == "timeout"
    assert res2.output["result_payload"]["partial"] is True


def test_spawn_failure_and_missing_cli():
    def spawn_fail(argv, timeout_s, stdout_max, stderr_max, env):
        return RunnerResult(False, None, "", "", False, "spawn_failed:OSError")
    ad = _enabled_adapter(runner=spawn_fail)
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "failed"
    assert res.output["error"]["class"] == "spawn_failed"

    ad2 = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="/no/such/hermes-cli-xyz", runner=_ok_runner)
    res2 = ad2.execute(ExecutionRequest(request_id="r2", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res2.status == "failed"
    assert res2.output["error"]["class"] == "dependency_unavailable"


def test_output_bounds_and_redaction():
    secret = "api_key=sk-secret-token password=hunter2 Authorization: Bearer abc.def"
    def big_runner(argv, timeout_s, stdout_max, stderr_max, env):
        return RunnerResult(True, 0, ("hello " + secret + " ") * 500, ("err " + secret) * 200, False, None)
    ad = _enabled_adapter(runner=big_runner, stdout_max_bytes=600, stderr_max_bytes=300)
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "completed"
    payload = res.output["result_payload"]
    assert "sk-secret-token" not in payload["stdout"]
    assert "hunter2" not in payload["stdout"]
    assert "[REDACTED]" in payload["stdout"] or "[REDACTED]" in payload["stderr"]
    assert "[truncated]" in payload["stdout"] or "[output truncated" in res.output["evidence"].__str__() or len(payload["stdout"]) <= 700


def test_fixed_argv_no_shell_and_env_allowlist(monkeypatch):
    monkeypatch.setenv("SHOULD_NOT_LEAK_SUPERSECRET", "leakme")
    seen = {}
    def runner(argv, timeout_s, stdout_max, stderr_max, env):
        seen["argv"] = list(argv)
        seen["env"] = dict(env or {})
        return RunnerResult(True, 0, "ok", "", False, None)
    ad = HermesExecutionAdapter(enabled=True, capability_enabled=True, cli_path="hermes", runner=runner)
    # force resolve to a dummy absolute path by stubbing shutil.which
    import shutil
    monkeypatch.setattr(shutil, "which", lambda p: "/usr/bin/hermes")
    res = ad.execute(ExecutionRequest(request_id="r1", capability_id=CAPABILITY_STATUS_READ, arguments=_v0_args()))
    assert res.status == "completed"
    assert seen["argv"] == ["/usr/bin/hermes", "gateway", "status"]
    assert "SHOULD_NOT_LEAK_SUPERSECRET" not in seen["env"]


def test_assembly_default_disabled_and_enablement_wiring(tmp_path):
    from aj.config import load as load_config
    aj = assemble(load_config(overrides={
        "core": {"data_dir": str(tmp_path), "audit_dir": str(tmp_path / "audit")},
        "runtime": {"persist_memory": False, "persist_tasks": False},
    }))
    desc = aj.execution.describe()
    assert desc["available"] is False
    assert desc["integration_status"] == "NOT ATTACHED"
    # enabling requires runtime+feature flag+execution.hermes.enabled+capability flag
    cfg = load_config(overrides={
        "core": {"data_dir": str(tmp_path / "e"), "audit_dir": str(tmp_path / "e" / "audit")},
        "runtime": {"persist_memory": False, "persist_tasks": False},
        "feature_flags": {"hermes_execution_adapter": True},
        "execution": {
            "runtime": "hermes_cli",
            "hermes": {"enabled": True, "capability_status_read_enabled": True, "cli_path": "hermes"},
        },
    })
    aj2 = assemble(cfg)
    assert aj2.execution.available() is True
    assert aj2.execution.describe()["integration_status"] == "attached_read_only"
    assert "hermes.status.read" in [c.capability_id for c in aj2.registry.executable() if c.owner_agent == "HERMES"]
