"""Module-level EventBus singleton shared by device_identity's service.py
(publisher, called from capture.py's hot ingest path) and module.py's
DeviceIdentityModule factory (subscriber-wiring point for the ModuleLoader).

Claude's Discretion (Plan 03 Task 1's action block): record_observation()
is called directly from src/routes/capture.py, outside the ModuleLoader's
constructor-injection graph — capture.py is not itself a module in this
phase's scope. A bare module-level singleton, instantiated once at import
time, lets capture.py's hot path and the ModuleLoader-instantiated
DeviceIdentityModule share the same EventBus instance without either one
constructing its own (which would silently fragment publish/subscribe
into two disconnected buses).
"""

from src.host.event_bus import EventBus

event_bus = EventBus()
