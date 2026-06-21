"""LinkedModuleManifest — pure data shape for a linked (third-party) module.

Per CONTEXT.md D-23, a linked module is a manifest entry only (no code): it
produces a dashboard card that opens the third-party app's own UI. This class
intentionally carries zero behavior beyond field declarations.
"""

from pydantic import BaseModel


class LinkedModuleManifest(BaseModel):
    id: str
    name: str
    icon_url: str
    target_url: str
