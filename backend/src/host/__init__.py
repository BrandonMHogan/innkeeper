"""Module-host infrastructure — not a module itself.

Provides the capability Protocols, ModuleManifest, ModuleRegistry,
ModuleLoader, EventBus, and require_module_enabled/is_module_enabled
dependency that every native module (DeviceIdentity, Devices, Traffic,
Security, Notifications) plugs into. See
docs/superpowers/specs/2026-06-21-module-platform-pivot-design.md for the
full design rationale.
"""
