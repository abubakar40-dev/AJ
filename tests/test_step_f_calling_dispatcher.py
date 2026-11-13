"""Step F: helix.calling_service wired into AJ's execution pipeline.

This is a *dispatcher integration* using deterministic in-process test doubles
(FakeResolver / FakeBridge), not a live HELIX execution and not a network call to
the HELIX bridge. helix.prepare_call resolves a contact and stops before dialing;
no real call is placed. Real HELIX execution is NOT VERIFIED (HELIX has no agreed
AJ task endpoint and is not running; see Step E/D audits).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aj import errors
from aj.audit import read_events
from aj.calling import BridgeCapabilities, CallState, CallingService, Contact
from aj.config import load
from aj.journal import Journal
from aj.orchestrator import Aj, build
from aj.receipts import ReceiptStore
from aj.runtime import assemble
from aj.task import AUTHORIZED, COMPLETED, EXECUTING, FAILED, RECEIVED, TaskStore

from conftest import AJ_ROOT, make_config


# --- deterministic test doubles (dispatcher integration, not mocks of AJ) ---

class FakeResolver:
    def __init__(self, contacts):
        self.contacts = list(contacts)
        self.calls = []

    def resolve(self, query):
        self.calls.append(query)
        return [c for c in self.contacts
                if query.lower() in c.display_name.lower()
                or query.lower() in c.phone]


class RaisingResolver:
    def __init__(self, exc):
        self.exc = exc

    def resolve(self, query):
        raise self.exc


class SlowResolver:
    def __init__(self, contacts, delay):
        self.contacts = list(contacts)
        self.delay = delay

    def resolve(self, query):
        time.sleep(self.delay)
        return [c for c in self.contacts if query.lower() in c.display_name.lower()]


class MalformedResolver:
    def resolve(self, query):
        return "not-a-list-of-contacts"  # iterating yields chars; Contact attrs missing


class FakeBridge:
    name = "fake"
    def available(self): return True
    def capabilities(self): return BridgeCapabilities()
    def open_dialer(self, number): return {}
    def place_call(self, number): return {}


def calling_env(tmp_path, *, resolver=None, bridge=None, unattended_ceiling=1):
    cfg = load(env={}, overrides={
        "core": {
            "data_dir": str(tmp_path / "data"),
            "audit_dir": str(tmp_path / "audit"),
        },
        "permissions": {"unattended_ceiling": unattended_ceiling},
        "runtime": {"persist_tasks": True, "persist_memory": True},
    })
    service = CallingService(resolver=resolver, bridge=bridge or FakeBridge())
    aj = assemble(cfg, calling=service)
    return aj, cfg


def sara():
    return Contact("c1", "Sara Khan", "+923001111111", source="test")


# 1. Valid authorized request (deterministic resolver; prepare only, no dial)
def test_valid_authorized_prepare_completes(tmp_path):
    aj, cfg = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"}, requester="user")
    assert out.ok is True
    assert out.status == COMPLETED
    assert out.owner_agent == "HELIX"
    assert out.capability_id == "helix.prepare_call"
    assert "Sara" in out.summary
    assert "awaiting dial confirmation" in out.summary.lower()
    assert out.output["state"] == CallState.AWAITING_CONFIRMATION.value
    assert out.output["contact"]["display_name"] == "Sara Khan"
    assert "phone_masked" in out.output["contact"]
    assert "+923001111111" not in json.dumps(out.output)
    # No real call placed: prepare stops before dialing.
    assert "DIALING" not in out.summary


# 2a. Forbidden capability: policy refuses before execution
def test_forbidden_prepare_blocked_by_policy(tmp_path):
    aj, cfg = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    spec = aj.registry.find("helix.prepare_call")
    aj.registry.register(type(spec)(**{**spec.__dict__, "forbidden": True}), replace=True)
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})
    assert out.ok is False
    assert out.status in ("FAILED", "ABORTED")
    assert aj.calling.all_calls() == []  # never reached execution
    # mandatory audit evidence of denial recorded
    actions = [e["action"] for e in
               read_events(cfg.get("core.audit_dir"), task_id=out.task_id).events]
    assert "failed" in actions or "policy_denied" in actions


# 2b. Consequential capability without approval: CONFIRM gate, no resolver call
def test_consequential_prepare_without_approval_stops_at_gate(tmp_path):
    aj, cfg = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    spec = aj.registry.find("helix.prepare_call")
    aj.registry.register(type(spec)(**{**spec.__dict__, "risk_level": 3}), replace=True)
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})
    assert out.ok is False
    assert out.status == "WAITING_FOR_APPROVAL"
    assert out.requires_user_decision is True
    assert aj.calling.resolver.calls == []
    assert aj.calling.all_calls() == []
    actions = [e["action"] for e in
               read_events(cfg.get("core.audit_dir"), task_id=out.task_id).events]
    assert "awaiting_approval" in actions


# 3. Calling service unavailable in environment (no resolver configured)
def test_prepare_without_resolver_fails_honestly(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=None)
    spec = aj.registry.find("helix.prepare_call")
    assert aj.dispatch_of(spec)[0] is True
    assert spec.availability == "unavailable"
    assert spec.executable is False
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})
    # blocker runs before dispatch because capability is unavailable
    assert out.ok is False
    assert "unavailable" in out.summary.lower()


# 4. Connection failure surfaced as execution failure
def test_connection_failure_from_resolver(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=RaisingResolver(ConnectionError("link down")))
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})
    assert out.ok is False
    assert out.status == FAILED
    assert "link down" in out.summary or "connection" in out.summary.lower()
    assert aj.tasks.get(out.task_id).status == FAILED


# 5. Timeout handling
def test_prepare_timeout(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=SlowResolver([sara()], delay=2.0))
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"}, timeout_seconds=1)
    assert out.ok is False
    assert out.status == FAILED
    assert "timed out" in out.summary.lower()
    assert any(e.get("code") == errors.AGENT_TIMEOUT for e in out.errors)


# 6. Malformed response / resolver error
def test_malformed_resolver_result_fails_safely(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=MalformedResolver())
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})
    assert out.ok is False
    assert out.status == FAILED
    # no crash, no success claim
    assert out.summary


# 7. External operation failure (ambiguous contact, no match)
def test_ambiguous_contact_is_execution_failure(tmp_path):
    contacts = [sara(), Contact("c2", "Sara Ali", "+923002222222", source="test")]
    aj, _ = calling_env(tmp_path, resolver=FakeResolver(contacts))
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})
    assert out.ok is False
    assert out.status == FAILED
    assert "ambiguous" in out.summary.lower()

def test_no_contact_match_is_execution_failure(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    out = aj.handle("call Zain", capability_id="helix.prepare_call",
                    payload={"query": "Zain"})
    assert out.ok is False
    assert out.status == FAILED
    assert "no contact" in out.summary.lower()


# 8. Successful external operation (dispatcher integration with deterministic resolver)
def test_success_returns_structured_call_record(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    out = aj.handle("prepare Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})
    assert out.ok and out.status == COMPLETED
    rec = out.output
    assert rec["call_id"].startswith("call_")
    assert rec["state"] == "AWAITING_CONFIRMATION"
    assert rec["contact"]["display_name"] == "Sara Khan"
    assert rec["events"]  # state transitions recorded by CallingService
    # the whole record is masked: no full phone number in the structured result
    assert "+923001111111" not in json.dumps(rec)


# 9. Duplicate request / idempotency behaviour
def test_idempotent_replay_returns_existing_task(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    first = aj.handle("call Sara", capability_id="helix.prepare_call",
                      payload={"query": "Sara"}, idempotency_key="k-prepare-sara")
    second = aj.handle("call Sara", capability_id="helix.prepare_call",
                       payload={"query": "Sara"}, idempotency_key="k-prepare-sara")
    assert first.ok and second.ok
    assert second.task_id == first.task_id
    assert "idempotent" in second.summary.lower()
    # resolver invoked once (second was a replay, not re-executed)
    assert len(aj.calling.resolver.calls) == 1


# 10. Lease cleanup after failure
def test_lease_released_after_failure(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=RaisingResolver(RuntimeError("boom")))
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})
    assert out.status == FAILED
    assert aj.leases.status(out.task_id) == "RELEASED"
    assert aj.leases.get(out.task_id) is not None
    assert aj.leases.get(out.task_id).status == "RELEASED"


# 11. Receipt and journal persistence
def test_receipts_and_journal_persisted(tmp_path):
    aj, cfg = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})
    assert out.ok
    data_dir = Path(cfg.get("core.data_dir"))
    # journal
    jpath = data_dir / "journal.jsonl"
    assert jpath.is_file()
    events = [json.loads(l) for l in jpath.read_text().splitlines() if l.strip()]
    types = [e.get("event_type") or e.get("type") for e in events]
    assert "TASK_ACCEPTED" in types
    assert "EXECUTION_STARTED" in types
    assert "EXECUTION_RESULT_RECORDED" in types
    # receipt
    rpath = data_dir / "receipts.jsonl"
    assert rpath.is_file()
    receipts = [json.loads(l) for l in rpath.read_text().splitlines() if l.strip()]
    mine = [r for r in receipts if r.get("task_id") == out.task_id]
    assert mine, "receipt for task missing"
    assert mine[-1]["execution_status"] == "COMPLETED"
    assert mine[-1]["capability_id"] == "helix.prepare_call"
    assert mine[-1]["attempt_id"]


# 12. Audit event correctness
def test_audit_records_execution(tmp_path):
    aj, cfg = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})
    audit = read_events(cfg.get("core.audit_dir"), task_id=out.task_id)
    events = [e["action"] for e in audit.events]
    assert "task_received" in events
    assert "authorized" in events
    assert "executed" in events
    executed = [e for e in audit.events if e["action"] == "executed"][0]
    assert executed["capability"] == "helix.prepare_call"
    assert executed["result"] == "completed"
    assert executed["agent"] == "HELIX"


# 13. Restart/recovery after interrupted execution
def test_interrupted_prepare_requires_manual_recovery(tmp_path):
    # Create a persisted task left in EXECUTING (simulated crash mid-execution).
    data_dir = tmp_path / "data"
    cfg = load(env={}, overrides={
        "core": {"data_dir": str(data_dir), "audit_dir": str(tmp_path / "audit")},
        "runtime": {"persist_tasks": True, "persist_memory": True},
    })
    store = TaskStore(data_dir)
    rec = store.create("call Sara", capability_id="helix.prepare_call")
    store.transition(rec.task_id, "UNDERSTANDING")
    store.transition(rec.task_id, "PLANNED")
    store.transition(rec.task_id, "AUTHORIZED")
    store.transition(rec.task_id, "EXECUTING")
    rec.request_payload = {"query": "Sara"}
    store.save(rec, "interrupted")
    # Restart: new orchestrator over same persisted state.
    aj2 = assemble(cfg, calling=CallingService(resolver=FakeResolver([sara()])))
    outcome = aj2.recover(rec.task_id)
    # helix.prepare_call is not replay_safe -> must not silently re-execute.
    assert outcome.ok is False
    assert outcome.requires_user_decision is True
    assert "not declared replay-safe" in outcome.summary or "Recovery required" in outcome.summary
    assert aj2.tasks.get(rec.task_id).status in ("RECOVERY_REQUIRED", "FAILED")


# 14. Unknown capability or missing dispatcher
def test_unknown_capability_fails_explicitly(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    out = aj.handle("do it", capability_id="no.such.capability")
    assert out.ok is False
    assert any(e.get("code") == errors.CAPABILITY_NOT_FOUND for e in out.errors)

def test_missing_dispatcher_fails_explicitly(tmp_path):
    # aj.delegate still has no dispatcher (by design, corrected in Step E)
    aj, _ = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    out = aj.handle("delegate", capability_id="aj.delegate")
    assert out.ok is False
    assert out.status == "FAILED"
    assert any(e.get("code") == errors.CAPABILITY_UNAVAILABLE for e in out.errors)


# CLI / observability
def test_capabilities_cli_reports_calling_dispatch(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(AJ_ROOT),
               AJ_CORE__DATA_DIR=str(tmp_path / "data"),
               AJ_CORE__AUDIT_DIR=str(tmp_path / "audit"))
    # JSON
    done = subprocess.run([sys.executable, "-m", "aj", "capabilities", "--json"],
                          cwd=str(AJ_ROOT), capture_output=True, text=True,
                          env=env, timeout=120)
    assert done.returncode == 0, done.stderr
    rows = {r["capability_id"]: r for r in json.loads(done.stdout)["capabilities"]}
    h = rows["helix.prepare_call"]
    assert h["dispatchable"] is True
    assert "calling service" in h["dispatch_reason"]
    assert h["registered"] if "registered" in h else h["capability_id"] == "helix.prepare_call"
    assert h["availability"] in ("available", "unavailable")
    # text
    done = subprocess.run([sys.executable, "-m", "aj", "capabilities"],
                          cwd=str(AJ_ROOT), capture_output=True, text=True,
                          env=env, timeout=120)
    assert done.returncode == 0, done.stderr
    assert "helix.prepare_call" in done.stdout
    assert "dispatchable: true" in done.stdout


def test_dispatch_of_reports_calling_adapter():
    aj = build(make_config(), calling=CallingService(resolver=FakeResolver([sara()])))
    spec = aj.registry.find("helix.prepare_call")
    ok, reason = aj.dispatch_of(spec)
    assert ok is True and "calling service" in reason
    assert spec.availability == "available"
    assert spec.executable is True
    assert spec.metadata_executable if hasattr(spec, "metadata_executable") else spec.executable

def test_prepare_requires_query(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    # goal empty-ish won't happen via handle validation, but payload/query absent with blank goal fallback
    out = aj.handle(" ", capability_id="helix.prepare_call", payload={})
    assert out.ok is False  # empty goal rejected at task creation or as missing query


# --- cancellation, retry refusal and bounded-timeout evidence -------------

class HookingResolver:
    """Resolver that runs a hook inside the preparation window."""

    def __init__(self, contacts):
        self.contacts = list(contacts)
        self.calls = []
        self.hook = None

    def resolve(self, query):
        self.calls.append(query)
        if self.hook is not None:
            self.hook()
        return [c for c in self.contacts if query.lower() in c.display_name.lower()]


def test_cancel_before_execution_never_resolves(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=FakeResolver([sara()]))
    spec = aj.registry.find("helix.prepare_call")
    aj.registry.register(type(spec)(**{**spec.__dict__, "risk_level": 3}), replace=True)
    waiting = aj.handle("call Sara", capability_id="helix.prepare_call",
                        payload={"query": "Sara"})
    assert waiting.status == "WAITING_FOR_APPROVAL"

    cancelled = aj.cancel_task(waiting.task_id)
    assert cancelled.ok is True
    assert cancelled.status == "CANCELLED"
    assert aj.tasks.get(waiting.task_id).status == "CANCELLED"
    assert aj.calling.resolver.calls == []
    assert aj.calling.all_calls() == []


def test_cancel_requested_during_preparation_is_not_reported_as_completed(tmp_path):
    resolver = HookingResolver([sara()])
    aj, cfg = calling_env(tmp_path, resolver=resolver)

    def request_cancel():
        record = aj.tasks.query(newest_first=True, limit=1)[0]
        aj.tasks.transition(record.task_id, "CANCEL_REQUESTED", "test cancel")

    resolver.hook = request_cancel
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"})

    assert out.ok is False
    assert out.status == "CANCELLED"
    assert "cancel" in out.summary.lower()
    assert aj.tasks.get(out.task_id).status == "CANCELLED"
    actions = [e["action"] for e in
               read_events(cfg.get("core.audit_dir"), task_id=out.task_id).events]
    assert "executed" not in actions
    assert "cancelled" in actions
    receipts = [json.loads(line) for line in
                (Path(cfg.get("core.data_dir")) / "receipts.jsonl")
                .read_text().splitlines() if line.strip()]
    mine = [r for r in receipts if r["task_id"] == out.task_id]
    assert mine and mine[-1]["execution_status"] == "CANCELLED"


def test_retry_is_refused_and_does_not_reexecute(tmp_path):
    resolver = FakeResolver([sara()])

    def boom(query):
        resolver.calls.append(query)
        raise RuntimeError("resolver exploded")

    resolver.resolve = boom
    aj, cfg = calling_env(tmp_path, resolver=resolver)
    first = aj.handle("call Sara", capability_id="helix.prepare_call",
                      payload={"query": "Sara"})
    assert first.status == FAILED
    assert len(resolver.calls) == 1

    outcome = aj.retry(first.task_id)
    assert outcome.ok is False
    assert "not declared retry-safe" in outcome.summary
    assert len(resolver.calls) == 1, "retry must not re-execute a non-retry-safe capability"
    record = aj.tasks.get(first.task_id)
    assert record.status == FAILED
    assert record.attempt == 1
    executed = [e["action"] for e in
                read_events(cfg.get("core.audit_dir"), task_id=first.task_id).events]
    assert executed.count("executed") == 0
    assert "retry_refused" in executed


def test_timeout_is_a_real_wall_clock_bound(tmp_path):
    aj, _ = calling_env(tmp_path, resolver=SlowResolver([sara()], delay=2.0))
    started = time.time()
    out = aj.handle("call Sara", capability_id="helix.prepare_call",
                    payload={"query": "Sara"}, timeout_seconds=1)
    elapsed = time.time() - started
    assert out.status == FAILED
    assert "timed out" in out.summary.lower()
    # The bound must hold at the caller, not after the resolver returns.
    assert elapsed < 1.6, f"timeout did not bound the call: {elapsed:.2f}s"
    assert aj.tasks.get(out.task_id).status == FAILED
