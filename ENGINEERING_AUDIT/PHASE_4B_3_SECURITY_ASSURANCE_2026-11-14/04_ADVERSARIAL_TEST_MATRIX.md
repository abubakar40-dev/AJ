# 04 — Adversarial Test Matrix

**Primary suite:** `AJ/tests/test_phase4b3_security_assurance.py` (47 tests) — deterministic, isolated, mock runners for boundary/contract tests, real safe subprocesses for process/cleanup tests, no live Hermes dependency.

| Threat ID | Test(s) | Adversarial input/scenario | Expected | Result |
|---|---|---|---|---|
| T03/T04 | `test_cli_path_invalid_forms_fail_closed[...]` | empty/whitespace, spaces/args, `;`, newline, NUL, leading `-`, `--flag` cli_path | `failed`, `dependency_unavailable`, `accepted=false`, no Hermes ID | PASS (8 cases) |
| T04 | `test_cli_path_directory_and_non_executable_fail_closed` | directory path, non-executable file | fail closed, no spawn | PASS |
| T04 | `test_symlink_to_executable_resolves_and_runs_fixed_argv` | symlink to executable script | if resolved: completed with fixed argv; if refused: safe dependency failure | PASS (safe outcome) |
| T03 | `test_fixed_argv_immutable_no_user_control` | extra envelope fields `command/argv/flags` | cannot change fixed `['<hermes>','gateway','status']` | PASS |
| T09 | `test_runtime_explicit_enablement_invalid_config_fails_closed[...]` | wrong types, None, negative/zero/excessive/bool-as-int/float timeout or bounds, inverted bounds, invalid enabled type | runtime not attached (`NOT ATTACHED`/disabled) | PASS (11 cases) |
| T09 | `test_default_flags_remain_disabled_in_source_defaults` | source defaults inspection | all hermes flags/runtime disabled | PASS |
| T01/T02 | `test_validate_request_rejects_adversarial_envelopes[...]` | unknown capability, bad version, missing/forged authz/trust, non-empty input, bad/huge timeout, missing IDs | `validate_request` rejects (None + error) | PASS (15 cases) |
| T01 | `test_adapter_rejects_disabled_and_request_control_cannot_change_command` | capability disabled; smuggled subcommand/args in input | `ExecutionUnavailable` when disabled; smuggle rejected; valid fixed command only | PASS |
| T06 | `test_redaction_covers_common_and_edge_formats` | Bearer/Basic, api/access/refresh/client tokens, password/session/cookie, credential URL, env-style secrets, quoted JSON-like, NBSP token, truncation-tail secret | secrets absent, `[REDACTED]` present, no tail leak beyond limit | PASS |
| T06/T10 | `test_output_is_untrusted_bounded_and_no_false_health_claim` | stdout says `Gateway: DOWN/ERROR` with exit 0 | `completed` as process outcome, `observation=exit_zero`, explicit non-semantic-health note, raw text preserved | PASS |
| T08/T10 | `test_runner_signal_nonzero_and_spawn_failure_classification` | real process exits via SIGTERM; missing executable | honest nonzero/signal classification; `cli_not_found`/not started | PASS |
| T10 | `test_adapter_maps_spawn_failure_signal_and_timeout_honestly` | spawn failure, signal -9, timeout with partial output | correct failed/timeout status, accepted flags, no Hermes ID, not ok on timeout | PASS |
| T05 | `test_controlled_env_allowlist_enforced` | set `AWS_SECRET_ACCESS_KEY`, `SHOULD_NOT_LEAK`, `HERMES_HOME` | disallowed vars absent; allowlisted vars (PATH, HERMES_HOME) present | PASS |
| T10/T11 | `test_orchestrator_hermes_timeout_records_honest_failure_evidence` | AJ-mediated timeout via injected runner, isolated assemble | task not completed, failure/timeout outcome, no fabricated success | PASS |
| T02 | `test_local_trust_not_represented_as_authenticated` | `trust_mode=authenticated` in permission context; adapter identity model | rejected `permission_denied`; adapter reports `local_trust` | PASS |
| T07/T08 | `test_runner_timeout_with_child_holding_pipe_returns_bounded` | child spawns descendant inheriting stdout pipe and sleeps; parent hangs | timeout detected, bounded return (<8s), partial output, no uncontrolled hang | PASS |

## Existing regression suites (preserved)
- `tests/test_phase4b1_hermes_adapter.py`, `tests/test_phase4b1_hermes_security_faults.py` — PASS
- `tests/test_phase4b2_reliability_hardening.py` — PASS
- `tests/test_hermes_contract.py` — PASS
- Full AJ regression — **503 passed, 13 warnings, 0 failed**

## Not tested (documented)
- Live Hermes gateway fault manipulation (forbidden); sustained long-term reliability.
- Induced multi-store persistence failures during live execution (would require invasive fault hooks; architecture-level non-atomicity documented).
- Host compromise/PATH hijack beyond local boundary assumptions (TOCTOU residual documented).