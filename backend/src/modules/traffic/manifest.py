"""ModuleManifest instance for the traffic feature module (D-06).

db_schema="traffic" — Traffic owns its own Postgres schema for
traffic_flows/bandwidth_metrics (D-11/D-14), migrated via its own Alembic
branch (migrations/0001_initial.py).
"""

from src.host.manifest import ModuleManifest
from src.modules.device_identity.interfaces import DeviceLookupInterface

MANIFEST = ModuleManifest(
    id="traffic",
    display_name="Traffic",
    version="1.0.0",
    kind="feature",
    provides=[],
    requires=[DeviceLookupInterface],
    db_schema="traffic",
)
