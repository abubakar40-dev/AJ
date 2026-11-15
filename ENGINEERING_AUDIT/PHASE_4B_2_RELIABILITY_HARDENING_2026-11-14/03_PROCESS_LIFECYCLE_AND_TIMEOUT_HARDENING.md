# 03 — Process Lifecycle and Timeout Hardening

## Implementation (additive, bounded)
- **Spawn:** `subprocess.Popen` with `shell=False`, fixed argv list, controlled env allowlist, `cwd=os.getcwd()`, captured stdout/stderr pipes. POSIX uses `start_new_session=True` to isolate process group for timeout cleanup. Spawn failures classified as `started=false` / `spawn_failed` or `dependency_unavailable` (CLI missing/invalid path) with honest failed status.
- **Output collection (bounded during collection):** dedicated reader threads drain stdout/stderr incrementally, append up to configured per-stream maxima into buffers, then continue draining to EOF after limit (discarding excess) to avoid blocking the child; truncation flagged at collection time (`stdout_truncated`/`stderr_truncated`) and marker appended to returned text. No full unbounded pre-truncation buffering.
- **Timeout:** `proc.wait(timeout=timeout_s)` enforced by adapter-provided bounded timeout (request capped by `max_timeout_ms`, config validated in strict mode when explicitly enabled). On `TimeoutExpired`: mark `timed_out/terminated`, best-effort terminate process group and pid (SIGTERM then SIGKILL on POSIX; terminate/kill on Windows path), bounded reap waits (`0.8s`, `1.0s`, fallback `0.5s`), preserve already-collected partial bounded output (no blocking extra drains), return `timeout` with `accepted=true`, `partial=true`, and explicit note that timeout/partial output is not proof of gateway health.
- **Completion:** on normal exit, readers joined (bounded) after process exit/EOF; exit code and signal (negative rc) captured; `exit_code==0` mapped to completed probe with conservative `observation=exit_zero` (not semantic health proof), non-zero/signal mapped to failed with explicit error.
- **Cleanup:** `finally` performs best-effort kill/reap if process still running; readers close pipes on EOF/error. No cooperative Hermes cancellation claimed.

## Verified behaviors
- **Bounded collection:** 20KB/12KB flood captured within configured 1024/512-byte limits with truncation flags/markers (`test_default_runner_bounds_output_during_collection_and_reports_truncation`).
- **Timeout + partial + bounded wall time:** process printing then sleeping 10s timed out at 0.4s, returned `timed_out=True`, captured partial output, and completed in ~0.4s (process terminated/reaped) (`test_default_runner_timeout_terminates_and_collects_partial`).
- **Non-zero/signal:** exit code 7 classified failed; signal termination (injected `-15`/signal 15) mapped to failed with `terminated by signal 15` (`test_default_runner_nonzero_and_signal_classification`).
- **Repeated bounded probes:** 3 isolated live AJ-mediated runs completed consistently with fixed argv and `collection=bounded_incremental` evidence.

## Limitations
- Best-effort descendant cleanup depends on platform/process-group behavior; runner kills session/process group and pid but cannot prove no external child survives in all hostile cases.
- After timeout, additional output emitted between timeout detection and kill is not guaranteed to be captured beyond incremental buffers; outcome remains honest `timeout` (not success/failure proof).
- Read-only status command may invoke host service queries; adapter bounds duration but host-level blocking outside child lifetime is outside adapter control.