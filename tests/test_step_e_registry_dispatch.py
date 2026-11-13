"""Step E registry honesty: metadata executability vs a real dispatcher.

``CapabilitySpec.executable`` is a policy predicate. It said yes for capabilities
the executor has no handler for, so ``aj capabilities`` could advertise work that
fails the moment it is selected. These tests pin the two answers apart and guard
against metadata outrunning the dispatch table again.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from aj.orchestrator import build
from aj.runtime import health

from conftest import AJ_ROOT, make_config


def _orchestrator():
    return build(make_config())


def test_internal_actions_are_dispatchable():
    aj = _orchestrator()
    for capability_id in ("aj.echo", "aj.health_check"):
        ok, reason = aj.dispatch_of(aj.registry.find(capability_id))
        assert ok is True, f"{capability_id}: {reason}"
        assert reason == "in-process action"


def test_hermes_capability_is_dispatchable_but_not_executable():
    """The port exists, so dispatch is real; the runtime is not attached, so it is not executable."""
    aj = _orchestrator()
    spec = aj.registry.find("hermes.execute_skill")
    assert aj.dispatch_of(spec) == (True, "execution port")
    assert spec.executable is False
    assert spec.availability == "unavailable"
    assert spec.verification_status == "planned"


def test_aj_delegate_is_neither_dispatched_nor_advertised():
    aj = _orchestrator()
    spec = aj.registry.find("aj.delegate")
    assert aj.dispatch_of(spec) == (False, "no agent adapter for AJ")
    assert spec.executable is False, "aj.delegate must not claim to be executable"

    outcome = aj.handle("delegate this", capability_id="aj.delegate", approval="confirm")
    assert outcome.status == "FAILED"
    assert [error.get("code") for error in outcome.errors] == ["capability_unavailable"]


def test_helix_calling_capability_is_dispatchable_but_environment_gated():
    """The executor now routes helix.calling_service, but without a contact
    resolver the live environment cannot satisfy helix.prepare_call honestly."""
    aj = _orchestrator()
    spec = aj.registry.find("helix.prepare_call")
    ok, reason = aj.dispatch_of(spec)
    assert ok is True
    assert "calling service" in reason
    assert spec.executable is False
    assert spec.availability == "unavailable"


def test_no_executable_external_capability_lacks_a_dispatcher():
    """Regression guard: allowed-to-run must imply there is a code path to run it."""
    aj = _orchestrator()
    undispatchable = [spec.capability_id for spec in aj.registry.all()
                      if spec.executable and not aj.dispatch_of(spec)[0]]
    assert undispatchable == []


def test_capability_report_exposes_both_answers():
    aj = _orchestrator()
    rows = {row["capability_id"]: row for row in aj.capability_report()}

    assert rows["aj.echo"]["dispatchable"] is True
    assert rows["aj.echo"]["metadata_executable"] is True
    assert rows["aj.delegate"]["dispatchable"] is False
    assert rows["aj.delegate"]["metadata_executable"] is False
    assert rows["jarvis.web_search"]["dispatch_reason"].endswith(
        "has no agreed task transport"
    )


def test_health_reports_dispatchable_and_metadata_executable_counts():
    report = health(make_config())
    assert report["ok"] is True
    detail = report["checks"]["orchestrator"]["detail"]
    assert detail["metadata_executable"] == 2
    assert detail["dispatchable"] == 4
    assert set(detail["dispatchable_ids"]) == {
        "aj.echo", "aj.health_check", "helix.prepare_call", "hermes.execute_skill",
    }


def test_capabilities_cli_surfaces_dispatchability(tmp_path):
    env = dict(
        os.environ,
        PYTHONPATH=str(AJ_ROOT),
        AJ_CORE__DATA_DIR=str(tmp_path / "data"),
        AJ_CORE__AUDIT_DIR=str(tmp_path / "audit"),
    )
    done = subprocess.run(
        [sys.executable, "-m", "aj", "capabilities", "--json"],
        cwd=str(AJ_ROOT), capture_output=True, text=True, env=env, timeout=120,
    )
    assert done.returncode == 0, done.stderr
    payload = json.loads(done.stdout)
    rows = {row["capability_id"]: row for row in payload["capabilities"]}

    assert rows["aj.echo"]["dispatchable"] is True
    assert rows["aj.delegate"]["dispatchable"] is False
    assert rows["aj.delegate"]["dispatch_reason"] == "no agent adapter for AJ"


def test_capabilities_text_output_states_dispatchability(tmp_path):
    """The human-readable view must not be the one place that still overclaims."""
    env = dict(
        os.environ,
        PYTHONPATH=str(AJ_ROOT),
        AJ_CORE__DATA_DIR=str(tmp_path / "data"),
        AJ_CORE__AUDIT_DIR=str(tmp_path / "audit"),
    )
    done = subprocess.run(
        [sys.executable, "-m", "aj", "capabilities"],
        cwd=str(AJ_ROOT), capture_output=True, text=True, env=env, timeout=120,
    )
    assert done.returncode == 0, done.stderr
    blocks = {}
    current = None
    for line in done.stdout.splitlines():
        if line and not line.startswith(" "):
            current = line
            blocks[current] = []
        elif current:
            blocks[current].append(line.strip())

    assert "dispatchable: false (no agent adapter for AJ)" in blocks["aj.delegate"]
    assert "dispatchable: true (in-process action)" in blocks["aj.echo"]
