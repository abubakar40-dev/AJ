# 04 — Hermes Contract (NOT ATTACHED)

**Status:** contract implemented and tested · **integration: NONE** · awaiting HERMES GREEN SIGNAL

## 1. The port

```python
class ExecutionPort(Protocol):
    name: str
    def available(self) -> bool: ...
    def describe(self) -> dict: ...
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...
```

The only production implementation today is `UnavailableExecutionAdapter`, whose
`describe()` returns:

```json
{ "name": "none", "available": false, "reason": "no execution runtime is attached",
  "integration_status": "NOT ATTACHED",
  "requires": "HERMES GREEN SIGNAL from the project owner" }
```

Every HERMES-owned capability is declared `availability=unavailable`,
`verification_status=planned`. Requesting one produces a task in `FAILED` with
`execution_unavailable`. There is no stub runtime, no mock skill interpreter and no
shortcut that pretends integration happened.

## 2. Request contract

`ExecutionRequest` (schema: `schemas/execution_request.schema.json`):

| Field | Meaning |
|---|---|
| `request_id` | unique per invocation (`<task_id>/exec`) |
| `capability_id`, `skill_id` | what to run |
| `arguments` | plain JSON |
| `task_id` | the AJ task this belongs to |
| `permission_level` | the capability's declared level |
| `timeout_seconds`, `dry_run` | execution controls |
| `approval_token` | in-process only, **never serialised** |

## 3. Result contract

`ExecutionResult`: `status` ∈ `completed | failed | rejected | timeout | unknown`,
`output`, `error` (normalized), `side_effects`, `verified`, `verification`.

Two rules the helper enforces:

- a port that raises is a **failed** execution, not an exception that escapes;
- a port that returns a non-`ExecutionResult` is a **failed** execution.

`verified=False` stays false. A skill that did not check its own effect is not allowed to
look verified.

## 4. Skill lifecycle

```
draft → tested → reviewed → approved → (executed) → revoked
```

`SkillRegistry.register()` withholds a skill unless **all** of:

1. `review_status == "approved"`;
2. at least one recorded test, and every test `status == "PASS"`;
3. `verification_steps` non-empty;
4. a level-4 skill keeps `approval_required=True`.

Withheld skills are kept with their blocking reasons, so the system can explain why
something is unavailable instead of silently omitting it.

Declared permissions are a **ceiling**, not a grant. AJ's authorizer still decides per
invocation, and a skill that has run successfully a hundred times gains nothing.

## 5. What the owner must confirm before attachment

The contract is ready; Hermes is not. At GREEN SIGNAL, verify against the actual runtime:

1. Runtime location, version, service unit and health.
2. How a skill is invoked (CLI, gateway, MCP, HTTP) and the exact response shape.
3. Whether skills can declare and enforce their own permissions, or whether AJ must gate
   every call.
4. Cancellation and timeout semantics.
5. Where skill state and logs live (must not become canonical memory).
6. Whether the runtime can run concurrently with the existing HELIX voice services on
   6.9 GiB of RAM.

Then implement `HermesExecutionAdapter` against the port, add it in `aj/execution.py`
only, and run the isolated integration tests in `06_WORKSPACE_AND_REPOSITORY_STATUS.md`
§5. Nothing else in AJ should need to change — that is the test of whether this boundary
was worth building.

## 6. Deliberate non-goals

- Automatic skill generation.
- Permission escalation after repeated success.
- Hermes as identity, memory owner, or router.
- Replacing `~/.hermes` configuration or services as part of this phase.
