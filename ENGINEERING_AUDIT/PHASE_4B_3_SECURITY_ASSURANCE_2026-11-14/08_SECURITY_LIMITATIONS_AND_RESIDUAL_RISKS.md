# 08 — Security Limitations and Residual Risks

## Verified (within tested threat model/scope)
- Read-only boundary only: fixed `hermes gateway status`, fixed argv, `shell=False`, deny-by-default allowlist, capability/contract/authz/input validation, default-disabled/fail-closed config and runtime gating.
- `local_trust` correctly treated as non-authenticated; no verified identity claims or Hermes ID fabrication.
- Bounded incremental output collection, timeout termination/reap (best-effort), honest outcome classification, conservative non-semantic observation, no false-success mapping.
- Controlled env allowlist enforced; best-effort redaction improved and regression-tested.
- 47 new security-assurance tests + 4B.1/4B.2/contract suites + full regression (503 passed) + `aj --check` (23/23, Hermes NOT ATTACHED).

## Residual risks (concrete)
| Risk | Detail | Severity | Mitigation/status |
|---|---|---|---|
| TOCTOU / executable provenance | Path/executable validated then spawned; symlink resolved if executable; PATH/FS trust assumed in local context | Medium | Documented; fixed command limits impact; operator-controlled environment assumption |
| Descendant process/pipe holders | Child may spawn session-escaping descendant holding inherited pipe; reader threads join bounded but best-effort cleanup not absolute | Medium | Bounded return verified in test; process-group+pid kill applied; residual documented |
| Redaction completeness | Regex best-effort; novel encodings/formats may leak | Medium | Improved patterns/tests; bounds/env allowlist reduce exposure; not primary boundary |
| Multi-store evidence non-atomicity | Task/audit/journal/receipt/memory writes not atomic across stores | Medium (known) | Existing architecture; no redesign; honest failure semantics preserved |
| Hermes CLI/version drift | Behavior/output/options may change | Low–Medium | Fixed argv/read-only scope; untrusted output; re-verify on upgrades |
| Host/installer compromise | Malicious `hermes` binary in PATH or replaced target outside AJ control | High (out of scope) | Relies on operator/host integrity; AJ bounds blast radius to read-only probe |
| Semantic health ambiguity | Exit 0/raw text not proof of runtime health | Low | Explicitly documented and encoded in observations/notes |

## Threat-model exclusions
Remote/multi-user attackers, authenticated identity, compromised OS/kernel/host supply chain, physical attacks, live Hermes/JARVIS/HELIX internals, non-approved Hermes commands/capabilities, long-haul production reliability claims. No security assurance completeness claimed beyond defined local read-only scope.