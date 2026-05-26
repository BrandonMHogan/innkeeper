# Code Standards Router

This is the entry point for all coding standards in this project. Before writing any file, use the lookup table to identify and load the relevant standards file(s).

This file is project-specific. The Implementor and Verifier skills are agnostic — they reference this router and this router points to what applies here.

---

## Standards File Lookup

| Language / Context | File Pattern | Standards File |
| :--- | :--- | :--- |
| Python — backend, services, scripts | `*.py`, `*.pyi` (excluding `test_*`) | `docs/standards/python.md` |
| Python — Alembic migrations | `alembic/versions/*.py` | `docs/standards/python.md` (see Alembic section) |
| Svelte components | `*.svelte` | `docs/standards/svelte5.md` |
| TypeScript / JavaScript — frontend | `*.ts`, `*.js` under `frontend/` | `docs/standards/svelte5.md` |
| Backend tests | `test_*.py`, `*_test.py` | `docs/standards/testing.md` |
| Frontend tests | `*.spec.ts`, `*.test.ts` | `docs/standards/testing.md` |

---

## How to Use

1. Identify every file type you will create or modify for the current requirement
2. Load the corresponding standards file(s) from the table above
3. Apply all standards in that file throughout your implementation
4. If a standard conflicts with a spec requirement, **the spec wins** — note the conflict explicitly and ask the human

**Note:** Library versions, tool choices, and quality gate commands live in `docs/architecture/tech-stack.md`, not here. Standards files cover HOW to write code; tech-stack covers WHAT to use.

---

## Adding Standards for a New Language or Platform

If this project adds a new language or platform:
1. Create `docs/standards/<language>.md` following the pattern of the existing files
2. Add a row to the lookup table above
3. Update the Implementor pre-flight to note the addition if needed
