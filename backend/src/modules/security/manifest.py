"""ModuleManifest instance for the security feature module (D-06).

db_schema="security" — Security owns its own Postgres schema for
port_scan_results/security_alerts/pending_scan_requests (D-11/D-14),
migrated via its own Alembic branch (migrations/0001_initial.py).
"""

from src.host.manifest import ModuleManifest
from src.modules.device_identity.interfaces import DeviceLookupInterface

MANIFEST = ModuleManifest(
    id="security",
    display_name="Security",
    version="1.0.0",
    kind="feature",
    provides=[],
    requires=[DeviceLookupInterface],
    db_schema="security",
)
