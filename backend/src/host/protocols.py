"""Capability Protocols — composition, not a fat base class (D-02/D-03).

Each Protocol is small and independent; a module is any Python object that
structurally satisfies zero or more of these — no inheritance required.
Every Protocol is decorated `@runtime_checkable` so the loader can detect
which capabilities a module instance actually has via `isinstance()`, and
only wire up those (D-03).

Versioning rule (D-04): if a capability Protocol's shape must change
incompatibly later, define a new version (e.g. `HasAPIRoutesV2`) rather than
mutating the original; the loader checks the newer version first and falls
back. Existing modules are never forced to migrate on someone else's
schedule.

Known limitation (RESEARCH.md Pitfall 2): `isinstance()` against a
`@runtime_checkable` Protocol only verifies that members *exist*, not that
their signatures match (PEP 544). A module implementing `get_router(self,
x) -> None` would still pass `isinstance(instance, HasAPIRoutes)` and then
raise at call time. The loader wraps every capability-wiring call in its
own try/except to defend against this (see host/loader.py).
"""

import asyncio
from typing import Callable, Protocol, runtime_checkable

from fastapi import APIRouter


@runtime_checkable
class HasAPIRoutes(Protocol):
    def get_router(self) -> APIRouter: ...


@runtime_checkable
class HasUIPage(Protocol):
    def get_ui_route(self) -> str: ...


@runtime_checkable
class HasEventSubscriptions(Protocol):
    def get_subscriptions(self) -> dict[str, Callable]: ...


@runtime_checkable
class HasCollector(Protocol):
    async def run_collector(self, stop_event: asyncio.Event) -> None: ...
