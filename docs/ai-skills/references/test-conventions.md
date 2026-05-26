# Reference: Test Conventions

This reference defines test placement, naming, traceability link format, and independence requirements. It is shared by the Verifier and Implementor skills.

For test run commands, see `docs/architecture/tech-stack.md §2`.

---

## Test Placement

| Test Type | Location Rule |
| :--- | :--- |
| Backend unit | Colocated in the same directory as the module under test (e.g., `test_service.py` alongside `service.py`) |
| Frontend unit / component | Colocated in the same directory as the component (e.g., `MyComponent.spec.ts` alongside `MyComponent.svelte`) |
| Backend integration (single module) | Colocated in the same directory as the module under test |
| Backend integration (multi-module or cross-layer) | `tests/[spec-slug]/` top-level directory |
| E2E / full user flow | `tests/[spec-slug]/` top-level directory |

`[spec-slug]` matches the spec filename slug (e.g., `tests/docker-stack/` for `SPEC-01_docker-stack.md`).

---

## Test Naming

**Python:** `test_<what_behavior_is_verified>` — describes the observable behavior being tested, not the function being called.

**TypeScript / JavaScript:** `'<what behavior is verified>'` inside `test()` or `it()` — same principle.

**Test files:**
- Python: `test_<module_name>.py`
- TypeScript/Svelte: `<ModuleName>.spec.ts` or `<ModuleName>.test.ts`

---

## Traceability Link Format

Every test function must include a traceability link as the **first line** of the test body. The link must reference the exact spec file path and requirement anchor.

### Python

```python
def test_postgres_connection_resilience():
    # REQ: docs/specs/SPEC-01_docker-stack.md#FC-01-02
    ...
```

### TypeScript / JavaScript

```typescript
test('displays active connection status container', () => {
    // REQ: docs/specs/SPEC-01_docker-stack.md#REQ-01-05
    ...
});
```

**Rules:**
- One traceability link per test function
- Each link must match an existing `REQ-XX-*` or `FC-XX-*` ID in the referenced spec
- If a test covers multiple requirements, split it into separate tests — one per requirement

---

## Test Independence

Every test must be independently runnable without depending on side effects from other tests:

- Each test sets up its own preconditions (GIVEN state)
- Each test cleans up after itself (or uses isolated fixtures)
- Tests must produce the same result regardless of execution order
- No shared mutable state between tests at module or suite level

---

## Comment Policy (Implementation Code)

This policy applies to all production code written by the Implementor:

| Comment Type | Rule |
| :--- | :--- |
| Traceability link | Required on every function/method that implements a spec requirement |
| File header | Required at top of each public module — one line: what the file is responsible for |
| Complex logic | One short inline comment explaining WHY (not WHAT) when logic would surprise a reader |
| Docstrings | Forbidden unless a framework explicitly requires them |
| Narrative / TODO comments | Forbidden unless pointing to a specific `REQ-XX-*` or `FC-XX-*` |

### Traceability Link Format (Implementation Code)

```python
# REQ: docs/specs/SPEC-01_docker-stack.md#REQ-01-03
async def start_backend_service():
    ...
```

```typescript
// REQ: docs/specs/SPEC-01_docker-stack.md#REQ-01-04
export function initFrontend() {
    ...
}
```
