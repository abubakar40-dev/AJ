# 04 — Output Validation and Redaction

## Output handling (untrusted diagnostic text)
- Hermes CLI stdout/stderr treated as untrusted, unstructured diagnostic text; never executed/interpreted as instructions.
- **Validation/normalization (conservative):** raw sanitized stdout/stderr preserved separately in payload; adapter adds `observation` classification (`exit_zero`, `nonzero_exit`, `timeout`) and explicit notes. **No semantic gateway-health inference from text content**, no parsing claims, no invented Hermes IDs/metadata.
- **Bounds:** per-stream maxima enforced during collection (`stdout_max_bytes`, `stderr_max_bytes`, min 256 / max 64KB in strict config) and redaction/truncation applied before persistence/return; truncation marked.
- **Encoding/malformed data:** bytes decoded with `utf-8` `replace`; NUL normalized; malformed/binary-ish output captured as text without crashing.

## Redaction (best-effort, not guaranteed)
Expanded patterns in `aj/hermes_contract.redact_text`:
- Key/value or header-like assignments: `api_key|token|access/refresh token|secret|client_secret|password|passwd|pwd|session|session_id|cookie|authorization` with `:` or `=`.
- Auth tokens: `Bearer <token>`, `Basic <token>`.
- Credential-bearing URLs: `scheme://user:pass@...` => `scheme://user:[REDACTED]@`.
- Env-style secret assignments: `*_KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD|SESSION|COOKIE|AUTH=*`.

Applied to stdout/stderr/error messages and selected evidence strings (e.g. CLI path/message snippets). Useful diagnostic structure retained where possible (labels/schemes preserved in common cases).

## Verified
- `test_redaction_patterns_best_effort`: Bearer, API key/token/password, credential URL, env-style secrets redacted (`[REDACTED]` present; sensitive values absent).
- Existing 4B.1 redaction test still passes (`sk-secret-token`, `hunter2` absent).
- `test_default_runner_bounds_output_during_collection_and_reports_truncation`: truncation during collection and markers.
- `test_malformed_encoding_empty_output_and_unknown_honesty`: malformed bytes handled; empty outputs classified honestly.

## Limitations
- **Best-effort only:** cannot guarantee removal of every possible secret format/encoding/obfuscation. Minimization relies on env allowlist, no secret requirements, and bounded capture.
- Truncation may remove diagnostically relevant (or sensitive) tail content; truncation is disclosed.
- `observation=exit_zero` reflects process exit only, not verified semantic runtime health. Unstructured text remains non-authoritative.