# 02 — Capability Registry

**Status:** implemented · **Measured:** 38 capabilities, 2 executable

## 1. What a capability is

A declaration of something the ecosystem *can do*, with the metadata AJ needs to decide
whether to allow it right now:

```
capability_id          helix.place_call
name                   Place a phone call
owner_agent            HELIX
execution_adapter      device_bridge:gsconnect
required_permissions   ["phone_call"]
risk_level             3            (0 read … 4 highly sensitive)
availability           unavailable  (this environment, now)
verification_status    implemented_unverified
supported_inputs       ["contact", "phone_number"]
supported_outputs      ["call_state"]
side_effects           ["places a real call", "may incur carrier charges"]
forbidden              false
source / notes         evidence
```

A capability is metadata, never an implementation. AJ resolves the owner and the adapter;
it does not import a tool.

## 2. Where the data comes from

| Source | Entries | Why |
|---|---|---|
| `JARVIS/core/capabilities.py` | **26** | imported by file path at build time — one authority, no copy |
| `config/capabilities.json` | 12 | HELIX calling/comms, the Hermes boundary, AJ delegation |

JARVIS tiers are translated, not redefined:

```
read → 0    local-write → 1    consequential → 3    forbidden → 4
```

`forbidden` is represented twice on purpose: as level 4 (sensitive) *and* as the
`forbidden` flag (never, with or without approval). The flag wins.

## 3. Measured state (9 Nov 2026)

```
total 38   AJ 1 · HELIX 10 · HERMES 1 · JARVIS 26
verified                    1   (aj.delegate)
implemented_unverified     33
partial                     3   (browser_control, computer_control, prepare_call)
planned                     1   (hermes.execute_skill)
executable                  2   (aj.delegate, helix.prepare_call)
```

Only two are executable because `executable` requires non-unknown availability. JARVIS
capabilities are registered `implemented_unverified` **and** `availability=unknown`
because no live JARVIS bridge was reachable during this phase: the app was not running
on `127.0.0.1:8875`. That is not a defect in the registry; it is the registry refusing to
guess.

To promote one, evidence must exist:

```python
registry.set_availability("jarvis.web_search", "available")   # bridge verified
registry.set_verification("jarvis.web_search", "verified")    # behaviour tested
```

## 4. Why 26 rather than the audit's 25

The November audit counted 25 declared *voice tools*. JARVIS's registry also carries
`desktop_control`, which the audit listed as a capability in the traceability table but
not in the tool inventory. The registry is generated from code, so 26 is the code's count.

## 5. Adding a capability

1. Declare it in `config/capabilities.json` (or in the owning agent's own registry, which
   is preferable for agent-internal tools).
2. Set `availability` to what you can demonstrate, and `verification_status` to what you
   have evidence for. `implemented_unverified` is the honest default.
3. Add `side_effects` for anything visible outside the machine.
4. If it belongs to Hermes, leave `availability=unavailable` until the runtime exists.
5. Run `python -m pytest tests -q` — the loader validates owner, level and vocabulary, so
   a typo fails loudly instead of silently disabling a capability.

## 6. Duplicate prevention

`register()` raises when the same id arrives with different metadata; `replace=True` is the
only way to redefine, and it is explicit. This means a second definition cannot quietly
win — the single most likely way a capability list becomes fiction.
