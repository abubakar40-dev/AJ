"""Calling tests: state machine, ambiguity, approval, honest bridge reporting."""

from __future__ import annotations

import pytest

from aj import errors
from aj.calling import (
    BridgeCapabilities,
    CallState,
    CallingService,
    Contact,
    NullDeviceBridge,
)
from aj.permissions import ApprovalGate, Authorizer


class FakeResolver:
    def __init__(self, contacts):
        self.contacts = contacts

    def resolve(self, query):
        return [c for c in self.contacts if query.lower() in c.display_name.lower()]


class FakeBridge:
    name = "fake"

    def __init__(self, capabilities, outcome=None):
        self.capabilities_ = capabilities
        self.outcome = outcome or {"state": "DIALING", "verified": False}
        self.dialed = []

    def available(self):
        return True

    def capabilities(self):
        return self.capabilities_

    def open_dialer(self, number):
        return {"ok": True}

    def place_call(self, number):
        self.dialed.append(number)
        return self.outcome


def telephone():
    return BridgeCapabilities(can_place_call=True, can_open_dialer=True,
                              can_end_call=True, can_read_call_state=True)


def test_resolution_that_is_ambiguous_never_guesses():
    service = CallingService(
        resolver=FakeResolver([Contact("1", "Ali Khan", "+923001111111"),
                               Contact("2", "Ali Raza", "+923002222222")]),
        bridge=FakeBridge(telephone()),
    )
    record = service.prepare("Ali")
    assert record.state is CallState.FAILED
    assert "ambiguous" in record.error


def test_prepare_stops_before_dialing():
    service = CallingService(
        resolver=FakeResolver([Contact("1", "Sara", "+923001111111")]),
        bridge=FakeBridge(telephone()),
    )
    record = service.prepare("Sara")
    assert record.state is CallState.AWAITING_CONFIRMATION
    assert record.contact.display_name == "Sara"
    assert "•" in record.to_dict()["contact"]["phone_masked"]


def test_dialing_without_approval_is_refused_and_claims_nothing():
    bridge = FakeBridge(telephone())
    service = CallingService(
        resolver=FakeResolver([Contact("1", "Sara", "+923001111111")]),
        bridge=bridge,
        authorizer=Authorizer(gate=ApprovalGate()),
    )
    record = service.prepare("Sara")
    result = service.confirm_and_dial(record.call_id)
    assert result.state is CallState.AWAITING_CONFIRMATION
    assert "consequential" in result.error
    assert bridge.dialed == []


def test_dialing_with_approval_reports_only_what_the_bridge_reports():
    gate = ApprovalGate()
    bridge = FakeBridge(telephone(), {"state": "CONNECTED", "verified": True})
    service = CallingService(
        resolver=FakeResolver([Contact("1", "Sara", "+923001111111")]),
        bridge=bridge,
        authorizer=Authorizer(gate=gate),
    )
    record = service.prepare("Sara")
    payload = {"call_id": record.call_id, "contact": record.contact.contact_id}
    approval = gate.issue("helix.place_call", payload)
    result = service.confirm_and_dial(record.call_id, approval_token=approval.token)
    assert bridge.dialed == ["+923001111111"]
    assert result.state is CallState.CONNECTED
    assert result.verified is True


def test_bridge_without_call_control_fails_closed():
    service = CallingService(
        resolver=FakeResolver([Contact("1", "Sara", "+923001111111")]),
        bridge=FakeBridge(BridgeCapabilities()),
    )
    record = service.prepare("Sara")
    result = service.confirm_and_dial(record.call_id)
    assert result.state is CallState.FAILED
    assert "no dialing capability" in result.error


def test_null_bridge_advertises_nothing_and_refuses():
    bridge = NullDeviceBridge()
    assert bridge.available() is False
    assert bridge.capabilities().to_dict() == {k: False for k in
                                               bridge.capabilities().to_dict()}
    with pytest.raises(errors.AjError):
        bridge.place_call("+92300")


def test_illegal_call_transition_is_refused():
    service = CallingService(
        resolver=FakeResolver([Contact("1", "Sara", "+923001111111")]),
        bridge=FakeBridge(telephone()),
    )
    record = service.prepare("Sara")
    with pytest.raises(errors.AjError):
        record.transition(CallState.ENDED)


def test_cancel_before_dialing_is_terminal():
    service = CallingService(
        resolver=FakeResolver([Contact("1", "Sara", "+923001111111")]),
        bridge=FakeBridge(telephone()),
    )
    record = service.prepare("Sara")
    assert service.cancel(record.call_id) is True
    assert record.state is CallState.CANCELLED
    assert service.cancel(record.call_id) is False


def test_end_call_is_refused_when_the_bridge_cannot_end_calls():
    service = CallingService(
        resolver=FakeResolver([Contact("1", "Sara", "+923001111111")]),
        bridge=FakeBridge(BridgeCapabilities(can_place_call=True)),
    )
    record = service.prepare("Sara")
    record.transition(CallState.PREPARING)
    record.transition(CallState.DIALING)
    record.transition(CallState.CONNECTED)
    with pytest.raises(errors.AjError):
        service.hang_up(record.call_id)


def test_gsconnect_probe_does_not_claim_telephony(monkeypatch):
    """The real adapter must not invent call control when no plugin is exported."""
    from aj.integrations import gsconnect

    bridge = gsconnect.GSConnectBridge()
    monkeypatch.setattr(bridge, "devices", lambda refresh=False: [
        gsconnect.BridgeDevice(
            device_id="d", name="Redmi A3", paired=True, connected=True, kind="phone",
            interfaces=["org.freedesktop.DBus.Properties",
                        "org.gnome.Shell.Extensions.GSConnect.Device"],
        )
    ])
    caps = bridge.capabilities()
    assert caps.can_place_call is False
    assert caps.can_open_dialer is False
    with pytest.raises(errors.AjError):
        bridge.place_call("+92300")
