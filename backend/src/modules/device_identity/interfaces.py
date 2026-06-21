"""DeviceLookupInterface — the swappable support-interface Protocol every
other module (Devices, and later Traffic/Security in Plans 04/05) resolves
through the ModuleRegistry instead of importing device_identity's ORM
models directly (D-05/RESEARCH.md Pattern 6).

Contract (documented here since Plans 04/05 depend on it): lookup(identifier)
accepts a numeric Device.id (as a string), a MAC address, or an identity_key
string, and returns a DeviceInfo if a registered Device matches, or None if
no match is found. Numeric-string identifiers are tried against Device.id
first (Plan 04 extension — Traffic's routes are keyed by integer device_id
path params, not MAC/identity_key).
"None" (not a raised exception) is the "not found" signal — callers should
treat a None return as "no registered device for this identifier", which
mirrors the pre-retrofit routes' use of `scalar_one_or_none()` throughout
traffic.py/security.py/devices.py.

DeviceInfo.macs is the union of the device's current last_known_mac plus
every historical MAC from DeviceMacHistory — the same MAC-rotation-aware
union logic routes/traffic.py::_resolve_device_macs implemented inline.
Per RESEARCH.md Pattern 6's explicit instruction, that union logic lives
here (in the interface's implementation), not duplicated in every consumer.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class DeviceInfo:
    device_id: int | None
    name: str | None
    type: str | None
    macs: set[str]


@runtime_checkable
class DeviceLookupInterface(Protocol):
    async def lookup(self, identifier: str) -> DeviceInfo | None:
        """Resolve a MAC or identity_key to a DeviceInfo, or None if no
        registered Device matches."""
        ...
