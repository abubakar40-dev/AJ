# 02 Repo Map (read-only)

## Directory tree (depth 3, excluding `.git`, `__pycache__`, `venv`, `.venv`)

Command:
```bash
find . -maxdepth 3 \( -path '*/.git' -o -path '*/__pycache__' -o -path '*/venv' -o -path '*/.venv' \) -prune -o -print | sed 's|^\./||' | sort
```

```text
.
aj
aj/__init__.py
aj/__main__.py
aj/actions.py
aj/agents.py
aj/audit.py
aj/authorization.py
aj/calling.py
aj/capability.py
aj/config.py
aj/consistency.py
aj/contracts.py
aj/delegation.py
aj/diagnostics.py
aj/errors.py
aj/execution.py
aj/execution_domain.py
aj/hermes_adapter.py
aj/hermes_contract.py
aj/idempotency.py
aj/ids.py
aj/inbox.py
aj/inbox_cli.py
aj/inbox_view.py
aj/integrations
aj/integrations/__init__.py
aj/integrations/gsconnect.py
aj/integrations/jarvis_registry.py
aj/invariants.py
aj/journal.py
aj/lease.py
aj/locking.py
aj/memory.py
aj/operation_evidence.py
aj/orb.py
aj/orb_autostart.py
aj/orb_web.py
aj/orchestrator.py
aj/permissions.py
aj/providers.py
aj/receipts.py
aj/recovery.py
aj/retention.py
aj/runtime.py
aj/scheduler.py
aj/storage_diagnostics.py
aj/summary.py
aj/task.py
aj/transfer.py
aj_control_plane.egg-info
aj_control_plane.egg-info/PKG-INFO
aj_control_plane.egg-info/SOURCES.txt
aj_control_plane.egg-info/dependency_links.txt
aj_control_plane.egg-info/entry_points.txt
aj_control_plane.egg-info/requires.txt
aj_control_plane.egg-info/top_level.txt
config
config/aj.config.json
config/capabilities.json
_context_pack
_context_pack/01_baseline.md
_context_pack/_tmp_collect.txt
_context_pack/_tmp_full_suite_exit.txt
_context_pack/_tmp_full_suite.txt
_context_pack/_tmp_sqlite_runs.txt
_context_pack/_tmp_tree.txt
_context_pack/_tmp_tree3.txt
docs
docs/01_AJ_CONTROL_PLANE.md
docs/02_CAPABILITY_REGISTRY.md
docs/03_PROVIDER_GATEWAY.md
docs/04_HERMES_CONTRACT.md
docs/05_CALLING_FOUNDATION.md
docs/06_WORKSPACE_AND_REPOSITORY_STATUS.md
docs/07_KNOWN_LIMITATIONS.md
docs/08_PRE_HERMES_READINESS_REPORT.md
docs/09_DECISION_LOG.md
docs/10_AJ_ORB.md
Drive
Drive/AI_WORKSPACE
Drive/AI_WORKSPACE/AJ
ENGINEERING_AUDIT
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/AUDIT_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/BACKUP_RESTORE_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/CANCELLATION_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/CLI_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/CONCURRENCY_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/CONFIG_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/IMPLEMENTATION_SUMMARY
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/KNOWN_ISSUES
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/LIFECYCLE_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/MASTER_REPORT
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/NEXT_PHASE
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/PERFORMANCE_SANITY
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/RECOVERY_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/RETRY_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/SECURITY_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_03_1/SUMMARY_VERIFICATION
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/ARCHITECTURE.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/BACKUP_RESTORE_VALIDATION.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/BATCH_1_IMPLEMENTATION_REPORT.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/BATCH_1_VERIFICATION_REPORT.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/CHANGED_FILES.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/CRASH_RECOVERY_MATRIX.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/CRASH_RECOVERY_RESULTS.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/DEPENDENCY_AND_LINEAGE.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/EVIDENCE_REGISTER.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/EXECUTIVE_SUMMARY.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/FEATURE_EVIDENCE_MATRIX.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/IDEMPOTENCY_GUARANTEES.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/JOURNAL_AND_RECEIPT_CONSISTENCY.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/KNOWN_LIMITATIONS_BATCH_2.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/KNOWN_LIMITATIONS.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/MASTER_REPORT.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/NEXT_PHASE_RECOMMENDATION.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/PERFORMANCE_REPORT.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/RETENTION_ASSESSMENT.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/RETRY_AND_DEAD_LETTER_POLICY.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/SECURITY_REDACTION_RESULTS.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/SECURITY_VALIDATION.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/STORAGE_VERSIONING.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/TEST_COUNT_RECONCILIATION.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/TEST_EVIDENCE.md
ENGINEERING_AUDIT/IMPLEMENTATION_PHASE_04/TEST_RESULTS.md
ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13
ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/00_MASTER_REPORT.md
ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/01_ARCHITECTURE_AND_CAPABILITY_INVENTORY.md
ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/02_REQUIREMENTS_COVERAGE_AND_CAPABILITY_MATRIX.md
ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/03_MASTER_ISSUE_BACKLOG.md
ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/04_RESOLVED_ISSUES_AND_EVIDENCE.md
ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/05_TEST_AND_STRESS_RESULTS.md
ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/06_SECURITY_RELIABILITY_LIMITATIONS_AND_ROADMAP.md
ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13
ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/00_PREFLIGHT_AND_ACTUAL_STATE.md
ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/01_IDENTITY_TRUST_ARCHITECTURE_AND_THREAT_MODEL.md
ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/02_MULTI_STORE_CONSISTENCY_INVESTIGATION.md
ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/03_UPDATED_BACKLOG_DELTA.md
ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/04_TEST_AND_REGRESSION_RESULTS.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/00_MASTER_INTEGRATION_READINESS_REPORT.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/01_REPOSITORY_AND_RUNTIME_INVENTORY.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/02_CAPABILITY_OWNERSHIP_MATRIX.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/03_INTERFACE_AND_CONTRACT_CATALOG.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/04_INTEGRATION_COMPATIBILITY_MATRIX.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/05_MEMORY_AND_DATA_OWNERSHIP.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/06_SECURITY_AND_TRUST_BOUNDARY_ASSESSMENT.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/07_TASK_LIFECYCLE_AND_FAILURE_ANALYSIS.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/08_PROVIDER_AND_EXTERNAL_DEPENDENCY_STATUS.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/09_MASTER_INTEGRATION_BACKLOG.md
ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/10_PHASE_4B_IMPLEMENTATION_PLAN.md
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/00_PHASE_4B_0_MASTER_DESIGN_REPORT.md
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/01_HELIX_REPOSITORY_COMPARISON_AND_DECISION.md
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/02_HERMES_INTERFACE_SELECTION.md
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/03_AJ_HERMES_VERSIONED_CONTRACT.md
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/04_SECURITY_PERMISSION_AND_IDENTITY_DESIGN.md
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/05_MEMORY_AND_DATA_OWNERSHIP_CONTRACT.md
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/06_EXECUTION_LIFECYCLE_FAILURE_AND_RECOVERY.md
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/07_CONTRACT_TEST_STRATEGY.md
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/08_PHASE_4B_1_IMPLEMENTATION_BLUEPRINT.md
ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/09_ARCHITECTURAL_DECISIONS_AND_OPEN_QUESTIONS.md
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/00_PHASE_4B_1_MASTER_IMPLEMENTATION_REPORT.md
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/01_PREFLIGHT_AND_CLI_SAFETY_VERIFICATION.md
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/02_ADAPTER_ARCHITECTURE_AND_MODULE_MAP.md
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/03_CONTRACT_AND_STATUS_MAPPING.md
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/04_AUTHORIZATION_PERMISSION_AND_FEATURE_FLAGS.md
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/05_OPERATION_EVIDENCE_AND_RECOVERY.md
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/06_TEST_RESULTS_AND_FAULT_INJECTION.md
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/07_SECURITY_REVIEW_AND_LIMITATIONS.md
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/08_LIVE_INTEGRATION_VERIFICATION.md
ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/09_PHASE_4B_2_READINESS_AND_RECOMMENDATION.md
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/00_PHASE_4B_2_MASTER_REPORT.md
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/01_BASELINE_AND_GIT_PRESERVATION.md
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/02_RELIABILITY_GAP_ANALYSIS.md
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/03_PROCESS_LIFECYCLE_AND_TIMEOUT_HARDENING.md
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/04_OUTPUT_VALIDATION_AND_REDACTION.md
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/05_FAILURE_CLASSIFICATION_AND_RECOVERY.md
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/06_TEST_RESULTS_AND_FAULT_INJECTION.md
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/07_LIVE_READ_ONLY_VERIFICATION.md
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/08_SECURITY_INVARIANTS_AND_LIMITATIONS.md
ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/09_PHASE_4B_3_READINESS_RECOMMENDATION.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/00_PHASE_4B_3_MASTER_REPORT.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/01_BASELINE_AND_REPOSITORY_PRESERVATION.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/02_THREAT_MODEL_AND_ATTACK_SURFACE.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/03_SECURITY_SOURCE_AUDIT.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/04_ADVERSARIAL_TEST_MATRIX.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/05_SECURITY_HARDENING_IMPLEMENTATION.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/06_SECURITY_TEST_RESULTS.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/07_EVIDENCE_AND_OUTCOME_INTEGRITY.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/08_SECURITY_LIMITATIONS_AND_RESIDUAL_RISKS.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/09_PHASE_4B_4_READINESS_RECOMMENDATION.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/10_SQLITE_CONCURRENCY_ROOT_CAUSE_INVESTIGATION.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/11_SQLITE_DIAGNOSTIC_TEST_RESULTS.md
ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/12_SQLITE_REMEDIATION_RECOMMENDATION.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/00_PHASE_4B_4_MASTER_READINESS_REPORT.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/01_BASELINE_AND_PRESERVATION.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/02_CURRENT_SECURITY_BASELINE.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/03_EXECUTION_READINESS_MATRIX.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/04_FUTURE_CAPABILITY_CANDIDATES.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/05_CAPABILITY_RISK_COMPARISON.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/06_CONTRACT_GAP_ANALYSIS.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/07_FAILURE_AND_RECOVERY_MODEL.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/08_PERMISSION_CONFIRMATION_AND_SIDE_EFFECT_MODEL.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/09_OBSERVABILITY_AND_EVIDENCE_REQUIREMENTS.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/10_SECURITY_GATE_AND_ACCEPTANCE_CRITERIA.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/11_SQLITE_BLOCKING_ASSESSMENT.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/12_TEST_RESULTS.md
ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/13_PHASE_4B_5_IMPLEMENTATION_RECOMMENDATION.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/00_PHASE_4B_5_MASTER_REPORT.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/01_BASELINE_AND_REPOSITORY_PRESERVATION.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/02_HERMES_COMMAND_AND_SOURCE_TRACE.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/03_GATEWAY_ENSURE_SIDE_EFFECT_ANALYSIS.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/04_IDEMPOTENCY_AND_CONCURRENCY_ANALYSIS.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/05_LIFECYCLE_FAILURE_AND_RECOVERY_ANALYSIS.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/06_SECURITY_AND_PERMISSION_ANALYSIS.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/07_RESOURCE_AND_RUNTIME_IMPACT.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/08_TEST_AND_VERIFICATION_EVIDENCE.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/09_DECISION_AND_IMPLEMENTATION_ENTRY_CRITERIA.md
ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/10_ARCHITECTURAL_REQUIREMENTS_AND_DEFERRED_WORK.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/00_PHASE_4B_6_MASTER_REPORT.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/01_ENTRY_CRITERIA_TRACEABILITY.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/02_GATEWAY_STATE_AND_ACTION_MATRIX.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/03_IDEMPOTENCY_AND_CONCURRENCY_DESIGN.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/04_READBACK_AND_VERIFICATION_CONTRACT.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/05_FAILURE_RECOVERY_AND_AMBIGUITY_POLICY.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/06_SECURITY_AND_PERMISSION_BOUNDARY.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/07_RESOURCE_AND_BACKPRESSURE_POLICY.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/08_ISOLATED_TEST_DESIGN_AND_EVIDENCE.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/09_STORAGE_RELIABILITY_POSTURE.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/10_VERSIONED_CAPABILITY_CONTRACT_PROPOSAL.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/11_CONCURRENT_ORCHESTRATION_COMPATIBILITY.md
ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/12_FINAL_DECISION_AND_NEXT_PHASE.md
ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14
ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/00_BASELINE_AND_SCOPE.md
...
ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/57_PHASE_5A7_GATE_B_REVIEW_AND_S0_CLOSURE_REPORT.md
ENGINEERING_AUDIT/READINESS_AUDIT
...
README.md
pyproject.toml
tests
tests/test_*.py
... (truncated display; full depth-3 listing captured in _context_pack/_tmp_tree3.txt)
```

