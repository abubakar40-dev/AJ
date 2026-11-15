# TEST_RUN_PROTOCOL (round 4)

## Standard regression-gate command (environment setting, not a test change)
```bash
python3 -m pytest -q --basetemp=/tmp/aj-pytest-std
```
- Run from `AJ/` repo root: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`
- `PYTHONDONTWRITEBYTECODE=1` used in recorded runs to avoid bytecode side effects.
- **This is an environment/basetemp setting, not a test edit.** No existing tests were modified. The flag controls where pytest places `tmp_path`/basetemp artifacts.
- **Why:** in this environment `TMPDIR` points to `/home/abubakargcx/easy-diffusion/tmp` (on NTFS workspace storage context / `easy-diffusion/tmp`), and prior S0 evidence showed NTFS workspace paths can produce intermittent SQLite/WAL-related `sqlite3.OperationalError: disk I/O error` for the concurrent memory writer test. Using `--basetemp=/tmp/aj-pytest-std` places pytest temp artifacts on `/tmp` for the standard gate run; this does not change test logic, only artifact location.

## Separate T-12 evidence command (NTFS basetemp)
```bash
python3 -m pytest -q --basetemp="/run/media/abubakargcx/My Drive/easy-diffusion/tmp/aj-pytest-ntfs"
```
- Records behavior with pytest basetemp on NTFS-backed easy-diffusion tmp path (separate from standard gate). Relevant to T-12/SQLite storage-sensitivity evidence.

## Standard command results (3 runs, recorded)
| Run | Command context | Exact summary (tail) | Exit |
|---:|---|---|---|
| 1 | `rm -rf /tmp/aj-pytest-std && mkdir -p /tmp/aj-pytest-std && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --basetemp=/tmp/aj-pytest-std` | `1 failed, 581 passed, 11 xfailed, 13 warnings in 68.62s (0:01:08)` (FAILED `tests/test_crash_safety.py::test_multi_process_recovery_same_operation`, AssertionError `assert (False is True or False is True)`) | 0 (pytest process exit as captured in `/tmp/std_run1.txt`) |
| 2 | same (fresh basetemp dir) | `581 passed, 11 xfailed, 16 warnings, 1 error in 68.47s (0:01:08)` (ERROR at setup of `tests/test_audit_reliability_security.py::test_reconcile_evidence_incomplete_is_reported_not_silent_success`: `FileExistsError: [Errno 17] File exists: '/tmp/aj-pytest-std'` during basetemp mkdir/cleanup race; PytestWarnings about rm_rf on non-empty leftovers) | 0 (as captured in `/tmp/std_run2.txt`) |
| 3 | same (fresh basetemp dir) | `1 failed, 581 passed, 11 xfailed, 13 warnings in 67.30s (0:01:07)` (FAILED `tests/test_audit_reliability_security.py::test_clear_recovery_required_fails_closed_on_completion_receipt_conflict`, `assert True is False` from `res.get("ok")`) | 0 (as captured in `/tmp/std_run3.txt`) |

**Fact:** under this protocol, results were not identical across 3 runs (different failures/error mode observed). This is recorded factually; not attributed to any `aj/` edit in this round (no `aj/` edits made).

## NTFS basetemp command result (1 run, recorded)
| T-12 (NTFS) | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --basetemp="/run/media/abubakargcx/My Drive/easy-diffusion/tmp/aj-pytest-ntfs"` | `582 passed, 11 xfailed, 13 warnings in 60.79s (0:01:00)` | 0 (as captured in `/tmp/ntfs_run.txt`) |

Raw logs referenced: `/tmp/std_run1.txt`, `/tmp/std_run2.txt`, `/tmp/std_run3.txt`, `/tmp/ntfs_run.txt`.
