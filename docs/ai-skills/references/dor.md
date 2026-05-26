# Reference: Definition of Ready (DoR)

This is the canonical DoR checklist. It is the single source of truth shared by:
- `docs/ai-skills/01-architect.md` — Architect runs this silently before presenting any spec draft
- `docs/templates/spec-template.md §12` — Human reviewer confirms all items before approval

---

**Pillar 1 — Core Behavior**
- [ ] Problem statement answers *why this needs to exist*, not just what it does.
- [ ] Every persona who interacts with this feature has a user story.
- [ ] Happy path fully described with at least one complete Behavior Scenario with exact values.
- [ ] Every `REQ-XX-YY` is atomic and binary pass/fail. No vague language ("fast", "clean", "good UX") remains.
- [ ] Every requirement has a GIVEN clause. No ambient or unstated preconditions assumed.

**Pillar 2 — Data Boundaries**
- [ ] All data shapes owned by this module are defined in Section 4.1.
- [ ] Relationships and cardinality are expressed for every inter-entity reference.
- [ ] All external service dependencies (if any) are defined in Section 4.2 with expected response shapes and timeout contracts.
- [ ] All communication contracts are defined in Section 4.3 with idempotency stated for each operation.
- [ ] No `TBD` fields remain in Section 4.

**Pillar 3 — Failure Modes**
- [ ] Every failure mode has a row in Section 11 with a `FC-XX-*` ID.
- [ ] Every `FC-XX-*` row has a corresponding row in the Requirements Matrix (Section 10).
- [ ] Every failure mode has at least one Behavior Scenario (Section 8).
- [ ] Recovery path defined for every failure mode.
- [ ] Auth failure (`FC-XX-*`) is explicitly modeled as a failure mode.

**Pillar 4 — UX Copy** *(skip entirely if no user-facing interface)*
- [ ] All component states listed in Section 7.1 with exact copy. Empty, loading, error, and success states all present.
- [ ] All primary user flows documented in Section 7.2, including the error recovery path.
- [ ] No UI text, labels, or states left unspecified.

**Pillar 5 — Security & Permissions**
- [ ] All actor roles and permitted actions defined in Section 6.
- [ ] All operations explicitly reject unauthenticated callers. Auth failure is modeled as `FC-XX-*`.
- [ ] Data exposure rules stated. No sensitive fields, internal errors, or stack traces reach external callers.
- [ ] System privileges required (if any) are listed and tied to a Constraint.

**Completeness**
- [ ] State transitions defined (if module has stateful domain objects).
- [ ] Observability (Section 9): required if any `FC-XX-*` is defined; optional only for modules with zero failure modes.
- [ ] All `REQ-XX-*` and `FC-XX-*` IDs are unique. No duplicates across any spec in the project.
- [ ] Business rules listed and cross-referenced to requirements.
- [ ] Assumptions explicit (Section 2.3). Any broken assumption invalidates the spec.
- [ ] Non-goals explicit: out-of-scope features (5.2) and edge cases (5.3) clearly stated.
- [ ] Changelog updated (Section 1.1). Version is `1.0.0` for new specs.
- [ ] **No HOW in spec.** Zero implementation choices — no framework names, library names, class names, ORM models, migration scripts, or deployment configs.
- [ ] **Human approval received.** Approver name, date, and version recorded in Section 1.