> Note: `_context_pack/` (analysis output) and its `_tmp_*` helper files were created during this read-only pack generation; they are new working-tree artifacts.

## `aj/` modules (one line per module: purpose, lines, public/top-level API)

Source: `wc -l aj/*.py`, module docstrings, and `ast`-extracted top-level defs.

| Module | Purpose (first docstring line) | Lines | Public classes/functions (top-level, name heuristic) | All top-level defs |
|---|---|---:|---|---|
| `aj/__init__.py` | AJ — the ecosystem control plane (pre-Hermes foundation). | 40 | (none) | (none) |
| `aj/__main__.py` | AJ command line: operate the local control plane. | 1004 | `exit_code_for`, `build_parser`, `main` | `exit_code_for, _emit, _iso, _print_run, _print_task, _print_tasks, _print_audit, _print_memory, _add_json, build_parser, _tasks_dir, _audit_dir, _memory, _cmd_run, _cmd_tasks, _cmd_task, _cmd_cancel, _cmd_retry, _cmd_audit, _cmd_memory, _cmd_summary, _cmd_capabilities, _cmd_permissions, _cmd_config, _cmd_diagnostics, _cmd_export, _cmd_import, _cmd_backup, _cmd_recover, _cmd_reconcile, _cmd_orb, _cmd_consistency, main` |
| `aj/actions.py` | Safe capabilities that execute inside AJ. | 128 | `InternalActions`, `echo`, `health_check`, `default_actions`, `specs`, `register_specs` | same |
| `aj/agents.py` | Agent boundary — how AJ talks to JARVIS and HELIX. | 234 | `AgentPort`, `HttpAgentAdapter`, `UnconfiguredAgent`, `AgentRegistry` | `AgentPort, _probe, HttpAgentAdapter, UnconfiguredAgent, AgentRegistry` |
| `aj/audit.py` | Audit trail. | 297 | `AuditEvent`, `AuditSink`, `MemoryAuditSink`, `JsonlAuditSink`, `AuditRecordResult`, `AuditLog`, `read_jsonl`, `AuditReadResult`, `read_events`, `iter_events` | includes `_validate_audit_directory, _redact` |
| `aj/authorization.py` | Privileged-operation authorization guardrails. | 403 | `AuthorizationContext`, `AuthorizationDecision`, `PrivilegedOperationAuthorizer`, `LocalTrustPrivilegedAuthorizer`, `UnavailablePrivilegedAuthorizer`, `build_privileged_authorizer` | includes `_runtime_provenance, _CallableIdentityAuthorizerAdapter` |
| `aj/calling.py` | Calling foundation — the contracts HELIX owns and AJ supervises. | 387 | `CallState`, `Contact`, `AmbiguousContact`, `ContactResolver`, `BridgeCapabilities`, `DeviceBridge`, `NullDeviceBridge`, `CallRecord`, `CallingService` | same |
| `aj/capability.py` | Capability registry. | 283 | `CapabilitySpec`, `CapabilityRegistry` | same |
| `aj/config.py` | Layered configuration. | 391 | `invalid_path_reason`, `require_path`, `Config`, `load`, `memory_path`, `validate` | includes `_deep_merge, _coerce, _env_overrides, _writable_path` |
| `aj/consistency.py` | Read-only task/audit/journal/operation-evidence consistency checking. | 306 | `check_consistency` | `_safe_read_jsonl, _finding, check_consistency` |
| `aj/contracts.py` | Boundary contracts. | 314 | `AgentRequest`, `AgentResult`, `ExecutionRequest`, `ExecutionResult`, `SkillSpec`, `new_request_id` | same |
| `aj/delegation.py` | Agent assignment, task delegation, and hierarchical orchestration foundation (5A.6). | 1100 | `stable_delegation_id`, `stable_assignment_id`, `LogicalAgentRecord`, `DelegationRequest`, `DelegationRecord`, `AssignmentRecord`, `AppendOnlyJsonlStore`, `DelegationStore`, `AssignmentStore`, `LogicalAgentStore`, `compute_root_task_id`, `validate_parent_chain`, `match_agent`, `narrow_permissions`, `aggregate_parent_progress`, `detect_delegation_anomalies` | includes `_norm_str, _norm_str_list, _capability_state, _child_snapshot_hash` |
| `aj/diagnostics.py` | Read-only operator diagnostics. | 115 | `gather` | `_iso, _mtime, gather` |
| `aj/errors.py` | Error taxonomy and normalisation. | 162 | `AjError` + error classes, `normalize` | (many error classes) |
| `aj/execution.py` | Execution boundary — where Hermes will attach. | 147 | `ExecutionPort`, `UnavailableExecutionAdapter`, `SkillRegistry`, `execute` | same |
| `aj/execution_domain.py` | First-class Execution domain foundation (Phase 5A.4). | 257 | `ExecutionRecord`, `validate_record`, `ExecutionStore` | same |
| `aj/hermes_adapter.py` | Hermes CLI execution adapter (minimal, read-only spike). | 499 | `RunnerResult`, `default_runner`, `HermesExecutionAdapter` | includes `_checked_int, _drain_limited` |
| `aj/hermes_contract.py` | AJ↔Hermes v0 contract helpers (read-only spike). | 204 | `redact_text`, `V0Request`, `validate_request`, `normalize_status`, `response_envelope` | includes `_nonempty_str` |
| `aj/idempotency.py` | Persistent idempotency keys scoped to a capability. | 64 | `IdempotencyStore` | same |
| `aj/ids.py` | Identifier generation. | 47 | `new_task_id`, `new_child_id`, `new_call_id`, `new_skill_id`, `new_execution_id`, `new_delegation_id`, `new_assignment_id` | same |
| `aj/inbox.py` | AJ Personal Knowledge Inbox. | 719 | `default_data_dir`, `default_inbox_root`, `resolve_inbox_root`, `inbox_root`, `ensure_layout`, `utc_now`, `new_capture_id`, `sha256_bytes`, `sha256_file`, `canonical_url`, `looks_like_url`, `detect_platform`, `safe_filename`, `InboxStore`, `capture_file`, `capture_url`, `capture_text`, `process_capture`, `process_pending`, `retry_failed`, `inbox_summary` | includes helpers `_validated_inbox_root_value, _write_metadata_json, _record_base, _write_extracted, _extract_text_from_pdf, _extract_youtube` |
| `aj/inbox_cli.py` | CLI integration for AJ Personal Knowledge Inbox. | 372 | `add_inbox_parser`, `cmd_inbox` | `_emit, _store, _print_item, add_inbox_parser, cmd_inbox` |
| `aj/inbox_view.py` | Lightweight local inbox inspection surface (stdlib HTTP server). | 186 | `render_index`, `render_item`, `Handler`, `serve` | `_h, ...` |
| `aj/invariants.py` | Read-only invariant checks over persisted task, lease and receipt state. | 59 | `check` | same |
| `aj/journal.py` | Append-only execution journal. | 104 | `Journal` | same |
| `aj/lease.py` | Per-task operation and execution leases. | 563 | `Lease`, `LeaseManager` | includes `_atomic_json, _dump_leases, _load_leases` |
| `aj/locking.py` | Advisory file locking (POSIX). | 91 | `available`, `file_lock`, `lock_status` | same |
| `aj/memory.py` | Canonical memory, independent of any provider. | 272 | `Event`, `MemoryPort`, `MemoryStore` | same |
| `aj/operation_evidence.py` | Durable, append-only evidence for privileged operations. | 235 | `OperationEvidenceView`, `OperationEvidenceStore` | `_safe, ...` |
| `aj/orb.py` | AJ Floating Capture Orb (GTK3). | 1287 | `load_orb_state`, `save_orb_state`, `notify`, `OrbInstanceLock`, `web_orb_available`, `run_orb` | includes helpers/`_parse_args` |
| `aj/orb_autostart.py` | Helpers to install/remove AJ Orb autostart for the current user. | 63 | `desktop_entry`, `autostart_dir`, `default_exec_cmd`, `install`, `remove` | same |
| `aj/orb_web.py` | AJ Orb web host (WebKitGTK 4.1 + GTK3). | 1134 | `dist_index_path`, `web_gui_available`, `map_record_to_item`, `snapshot_state`, `notify`, `load_orb_state`, `save_orb_state`, `OrbInstanceLock`, `PendingDrop`, `run_orb_web` | includes helpers/`_parse_args` |
| `aj/orchestrator.py` | The AJ control plane. | 4507 | `Route`, `Router`, `TaskOutcome`, `Aj`, `build` | same |
| `aj/permissions.py` | Five-level permission model and the approval gate. | 318 | `level_from_tier`, `level_name`, `validate_level`, `canonical_fingerprint`, `Approval`, `ApprovalGate`, `PolicyDecision`, `Authorizer` | same |
| `aj/providers.py` | Provider gateway. | 361 | `Message`, `ChatRequest`, `ChatResponse`, `ModelSpec`, `ProviderSpec`, `ProviderAdapter`, `OpenAICompatibleAdapter`, `MockProvider`, `Health`, `ProviderRegistry`, `Gateway` | same |
| `aj/receipts.py` | Durable execution receipts, one per finished attempt. | 93 | `ReceiptStore` | `_safe, ReceiptStore` |
| `aj/recovery.py` | Conservative, evidence-based recovery for persisted tasks. | 133 | `Finding`, `classify`, `RecoveryManager` | `Finding, _map_assessment, classify, RecoveryManager` |
| `aj/retention.py` | Non-destructive retention assessment. | 72 | `assess` | same |
| `aj/runtime.py` | AJ runtime assembly and self-check. | 584 | `configure_logging`, `build_memory`, `assemble`, `health`, `run_demo` | includes `_build_execution` and many `_check_*`/`_run_check` |
| `aj/scheduler.py` | Scheduler, eligibility, admission, dispatch, and monitoring foundation (5A.5). | 856 | `EligibilityDecision`, `AdmissionDecision`, `SchedulerResult`, `DispatchLedger`, `Scheduler` | same (methods on classes) |
| `aj/storage_diagnostics.py` | Storage and SQLite diagnostics (Phase 3E). | 148 | `classify_sqlite_error`, `sqlite_runtime_info`, `inspect_storage` | `_path_info, ...` |
| `aj/summary.py` | Deterministic derived summaries over canonical raw events. | 121 | `digest`, `effective_kind`, `build`, `verify`, `delete`, `summaries` | `_event_dict, ...` |
| `aj/task.py` | Task lifecycle. | 766 | `TaskRecord`, `TaskStore` | same |
| `aj/transfer.py` | Local export, import, backup and restore verification. | 239 | `collect`, `validate`, `export_file`, `import_file`, `backup_directory`, `verify_backup` | `_redact_object, _atomic_write_json, ...` |

