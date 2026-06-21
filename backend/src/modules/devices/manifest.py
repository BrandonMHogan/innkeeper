"""ModuleManifest instance for the devices feature module (D-06).

db_schema=None — D-16: Devices' own schema is only for UI-owned concerns
(sort order/search history), none of which are in this phase's scope per
CONTEXT.md's Claude's Discretion note. Leave db_schema=None until a real
UI-owned field is needed.
"""

from src.host.manifest import ModuleManifest
from src.modules.device_identity.interfaces import DeviceLookupInterface

MANIFEST = ModuleManifest(
    id="devices",
    display_name="Devices",
    version="1.0.0",
    kind="feature",
    provides=[],
    requires=[DeviceLookupInterface],
    db_schema=None,
)
