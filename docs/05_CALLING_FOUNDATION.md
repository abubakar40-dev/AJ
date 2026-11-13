# 05 — Calling Foundation

**Status:** state machine + policy verified · **telephony: UNAVAILABLE on this machine**

## 1. What was measured (9 Nov 2026, read-only)

| Check | Result |
|---|---|
| GSConnect extension installed | yes (`gsconnect@andyholmes.github.io`) |
| GSConnect session-bus service | reachable |
| Paired devices | **1 — "Redmi A3", paired, connected, type=phone** |
| Telephony plugin interface on the device object | **none exported** |
| `kdeconnect-cli` | not installed |
| Device interfaces present | Properties, Introspectable, Peer, Device, gtk.Menus, gtk.Actions |
| HELIX bridge (`127.0.0.1:8765`) | listening; HTTP `GET /` returns no response (WebSocket server) |
| `helix-live.service` voice proxy | running on `127.0.0.1:8788` |

**Conclusion:** a device bridge exists and a phone is connected, but this bridge does not
expose call control. Therefore `can_place_call`, `can_open_dialer`, `can_answer_call`,
`can_reject_call`, `can_end_call` are all **False**, and the corresponding capabilities are
`unavailable`. Nothing in this phase claims otherwise.

`kdeconnect-cli` being absent also means the KDE Connect route is unverified; GSConnect and
KDE Connect share the protocol but not necessarily the plugin set.

## 2. State machine

```
IDLE → REQUESTED → CONTACT_RESOLVING → AWAITING_CONFIRMATION → PREPARING
     → DIALING → RINGING → CONNECTED → ENDED
                ↘ BUSY / NO_ANSWER / FAILED / UNKNOWN
```

`UNKNOWN` exists on purpose: when the bridge cannot report state, AJ must say so rather
than infer `CONNECTED` or `ENDED`. Illegal transitions raise — a call cannot jump from
`AWAITING_CONFIRMATION` to `ENDED`.

## 3. Approval behaviour (tested)

| Situation | Behaviour |
|---|---|
| Two contacts match "Ali" | `FAILED`, ambiguous, asks the user — never guesses |
| One contact resolved | stops at `AWAITING_CONFIRMATION` |
| Dial without approval token | stays `AWAITING_CONFIRMATION`, nothing dialed |
| Approval for a different call | rejected: "the action changed after it was approved" |
| Bridge has no dialing capability | `FAILED`, no call placed |
| Hang up without `can_end_call` | refused |

Phone numbers are masked in every record (`••••••1111`); `Contact.to_public_dict()` is the
only serialisation path, so a full number cannot leak into a log through the record.

## 4. Ports

- `ContactResolver.resolve(query) -> list[Contact]` — HELIX side. More than one match is
  an error by design.
- `DeviceBridge` — `available()`, `capabilities()`, `open_dialer()`, `place_call()`.
  `GSConnectBridge` implements discovery only; its dialing methods raise with an
  explanation because the interface is absent.

## 5. Test plan that still has to happen

1. Enable/pair a bridge that exports telephony, or accept dialer handoff only.
2. Discover capabilities at runtime and record the result in the registry.
3. Resolve a test contact; verify ambiguity handling with two similar names.
4. Open the dialer with a test number, **not** placing a call.
5. Verify incoming-call event delivery.
6. Verify state transitions during one controlled test call.
7. Exercise answer/reject/end only if the bridge officially exposes them.
8. Disconnect the phone mid-workflow; confirm the task fails cleanly.
9. Confirm a timeout cannot produce a duplicate call.
10. Confirm no full number, contact list or audio reaches ordinary logs.

## 6. Boundaries kept

- Voice conversation (AJ/JARVIS/HELIX speaking) is **not** a phone call and shares no
  state with one. `integrations.voice_separate_from_calls` is true in configuration.
- VoIP ≠ mobile telephony. No SIP provider is selected or configured.
- No auto-answer, no recording, no transcription, no emergency-call automation.
