# 08 — Security Invariants and Limitations

## Invariants preserved (verified)
- **Default-disabled/fail-closed:** `feature_flags.hermes_execution_adapter=false`, `execution.runtime="none"`, `execution.hermes.enabled=false`, `execution.hermes.capability_status_read_enabled=false`. Normal runtime: `attached.hermes: "NOT ATTACHED"` (`aj --check` 23/23). Capability not available/registered in default runtime.
- **Explicit enablement only:** adapter attached/capability registered only with required flags/config; invalid explicit config fails closed to unavailable (`strict_config` validation in adapter + runtime checks).
- **Deny-by-default allowlist:** only `hermes.status.read`, empty input, AJ permission context required (`authorizer=AJ`, `authorization_decision=allow`, `trust_mode=local_trust`), fixed argv `["<resolved-hermes>","gateway","status"]`, `shell=False`, no user-controlled command/args/env/path injection at request boundary.
- **CLI provenance/bounds:** cli_path validated (non-empty string, no whitespace/NUL, no leading `-`), resolved executable required, controlled env allowlist, bounded timeout and bounded incremental stdout/stderr collection, timeout termination/reap.
- **Honesty/evidence:** no fabricated Hermes IDs, no false success on timeout/failure/rejection, `unknown` not coerced to completed, best-effort redaction, untrusted output handling, no cross-store atomicity/exactly-once claims.
- **Trust boundary:** `local_trust` is **not** authenticated identity, not cryptographic identity, not remote-user authorization, not multi-user isolation, and not proof of human initiation. No remote/multi-user security guarantees claimed.

## Limitations / residual risks
- **Redaction best-effort:** pattern-based; cannot guarantee removal of all secret formats/encodings.
- **Unstructured output:** CLI text is environment-dependent/untrusted; truncation possible; `exit_zero` is process outcome, not semantic health proof.
- **Process cleanup:** best-effort process-group/pid termination; rare platform/descendant edge cases cannot be universally proven impossible.
- **Intermittent environment flake (unrelated):** `tests/test_phase3.py::test_concurrent_memory_writers_keep_every_event` showed 3/5 failures in isolated repeats (SQLite disk I/O/lock under fork stress) in this environment; not reproducible consistently and not caused by 4B.2 changes. Full suite passed 456/456 in final run.
- **Scope:** read-only status probe only; no authorization for broader Hermes/JARVIS/HELIX integration or any mutating capability. Hermes runtime/CLI behavior may drift across versions (re-verification required).