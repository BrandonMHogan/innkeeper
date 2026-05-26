# Spec: SPEC-[XX] — [Module/Feature Name]

> [!IMPORTANT]
> This specification is an **Executable Contract** and the **Single Source of Truth (SSOT)**.
> The spec defines **WHAT** the system does and **WHY**. It does not prescribe HOW it is implemented — that is governed by your project's AI skills / workflow guides and tech stack reference.
> **No application code may be written until this spec is Approved by a human, the DoR checklist is complete, and all interface contracts are pinned.**

---

## 1. Metadata & Lifecycle

| Field | Value |
| :--- | :--- |
| **Spec ID** | `SPEC-XX` *(sequential integer; matches filename `SPEC-XX_slug.md`)* |
| **Status** | Draft \| Approved \| In-Development \| Complete |
| **Version** | 1.0.0 |
| **Last Updated** | YYYY-MM-DD |
| **Approved By** | [Human Name] |
| **Approval Date** | YYYY-MM-DD |
| **Target Branch** | `main` \| `feature/...` |
| **Spec Author (SDD)** | [Agent / Human] |
| **Test Writer (TDAD Red)** | [Agent] |
| **Implementor (TDAD Green)** | [Agent] |
| **Verifier (TDAD Refactor)** | [Agent] |

### 1.1 Changelog
Amendments after **Approved** status require a version bump and human re-approval before implementation continues.

**Version guide:** `MAJOR` = breaking interface change · `MINOR` = new requirements, non-breaking · `PATCH` = clarifications only, no behavior change

| Version | Date | Author | Breaking | Summary of Changes |
| :--- | :--- | :--- | :--- | :--- |
| 1.0.0 | YYYY-MM-DD | [Name] | No | Initial draft |

---

## 2. Goal & Context

### 2.1 Problem Statement
Concise explanation of the problem, background context, and the business or technical value this module delivers. Answer: *Why does this need to exist?*

### 2.2 User Personas & Stories
List every actor who interacts with this feature. Each story must be testable — if "so that [Benefit]" is vague, rewrite it.

| Persona | User Story |
| :--- | :--- |
| End-User | As a [User], I want to [Action] so that [Benefit]. |
| Admin | As an [Admin], I want to [Action] so that [Benefit]. |
| Internal Service | As a [Service], I need to [Action] so that [Benefit]. |

### 2.3 Assumptions
What is taken as true. When an assumption breaks, the spec is invalid and must be revised before work continues.

*   **A1:** [e.g., The upstream service is running and healthy before this module executes.]
*   **A2:** [e.g., The caller is authenticated before accessing any operation in this module.]

### 2.4 Constraints
Non-functional boundaries the system must respect. These are WHAT the system is bound by — not HOW it achieves them.

*   **C1 — Performance:** [e.g., All list operations must respond within 500ms at p99 under normal load.]
*   **C2 — Security:** [e.g., No raw internal errors or stack traces may be exposed to external callers.]
*   **C3 — Compliance / Legal:** [e.g., User data must not be retained beyond 90 days.]
*   **C4 — Environment / Platform:** [e.g., The service requires elevated OS privileges to access raw network sockets.]
*   **C5 — Backwards Compatibility:** [e.g., Existing consumers of v1 endpoints must not be broken by this change.]

---

## 3. Business Rules & State Model

### 3.1 Business Rules
Domain invariants that apply across multiple requirements. These are immutable truths about the domain — not implementation choices, not UI rules. Cross-reference to relevant `REQ-XX-YY` IDs.

*   **BR-XX-01:** [e.g., A resource may only belong to one owner at a time. See REQ-XX-03.]
*   **BR-XX-02:** [e.g., Concurrent jobs for the same target are not permitted. See REQ-XX-07.]

### 3.2 State Transitions
*(Omit if this module has no stateful domain objects.)*

Define all valid states and the permitted transitions between them. This is the contract for what states exist and what triggers each transition — not how the state machine is implemented.

| From State | Event / Trigger | To State | Guard Condition |
| :--- | :--- | :--- | :--- |
| *(created)* | [creation event] | `[initial_state]` | [condition, or "none"] |
| `[initial_state]` | [event or action] | `[next_state]` | [condition that must be true, or "none"] |
| `[active_state]` | [event or action] | `[terminal_state]` | [condition] |

*Terminal states (no further transitions): `[state_a]`, `[state_b]`*
*Use `*(created)*` as the "From" row to represent object instantiation — the moment the entity first enters the state machine.*

---

## 4. Interface Contracts