## `docs/` files

| File | First heading |
|---|---|
| `docs/01_AJ_CONTROL_PLANE.md` | (see file) |
| `docs/02_CAPABILITY_REGISTRY.md` | (see file) |
| `docs/03_PROVIDER_GATEWAY.md` | (see file) |
| `docs/04_HERMES_CONTRACT.md` | (see file) |
| `docs/05_CALLING_FOUNDATION.md` | (see file) |
| `docs/06_WORKSPACE_AND_REPOSITORY_STATUS.md` | (see file) |
| `docs/07_KNOWN_LIMITATIONS.md` | (see file) |
| `docs/08_PRE_HERMES_READINESS_REPORT.md` | (see file) |
| `docs/09_DECISION_LOG.md` | (see file) |
| `docs/10_AJ_ORB.md` | (see file) |

## Phase 5A docs 52–57 (filename + first heading)

| File | First heading block |
|---|---|
| `ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/52_PHASE_5A_6R5_PROPOSED_NARROWED_INVARIANT_BASELINE_V1.md` | `# AJ — PHASE 5A.6R5` / `# NARROWED INVARIANT-BASED ACCEPTANCE BASELINE` / `## Proposed Engineering Contract — Version 1.0` |
| `.../53_PHASE_5A_6R5_POLICY_SEMANTICS_CLARIFICATION_PROPOSAL.md` | `# 53 — Phase 5A.6R5 Policy Semantics Clarification Proposal` |
| `.../54_PHASE_5A_6R5_CONSOLIDATED_ACCEPTANCE_BASELINE_V1_1_PROPOSAL.md` | `# 54 — Phase 5A.6R5 Consolidated Acceptance Baseline v1.1 (Proposal)` |
| `.../55_PHASE_5A7_IMPLEMENTATION_PLAN_AND_PROOF_STRATEGY.md` | `# 55 — Phase 5A.7 Implementation Plan and Proof Strategy` |
| `.../56_PHASE_5A7_REVISED_IMPLEMENTATION_PLAN_AND_PROOF_STRATEGY.md` | `# 56 — Phase 5A.7 Revised Implementation Plan and Proof Strategy` |
| `.../57_PHASE_5A7_GATE_B_REVIEW_AND_S0_CLOSURE_REPORT.md` | `# 57 — Phase 5A.7 Gate B Review and S0 Closure Report` |
