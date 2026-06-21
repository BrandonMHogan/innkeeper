"""DevicesModule — constructor-injection factory satisfying HasAPIRoutes,
requires=[DeviceLookupInterface] (D-08).

On construction, wires the resolved DeviceIdentityModule instance into
routes.py's module-level accessor (set_device_identity) so every route
handler in that file calls through the exact instance the ModuleLoader
resolved from the registry — not a second, independently constructed one.
"""

from fastapi import APIRouter

from src.modules.device_identity.interfaces import DeviceLookupInterface
from src.modules.devices import routes


class DevicesModule:
    def __init__(self, device_identity: DeviceLookupInterface) -> None:
        self.device_identity = device_identity
        routes.set_device_identity(device_identity)

    def get_router(self) -> APIRouter:
        return routes.router


def create(deps: dict[type, object]) -> DevicesModule:
    """Constructor-injection factory (D-08) — requires=[DeviceLookupInterface]
    resolved by the ModuleLoader before this factory is called."""
    return DevicesModule(deps[DeviceLookupInterface])