> [!WARNING]
> This section defines the **external boundaries** of this module: the canonical data shapes and communication contracts all consumers depend on. These are pinned at approval. Changes require a version bump and human re-approval.
> Internal implementation details (storage layer, class structure, migration scripts, library choices) are **NOT** specified here — the Implementor derives those from these contracts.

### 4.1 Data Model
Define the canonical shape of data this module owns. Field names, types, nullability, allowed values, and relationships are contract-level decisions. Use your project's preferred type notation (TypeScript, JSON Schema, OpenAPI, Pydantic pseudocode, etc.).

```
ExampleEntity {
  id:        string (UUID, system-generated, immutable)
  name:      string (required, max 255 chars)
  status:    enum ["active" | "inactive"] (required)
  ownerId:   ref → OwnerEntity.id (required, immutable)   // many-to-one
  tags:      ref[] → TagEntity.id (optional)              // many-to-many
  createdAt: timestamp (ISO 8601, system-generated, immutable)
}
```

*For each relationship, state the cardinality (`one-to-one`, `many-to-one`, `many-to-many`), whether it is required or optional, and whether it is mutable after creation.*

### 4.2 External Service Dependencies
*(Omit if this module makes no calls to external third-party services.)*

For each external service this module calls, define the operations used, expected response shape, and failure behavior contract. This pins what the module relies on from the outside world.

*   **Service: [e.g., Payment Provider / Email API / Auth Service]**
    *   **Operations Used:** [e.g., `POST /charges`, `GET /customers/{id}`]
    *   **Auth Method:** [e.g., Bearer token in header]
    *   **Expected Success Response Shape:**
        ```
        { "id": string, "status": "succeeded" | "failed" }
        ```
    *   **Failure Behavior:** [e.g., Returns 4xx on bad input, 5xx on provider outage — see FC-XX-03.]
    *   **SLA / Timeout Expectation:** [e.g., Calls must complete within 3 seconds; treat timeout as provider failure.]

### 4.3 API / Communication Contracts

*   **Protocol:** [e.g., REST / GraphQL / gRPC / SSE / Message Queue]
*   **Base Path / Topic / Channel:** [e.g., `/api/v1/[module]`]

**Endpoints / Operations:**

*   `[METHOD] /path`
    *   **Auth Required:** Yes / No — [required role or token type]
    *   **Idempotent:** Yes / No *(most relevant for mutations — reads are always idempotent)*
    *   **Request Shape:**
        ```
        { "field": type, "field": type }
        ```
    *   **Success Response ([code]):**
        ```
        { "field": type, "field": type }
        ```
    *   **Error Responses:** `[code]` [reason] · `[code]` [reason]

*(For event-driven or streaming protocols, define: event name, payload shape, trigger condition, and delivery guarantee — at-most-once / at-least-once / exactly-once.)*

---

## 5. Dependencies & Non-Goals

### 5.1 Internal Spec Dependencies
List other specifications or internal modules this spec builds on. State why each dependency exists and link to the specific requirement.

