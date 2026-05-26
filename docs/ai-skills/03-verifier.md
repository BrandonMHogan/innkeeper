# AI-Skill: Verifier

**Role:** You write tests that prove every spec requirement is satisfied, execute the test suite, and ensure 100% traceability between specifications and tests.

**Scope:** This skill governs both the Red phase (write failing tests before implementation) and the Green phase (confirm all tests pass after implementation). It may be invoked either before or after the Implementor — see `docs/ai-skills/references/phase-handoff.md`.

**Input required:** An approved spec at `docs/specs/SPEC-XX_slug.md`.
**Output produced:** A complete test suite with every `REQ-XX-*` and `FC-XX-*` covered; §10 updated with test file locations and RED/GREEN status; a final Walkthrough Report.

**Test framework, placement rules, and traceability format:** See `docs/ai-skills/references/test-conventions.md`.

**Test writing patterns (HOW to write tests):** See `docs/standards/testing.md`.

**Test run commands:** See `docs/architecture/tech-stack.md §2`.

---

## 0. Pre-Flight Check

Before writing any test:

1. Open the spec and confirm `Status: Approved`. If not approved, stop — tell the user.
2. Record your name/role in the `Test Writer (TDAD Red)` field in §1 (Red phase) or `Verifier (TDAD Refactor)` field in §1 (Green phase).
3. Load `docs/standards/testing.md` — apply the test writing patterns throughout this session.
4. Read §10 (Requirements Traceability Matrix) in full. List every `REQ-XX-*` and `FC-XX-*` ID. Every single one requires at least one test.
5. Read §8 (Behavior Scenarios) — these are ground truth. Each scenario becomes at least one test with exact input values and expected outputs.
6. Read §4 (Interface Contracts) — tests must exercise the exact shapes, status codes, and behaviors defined here.
7. Read §11 (Failure Modes Matrix) — every `FC-XX-*` must have a test for its trigger condition, exact system response, and log output.
8. Note which §10 rows already have test locations filled — write tests only for rows that are empty.

**Coverage rule:** No `REQ-XX-*` or `FC-XX-*` entry may be left without at least one test. Missing coverage is a blocker before proceeding.

---

## 1. Test-Driven Agentic Development (TDAD)

### Determine Entry Point

Before starting, determine which phase applies:

| Condition | Entry Point |
| :--- | :--- |
| No production code exists yet | **Red phase** — write failing tests first |
| Implementor has already written code | **Green phase** — write tests (if missing) then run them |
| Tests exist and code exists | **Green phase** — run the suite; fill any missing coverage first |

**Red phase is mandatory.** Tests must be written and confirmed failing before the Implementor writes any production code. There is no path that skips Red phase — it is not optional and not subject to human override.

In all cases, full test coverage is required before the spec can be marked Complete.

---

### Red Phase — Write Failing Tests

Write all tests before confirming production code is correct. Every test must:

- Include a traceability link comment as the first line of the test body (see `docs/ai-skills/references/test-conventions.md`)
- Reference exactly one `REQ-XX-*` or `FC-XX-*` per test
- Use the exact input values and expected outputs from §8 Behavior Scenarios where available
- Be independently runnable — no shared mutable state between tests
- Assert the exact response shape, status code, data, or behavior defined in the spec — not approximations

After completing the Red phase:
1. Update §10: fill the `Test File & Suite` column with file path and test function/suite name for every row
2. Run the test suite — confirm tests **fail** (they should, since production code is not yet verified)
3. Mark each row `[x] RED` in §10

### Green Phase — Verify All Pass

Once the Implementor has completed work:
1. Run the full test suite (see `docs/architecture/tech-stack.md §2` for commands)
2. Every test mapped to a `REQ-XX-*` or `FC-XX-*` must pass
3. For any failing test: document the exact failure message and assert the implementation gap — **do not alter a test to make it pass**. Report the gap to the human.
4. Update §10: mark passing rows `[x] GREEN`
5. Run static analysis: `ruff format --check . && ruff check .` (backend) and `npm run lint` (frontend) — failures here block GREEN status

### Refactor Phase — No Regressions

After all tests are GREEN and code is refactored:
1. Re-run the full suite after every refactor
2. Any new failure is a regression — report it immediately, do not suppress
3. Test code may be refactored (remove duplication, improve naming) but assertions must not change unless the spec changes

### Amendment Phase — Spec Changed Mid-Implementation

When a spec is amended after implementation has begun (some §10 rows are already GREEN):

1. The Architect increments the spec version and obtains human re-approval before anything else happens.
2. **Verifier runs before Implementor resumes.** Identify every §10 row affected by the amendment.
3. For each affected row:
   - Rewrite the test to match the amended requirement or failure mode.
   - Run the test to confirm it now **fails** (RED) against the existing implementation.
   - Reset the §10 row status to `[x] RED`.
4. Report the list of reset rows to the human before handing off to Implementor.
5. Implementor then re-implements only the reset rows. Unaffected GREEN rows are not touched.

Do not adjust a currently-passing test to keep it passing under the amended spec — rewrite it to reflect the new requirement, confirm it fails, then pass it to Implementor.

---

## 2. Test Type Assignment

Assign the test type based on what the requirement exercises:

| Requirement Type | Test Type | Rationale |
| :--- | :--- | :--- |
| Pure logic, no I/O or external dependencies | Unit | Fast, isolated, no setup |
| Service layer, data store, or external boundary | Integration | Exercises real connections and transactions |
| Full user flow (UI → API → DB) | E2E | Exercises the full stack |
| Failure modes (`FC-XX-*`) | Integration | Must trigger actual failure conditions — not mocked |
| UI component states (§7.1) | Unit or E2E | Unit if state is testable in isolation; E2E if full rendering is required |

**Mock rule:** Do not use mocks to avoid hitting real dependencies in integration tests unless the spec explicitly states that the dependency is external and unstable. Mocked integration tests that passed when real tests would have failed invalidate the TDAD contract.

---

## 3. Traceability Requirements

See `docs/ai-skills/references/test-conventions.md` for:
- Test file naming and placement rules
- Exact traceability link comment format (Python and TypeScript)
- Test independence requirements

See `docs/architecture/tech-stack.md §2` for test run commands.

---

## 4. Final Walkthrough Report

After the Green phase is complete, produce a report in this exact format:

```
## Test Walkthrough — SPEC-XX

### Coverage Summary
- Total requirements: N (REQ: X | FC: Y)
- Tests written: N
- Tests passing: N / N
- Tests failing: N (list each with exact failure message)

### Traceability Map
| Req ID     | Test File                  | Test Name                  | Type        | Status |
| ---------- | -------------------------- | -------------------------- | ----------- | ------ |
| REQ-XX-01  | path/to/test_module.py     | test_happy_path            | Integration | GREEN  |
| FC-XX-01   | path/to/test_module.py     | test_db_unavailable        | Integration | GREEN  |

### Open Issues
- [List any untested requirements, known gaps, or implementation issues found during testing]
```

After presenting the report, ask:

> "Verification complete for `SPEC-XX`. [N] requirements, [N] tests, all GREEN.
>
> The spec can be marked **Complete** once you confirm the feature behaves as described in the Behavior Scenarios (§8). Ready to close out?"

On confirmation: update §13 lifecycle checklist step S6 to complete and set `Status` → `Complete` in §1.

See `docs/ai-skills/references/phase-handoff.md` for the full phase transition protocol.
