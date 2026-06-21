"""ModuleManifest instance for the linked_apps module.

CONTEXT.md D-06 defines `ModuleManifest`'s canonical shape (id, display_name,
version, kind, provides, requires, db_schema) as living in
`backend/src/host/manifest.py`, written by Plan 01. This plan has zero
dependency on Plan 01's host infrastructure (see 05-02-PLAN.md objective) and
may execute before or after it lands, so `ModuleManifest` is imported lazily
with a structurally-identical local fallback when the host package is not
yet present. Once Plan 01/03 lands and wires this module through the
ModuleLoader, this file's only required change is dropping the fallback
branch — the MANIFEST instance itself does not need to change.
"""

try:
    from src.host.manifest import ModuleManifest
except ModuleNotFoundError:
    from typing import Literal

    from pydantic import BaseModel

    class ModuleManifest(BaseModel):  # type: ignore[no-redef]
        id: str
        display_name: str
        version: str
        kind: Literal["feature", "support", "linked"]
        provides: list[type]
        requires: list[type]
        db_schema: str | None


MANIFEST = ModuleManifest(
    id="linked_apps",
    display_name="Linked Apps",
    version="1.0.0",
    kind="feature",
    provides=[],
    requires=[],
    db_schema=None,
)
