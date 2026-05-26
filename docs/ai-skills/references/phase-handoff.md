# Reference: Phase Handoff Protocol

This reference defines how work transitions between the Architect, Verifier, and Implementor phases. **Human approval is required at every phase gate.** No skill may advance past its gate without an explicit human confirmation.

---

## Phase Map

```
User request
     │
     ▼
┌─────────────┐
│  Architect  │  Produces: approved spec at docs/specs/SPEC-XX_slug.md + INDEX.md updated
└──────┬──────┘
       │ Human approves spec ("Approved")
       ▼
┌─────────────────────────────────────────┐
│  Verifier — Red Phase (mandatory)       │  Produces: failing tests + §10 filled
└──────┬──────────────────────────────────┘
       │ Human confirms tests written and failing
       ▼
┌─────────────┐
│ Implementor │  Produces: production code; marks §10 GREEN per requirement
└──────┬──────┘
       │ Human confirms implementation
       ▼
┌─────────────────────────────────────────┐
│  Verifier — Green Phase                 │  Produces: all tests passing + Walkthrough Report
└──────┬──────────────────────────────────┘
       │ Human confirms feature matches Behavior Scenarios (§8)
       ▼
  Spec Status → Complete
```

**Red phase is not optional.** There is no path from Architect directly to Implementor. Tests must be written and confirmed failing before any production code is written.

---

## Gate Rules

| Gate | Condition to Advance | Who Confirms |
| :--- | :--- | :--- |
| Architect → Verifier (Red) | Spec has `Status: Approved`; §13 steps S1–S4 marked complete; `INDEX.md` updated | Human (explicit "Approved") |
| Verifier Red → Implementor | All `REQ-XX-*` and `FC-XX-*` have tests written; §10 `Test File & Suite` column filled; all tests confirmed failing (RED) | Human |
| Implementor → Verifier Green | All §10 rows marked `[x] GREEN` by Implementor; quality gates pass | Human |
| Verifier Green → Complete | All tests pass; Walkthrough Report produced; static analysis clean | Human confirms behavior matches §8 |

---

## Handoff Questions

Each skill ends with a standardized handoff question. Do not proceed past a gate without explicit human confirmation.

**Architect ends with:**
> "Spec approved at `docs/specs/SPEC-XX_slug.md` and INDEX.md updated. Ready to proceed to **Verifier** (Red phase — write failing tests)?"

**Verifier (Red phase) ends with:**
> "All tests written and confirmed failing (Red phase). Ready to proceed to **Implementor**?"

**Implementor ends with:**
> "All requirements implemented and marked GREEN in §10. Ready to proceed to **Verifier** for the Green phase?"

**Verifier (Green phase) ends with:**
> "All [N] tests passing. Ready to mark `SPEC-XX` as **Complete**?"

---

## Phase Prerequisites Summary

| Skill | Requires Before Starting |
| :--- | :--- |
| Architect | A user request or feature description |
| Verifier (Red) | Spec at `Status: Approved` |
| Implementor | Verifier Red phase complete — §10 `Test File & Suite` column fully filled; all tests confirmed failing |
| Verifier (Green) | Implementor has completed all §10 rows marked GREEN |
