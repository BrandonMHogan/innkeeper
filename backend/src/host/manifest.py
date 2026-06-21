"""ModuleManifest — typed declaration of what a module is, what it
provides, and what it requires (D-06).

Note (RESEARCH.md Pattern 2 Gotcha): Pydantic v2 validates `list[type]`
permissively — any `type` object passes, so a manifest declaring
`provides=[str]` would be schema-valid but semantically wrong. The real
safety net is the loader's fail-fast check (matching `requires` against
`provides` across all manifests in `host/loader.py`), not Pydantic's field
validation.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ModuleManifest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    display_name: str
    version: str
    kind: Literal["feature", "support"]
    provides: list[type]
    requires: list[type]
    db_schema: str | None