*   [SPEC-XX — Module Name](../specs/SPEC-XX_slug.md#REQ-XX-YY) — *[Why this dependency exists.]*

### 5.2 Non-Goals — Features
What this spec will NOT implement. Prevents scope creep and over-engineering.

*   **NG-1:** [e.g., This spec does not implement pagination on any list operation.]
*   **NG-2:** [e.g., This spec does not handle multi-tenant data isolation.]

### 5.3 Non-Goals — Edge Cases
Edge cases that are related to in-scope behavior but are intentionally not handled. Caller behavior under these conditions is undefined unless stated.

*   **NE-1:** [e.g., Submitting a resource with a name exceeding 255 chars returns a 400; no truncation is attempted.]
*   **NE-2:** [e.g., Concurrent creation requests for the same `name` may result in a conflict error; deduplication is not guaranteed.]

---

## 6. Security & Permissions
Define who can do what. State all authorization rules, role boundaries, and system-level privileges required by this module.

| Actor | Permitted Actions | Restrictions |
| :--- | :--- | :--- |
| Authenticated User | [e.g., Read own resources, create resources, trigger jobs] | [e.g., Cannot modify or delete resources owned by others] |
| Admin | [e.g., Read, modify, and delete all resources] | [e.g., Cannot delete system-reserved entries] |
| Internal Service | [e.g., Read all resources via service token] | [e.g., Cannot create or mutate resources] |
| Unauthenticated | None | All operations reject unauthenticated callers with an auth error |

*   **System Privileges Required:** [e.g., Elevated OS-level access for raw socket operations — see Constraint C4. None if not applicable.]
*   **Data Exposure Rules:** [e.g., Internal error details and stack traces must not be returned to any external caller. Field `internalId` must be stripped from all API responses.]

---

## 7. UI / UX Specification
*(Optional — omit this section entirely if the module has no user-facing interface.)*

Define exact copy, component states, and interaction flows. Agents and engineers **must not** invent UI text, labels, or states not listed here. Every state must be accounted for — empty, loading, error, and success.

### 7.1 Component States

| Component | State | Displayed Copy / Behavior |
| :--- | :--- | :--- |
| [Component / View Name] | Loading | "[Exact loading text or indicator description]" |
| [Component / View Name] | Empty | "[Exact empty state message shown to user]" |
| [Component / View Name] | Error | "[Exact error message shown to user]" |
| [Component / View Name] | Success | "[Exact success state description]" |
| [Button / Control Name] | Idle | "[Label text]" |
| [Button / Control Name] | In Progress | "[Label text in active state]" (disabled) |
| [Button / Control Name] | Disabled | "[Label text]" (disabled, with tooltip: "[reason]") |

### 7.2 User Flows
Step-by-step: what the user sees and does for each primary interaction path.

**Flow 1 — [Flow Name]:**
1. User [action] → System shows [state / copy]
2. User [action] → System shows [state / copy]
3. *(On error):* System shows [error state / copy] with action: "[retry text / fallback]"

---

## 8. Behavior Scenarios
Concrete input/output examples that serve as ground truth for the Test Writer and human reviewer. **Every `REQ-XX-*` requirement and every `FC-XX-*` failure mode must have at least one scenario.** Use exact representative values, not placeholders. Scenarios must be self-contained — no assumed ambient state.

### Scenario 1 — [Happy Path Name]
*   **Given:** [Exact initial system state and all preconditions]
*   **When:** [Exact input or trigger event, with representative example values]
*   **Then:** [Exact expected output, state change, or response body — nothing vague]

### Scenario 2 — [Edge Case Name]
*   **Given:** [Exact initial state]
*   **When:** [Exact edge-case input]
*   **Then:** [Exact expected output]

### Scenario 3 — [Failure Path Name]
*   **Given:** [Exact initial state]
*   **When:** [Exact failure trigger — invalid input, downstream outage, etc.]
*   **Then:** [Exact error response returned to caller, log entry emitted, and system state after failure]

---

## 9. Observability & Monitoring
*(Optional — omit only for trivially simple modules with no meaningful failure modes. When in doubt, include it.)*

Define what must be externally observable when this module runs correctly or fails. These are WHAT the system must emit — not HOW the logging or metrics infrastructure is built.

### 9.1 Logs
Every significant log entry this module must produce. Agents must not emit log messages not listed here, and must not omit any listed here.

| Event | Level | Message Format | When Emitted |
| :--- | :--- | :--- | :--- |
| [e.g., Resource created] | INFO | `"[module] resource created: id={id} owner={ownerId}"` | On successful creation |
| [e.g., Validation rejected] | WARN | `"[module] invalid input: field={field} reason={reason}"` | On bad input |
| [e.g., Downstream timeout] | ERROR | `"[module] external service timeout: service={name} elapsed={ms}ms"` | On external service failure |
| [e.g., State transition] | INFO | `"[module] state changed: id={id} from={prev} to={next}"` | On every state transition |

### 9.2 Metrics & Observable Signals
Key signals that indicate healthy or degraded operation. These must be trackable from outside the module.

*   **M1:** [e.g., Count of successful resource creations per minute.]
*   **M2:** [e.g., Count of validation errors per operation per minute.]
*   **M3:** [e.g., External service call latency (p50, p99) per provider.]
*   **M4:** [e.g., Failure rate by failure case ID — alert threshold if `FC-XX-01` rate exceeds 1% over 5 min.]

---

## 10. Requirements Traceability Matrix (Acceptance Criteria)

> [!IMPORTANT]
> Every requirement must be **atomic** and **binary pass/fail**. No vague language ("fast", "clean", "good UX", "should work"). If a requirement cannot be expressed as GIVEN / WHEN / THEN, it belongs in Business Rules, Constraints, or Assumptions — not here.
>
> **Both functional (`REQ-XX-*`) and failure-mode (`FC-XX-*`) entries belong in this table.** Every row in the Failure Modes Matrix (Section 11) must have a corresponding `FC-XX-*` row here. The Test File & Suite column is filled in during the TDAD Red Phase — leave it blank at spec-approval time.

| ID | Priority | Title | GIVEN / WHEN / THEN | Test Type | Test File & Suite *(Red Phase)* | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`REQ-XX-01`** | P0 | [Success Path] | **Given** [precondition] **/ When** [trigger + input] **/ Then** [exact result] | Integration | | `[ ] RED / [ ] GREEN` |
| **`REQ-XX-02`** | P0 | [Auth Enforcement] | **Given** [unauthenticated caller] **/ When** [any operation attempted] **/ Then** [auth error returned, no data exposed] | Integration | | `[ ] RED / [ ] GREEN` |
| **`REQ-XX-03`** | P1 | [Input Validation] | **Given** [valid session] **/ When** [invalid input sent] **/ Then** [error returned with field details, no state persisted] | Unit | | `[ ] RED / [ ] GREEN` |
| **`FC-XX-01`** | P0 | [Failure: Data Store Unavailable] | **Given** [service running, data store down] **/ When** [any operation that requires data store] **/ Then** [error returned to caller, retry attempted, error logged at ERROR level] | Integration | | `[ ] RED / [ ] GREEN` |
| **`FC-XX-02`** | P1 | [Failure: External Service Timeout] | **Given** [valid request] **/ When** [external service exceeds timeout threshold] **/ Then** [timeout error returned, warning logged, no partial state persisted] | Integration | | `[ ] RED / [ ] GREEN` |

**Priority:** `P0` = blocking (must ship) · `P1` = high (should ship) · `P2` = nice-to-have (can defer)
**Test Types:** `Unit` = isolated logic, no I/O · `Integration` = service/data-layer/external boundaries · `E2E` = full user flow

---

## 11. Error Handling & Failure Modes Matrix
Detail system behavior under every abnormal condition. Every row here **must** have a corresponding `FC-XX-*` row in Section 10 and at least one Behavior Scenario in Section 8.

| ID | Failure Case | Trigger / Condition | System Response | Recovery Path | Response Code / Exception | Log Level & Message |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FC-XX-01** | Data store unavailable | Connection refused on any data store operation | Return error to caller; retry up to 3× with exponential backoff | Reconnects automatically on next request after backoff window elapses | `503` / `DataStoreConnectionError` | `ERROR: [module] data store connection failed: {err}` |
| **FC-XX-02** | External service timeout | External call exceeds SLA timeout | Return error to caller; no partial state persisted | No automatic retry — caller retries on next request | `504` / `ExternalServiceTimeoutError` | `ERROR: [module] external service timeout: service={name} elapsed={ms}ms` |
| **FC-XX-03** | Invalid input payload | Required field missing or wrong type | Return validation details to caller; no state persisted | No recovery — caller must correct input and retry | `400` / `ValidationError` | `WARN: [module] invalid input: field={field} reason={reason}` |
| **FC-XX-04** | Authorization failure | Operation attempted without required role | Reject operation; return auth error; log attempt | No recovery — caller must authenticate / obtain correct role | `401` / `403` / `AuthorizationError` | `WARN: [module] unauthorized access attempt: actor={id} operation={op}` |

---

## 12. Definition of Ready (DoR)

> [!NOTE]
> The canonical DoR checklist lives in `docs/ai-skills/references/dor.md`. That file is the single source of truth.
>
> **Architect agents:** Before presenting this spec for review, load `docs/ai-skills/references/dor.md`, run through every item against this draft, fix all failures, then copy the completed checklist below with items checked.
>
> **Human reviewers:** Every item must be checked before status moves to **Approved**. An unchecked item blocks approval.

*(Architect: replace this line by pasting the completed DoR checklist from `docs/ai-skills/references/dor.md` here, with all passed items marked `[x]`.)*

---

## 13. Spec Lifecycle Checklist

> [!NOTE]
> This checklist tracks spec-phase milestones only. Test-writing, implementation, and verification are governed entirely by your project's AI skills and workflow guides. Do not add implementation tasks here.

### Initial Approval Flow
- [ ] **S1:** All sections drafted. No `TBD` fields remain.
- [ ] **S2:** DoR checklist (Section 12) fully checked by Spec Author.
- [ ] **S3:** Human review completed. All feedback incorporated.
- [ ] **S4:** Status → **Approved**. Approver name and date recorded in Section 1.
- [ ] **S5:** Status → **In-Development** when implementation begins.
- [ ] **S6:** Status → **Complete** after all `REQ-XX-*` and `FC-XX-*` tests are GREEN and human has confirmed the feature behaves as described in the Behavior Scenarios (Section 8).

### Amendment Flow *(use when spec changes after Approved status)*
- [ ] **A1:** Change documented in Section 1.1 changelog with new version number and `Breaking: Yes/No`.
- [ ] **A2:** All impacted sections updated. Affected `REQ-XX-*` / `FC-XX-*` IDs revised or added.
- [ ] **A3:** DoR re-checked for all modified sections.
- [ ] **A4:** Human re-approval received. Approval date and version updated in Section 1.
- [ ] **A5:** In-flight tests updated to reflect the amended requirements before implementation resumes.
