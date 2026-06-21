"""SecurityModule — constructor-injection factory satisfying HasAPIRoutes,
requires=[DeviceLookupInterface] (D-08).

On construction, wires the resolved DeviceLookupInterface instance into
routes.py's module-level accessor (set_device_lookup) so every route handler
in that file calls through the exact instance the ModuleLoader resolved from
the registry — not a second, independently constructed one (mirrors
TrafficModule's set_device_lookup()/get_device_lookup() pattern from
Plan 04).
"""

from fastapi import APIRouter

from src.modules.device_identity.interfaces import DeviceLookupInterface
from src.modules.security import routes


class SecurityModule:
    def __init__(self, device_lookup: DeviceLookupInterface) -> None:
        self.device_lookup = device_lookup
        routes.set_device_lookup(device_lookup)

    def get_router(self) -> APIRouter:
        return routes.router


def create(deps: dict[type, object]) -> SecurityModule:
    """Constructor-injection factory (D-08) — requires=[DeviceLookupInterface]
    resolved by the ModuleLoader before this factory is called."""
    return SecurityModule(deps[DeviceLookupInterface])
