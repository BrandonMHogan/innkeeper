"""ModuleManifest instance for the device_identity support module (D-06)."""

from src.host.manifest import ModuleManifest
from src.modules.device_identity.interfaces import DeviceLookupInterface

MANIFEST = ModuleManifest(
    id="device_identity",
    display_name="Device Identity",
    version="1.0.0",
    kind="support",
    provides=[DeviceLookupInterface],
    requires=[],
    db_schema="device_identity",
)
