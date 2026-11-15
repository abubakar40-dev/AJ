# 01 Baseline (read-only)

## Git (AJ: `/run/media/abubakargcx/My Drive/AI_WORKSPACE/AJ`)

Commands:
- `git rev-parse HEAD`
- `git branch --show-current`
- `git status --short`
- `git status --short | wc -l`
- `git log --oneline -20`

### HEAD / branch
```
468fdcebece5b25f02e53add4928d3650ef175f4
main
```

### Status (full, grouped)

**Tracked modified (17):**
- ` M aj/__main__.py`
- ` M aj/config.py`
- ` M aj/diagnostics.py`
- ` M aj/ids.py`
- ` M aj/orchestrator.py`
- ` M aj/receipts.py`
- ` M aj/recovery.py`
- ` M aj/runtime.py`
- ` M aj/scheduler.py`
- ` M aj/task.py`
- ` M aj/transfer.py`
- ` M tests/test_foundation.py`
- ` M tests/test_orchestrator.py`
- ` M tests/test_path_config_hardening.py`
- ` M tests/test_phase2.py`
- ` M tests/test_phase3.py`
- ` M tests/test_step_c_gap_closure.py`

**Untracked (40):**
- `?? ENGINEERING_AUDIT/MASTER_CORE_AUDIT_2026-11-13/`
- `?? ENGINEERING_AUDIT/PHASE_3F_IDENTITY_TRUST_2026-11-13/`
- `?? ENGINEERING_AUDIT/PHASE_4A_ECOSYSTEM_INTEGRATION_READINESS_2026-11-13/`
- `?? ENGINEERING_AUDIT/PHASE_4B_0_DESIGN_LOCK_2026-11-13/`
- `?? ENGINEERING_AUDIT/PHASE_4B_1_MINIMAL_HERMES_ADAPTER_2026-11-13/`
- `?? ENGINEERING_AUDIT/PHASE_4B_2_RELIABILITY_HARDENING_2026-11-14/`
- `?? ENGINEERING_AUDIT/PHASE_4B_3_SECURITY_ASSURANCE_2026-11-14/`
- `?? ENGINEERING_AUDIT/PHASE_4B_4_CONTROLLED_EXECUTION_READINESS_2026-11-14/`
- `?? ENGINEERING_AUDIT/PHASE_4B_5_HERMES_GATEWAY_ENSURE_VERIFICATION_2026-11-14/`
- `?? ENGINEERING_AUDIT/PHASE_4B_6_HERMES_GATEWAY_ENSURE_DESIGN_CLOSURE_2026-11-14/`
- `?? ENGINEERING_AUDIT/PHASE_5A_CONCURRENT_ORCHESTRATION_2026-11-14/`
- `?? aj/authorization.py`
- `?? aj/consistency.py`
- `?? aj/delegation.py`
- `?? aj/execution_domain.py`
- `?? aj/hermes_adapter.py`
- `?? aj/hermes_contract.py`
- `?? aj/operation_evidence.py`
- `?? aj/storage_diagnostics.py`
- `?? integrations/`
- `?? tests/test_audit_reliability_security.py`
- `?? tests/test_phase3_lifecycle_reliability.py`
- `?? tests/test_phase3c_recovery_integrity.py`
- `?? tests/test_phase3d_recovery_observability.py`
- `?? tests/test_phase3e_evidence_consistency.py`
- `?? tests/test_phase3f_identity_trust_boundary.py`
- `?? tests/test_phase4b1_hermes_adapter.py`
- `?? tests/test_phase4b1_hermes_security_faults.py`
- `?? tests/test_phase4b2_reliability_hardening.py`
- `?? tests/test_phase4b3_security_assurance.py`
- `?? tests/test_phase4b6_gateway_ensure_design_isolated.py`
- `?? tests/test_phase5a4_execution_domain.py`
- `?? tests/test_phase5a5_scheduler_admission.py`
- `?? tests/test_phase5a6_delegation_foundation.py`
- `?? tests/test_phase5a6r2_parent_lifecycle.py`
- `?? tests/test_phase5a6r3_scenario_certification.py`
- `?? tests/test_phase5a6r4_gap_closure.py`
- `?? tests/test_phase5a6r_delegation_closure.py`
- `?? tests/test_task_creation_import_integrity.py`
- `?? tests/test_task_persistence_fail_closed.py`

**Count:** `57` entries total (17 tracked modified, 40 untracked).

### Recent log (20)
```
468fdce AJ: harden runtime path configuration
62b12ac AJ: establish initial verified baseline
```

### Comparison to expected
Expected: `main @ 468fdcebece5b25f02e53add4928d3650ef175f4`, 57 entries (17 modified, 40 untracked).  
**MATCH.** No differences in HEAD, branch, total/status composition, or counts. (`_context_pack/` created during this read-only analysis is a new untracked directory not present in baseline count above? note: baseline captured before/during run; `git status` in this section reflects state at capture time. Creating `_context_pack/` adds an untracked path — see `09_gaps_and_unknowns.md` for current working-tree note.)

## Peer repositories (names + HEAD + branch + status count only)

| Repo | HEAD | Branch | `git status --short | wc -l` | Sample |
|---|---|---|---:|---|
| `/run/media/abubakargcx/My Drive/AI_WORKSPACE/JARVIS` | `d93c7027cd509c75eb6414d822017d320a8a06c2` | `audit/consolidation-2026-11-06` | 2 | `?? chat_history/2026-11-04.md`, `?? chat_history/2026-11-05.md` |
| `/run/media/abubakargcx/My Drive/AI_WORKSPACE/HELIX` | MISSING (directory not present) | n/a | n/a | n/a |
| `~/.hermes/hermes-agent` | `2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19` | (detached/empty branch name reported) | 0 | |

## Environment

- **Python:** `Python 3.14.4`
- **OS:** Ubuntu 26.04.1 LTS (Resolute Raccoon) (`/etc/os-release`)
- **Kernel:** `Linux 7.0.0-43-generic x86_64 GNU/Linux`
- **SQLite (python sqlite3 module):** `3.46.1`
- **pip freeze (top-level capture, first 80 lines):** see below (truncated to observed output; secrets not present in captured lines).

```text
absl-py==2.5.0
aptdaemon==2.0.2
attrs==25.4.0
autocommand==2.2.2
babel==2.17.0
bcc==0.35.0
bcrypt==5.0.0
beautifulsoup4==4.14.3
blinker==1.9.0
Brlapi==0.8.6
Brotli==1.2.0
certifi==2026.1.4
cffi==2.1.1
chardet==5.2.0
click==8.1.8
command-not-found==0.3
configobj==5.0.9
contourpy==1.4.0
cryptography==46.0.5
cssselect==1.4.0
cupshelpers==1.0
cycler==0.12.1
dasbus==1.7
dbus-python==1.4.0
defer==1.0.6
distro==1.9.0
distro-info==1.15
evdev==2.0.0
flatbuffers==25.12.19
fonttools==4.65.0
gyp-next==0.16.2
html5lib-modern==1.2
httplib2==0.22.0
idna==3.11
inflect==7.5.0
iniconfig==2.3.1
jaraco.context==6.0.1
jaraco.functools==4.1.0
jaraco.text==4.0.0
Jinja2==3.1.6
jsonpatch==1.32
jsonpointer==2.4
jsonschema==4.19.2
jsonschema-specifications==2023.12.1
kiwisolver==1.5.1
language-selector==0.1
launchpadlib==2.1.0
lazr.restfulclient==0.14.6
lazr.uri==1.0.6
libpass==1.9.3
linkify-it-py==2.0.3
louis==3.36.0
lxml==6.0.2
lz4==4.4.5+dfsg
markdown-it-py==3.0.0
MarkupSafe==3.0.3
matplotlib==3.11.2
mdurl==0.1.2
more-itertools==10.8.0
MouseInfo==0.1.3
mpmath==1.3.0
munkres==1.1.4
netaddr==1.3.0
numpy==2.3.5
oauthlib==3.3.1
olefile==0.47
opencv==4.10.0
opencv-contrib-python==5.0.0.93
opencv-python==5.0.0.93
packaging==26.0
pdf2image==1.17.0
pexpect==4.9.0
pgvector==0.5.1
pillow==12.1.1
pluggy==1.7.0
psutil==7.1.0
psycopg==3.3.8
ptyprocess==0.7.0
PyAutoGUI==0.9.54
pycairo==1.27.0
... (truncated; full freeze longer)
```

## Filesystem / mount / temp

Commands:
- `findmnt -T .`
- `findmnt -T /tmp`
- `findmnt -T /run/media/abubakargcx/My\ Drive/easy-diffusion/tmp/opencode`
- `findmnt -T /home/abubakargcx/easy-diffusion/tmp`
- `stat -f . /tmp /home/abubakargcx/easy-diffusion/tmp "/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp"`
- `df -T . /tmp`
- `python3 -c "import tempfile; print(tempfile.gettempdir())"`

| Path | Source/FSType | Mount options (observed) | Notes |
|---|---|---|---|
| AJ root (`.`) | `/dev/sda4` / `ntfs3` | `rw,nosuid,nodev,relatime,uid=1000,gid=1000,acl,iocharset=utf8,prealloc` | NTFS workspace |
| `/tmp` | `tmpfs` / `tmpfs` | `rw,nosuid,nodev,nr_inodes=1048576,inode64,usrquota` | local tmpfs |
| Default pytest basetemp dir from `tempfile.gettempdir()` | `/home/abubakargcx/easy-diffusion/tmp` | resolves on same NTFS mount (`/dev/sda4`, `ntfs3`, options as above) | **Important:** default temp base is on NTFS mount in this environment |
| NTFS test basetemp used in runs | `/run/media/abubakargcx/My Drive/easy-diffusion/tmp/opencode/aj-pytest-basetmp` | same NTFS mount (`/dev/sda4`, `ntfs3`) | |

`df -T` (observed): `/dev/sda4 ntfs3 104856572 1K-blocks ... 35% /run/media/abubakargcx/My Drive`; `tmpfs tmpfs ... /tmp`.
`stat -f`: AJ/NTFS paths report `Type: UNKNOWN (0x7366746e)`, `Inodes: Total 0 Free 0`; `/tmp` reports `Type: tmpfs`.
