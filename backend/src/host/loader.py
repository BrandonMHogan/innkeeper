"""ModuleLoader — topological sort (build_load_order) + constructor-injection
orchestration (scan/resolve/instantiate/wire) per D-08/D-09.

`build_load_order()` uses stdlib `graphlib.TopologicalSorter`/`CycleError`
(RESEARCH.md Pattern 4), per RESEARCH.md's explicit non-recommendation of
any third-party graph library, and not a hand-rolled Kahn's algorithm.
A circular module dependency or unsatisfied `requires` crashes startup
loudly (T-05-01), never silently works around it.

Design choice (Claude's Discretion per CONTEXT.md): a `ModuleLoader` class
is used (not a bare module-level function) so loader state (registry,
event_bus, instances) is held on a single object the caller (main.py, in a
later plan) can inspect after `load()` returns, rather than threading
several return values through free functions.

Per-capability wiring (T-05-03 / RESEARCH.md Pitfall 2): each of the four
capability checks is wrapped in its own try/except so a single
malformed/wrong-arity module capability is logged and skipped rather than
crashing the whole loader run for every other module.
"""

import asyncio
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter
from typing import Callable

from fastapi import APIRouter

from src.host.event_bus import EventBus
from src.host.manifest import ModuleManifest
from src.host.protocols import (
    HasAPIRoutes,
    HasCollector,
    HasEventSubscriptions,
    HasUIPage,
)
from src.host.registry import ModuleRegistry


def build_load_order(manifests: list[ModuleManifest]) -> list[str]:
    """Topologically sorts manifests by requires/provides edges. Returns
    module ids in an order where every module's requires are satisfied by a
    module earlier in the list.

    Raises RuntimeError (not CycleError) on a provides conflict, a requires
    with no matching provides, or a dependency cycle — always fail-fast at
    startup, never silently worked around (T-05-01/T-05-02).
    """
    provides_index: dict[type, str] = {}
    for m in manifests:
        for protocol_type in m.provides:
            if protocol_type in provides_index:
                raise RuntimeError(
                    f"provides conflict: {protocol_type} declared by both "
                    f"{provides_index[protocol_type]} and {m.id}"
                )
            provides_index[protocol_type] = m.id

    graph: dict[str, set[str]] = {m.id: set() for m in manifests}
    for m in manifests:
        for required_type in m.requires:
            provider_id = provides_index.get(required_type)
            if provider_id is None:
                raise RuntimeError(f"{m.id} requires {required_type}, no module provides it")
            graph[m.id].add(provider_id)

    try:
        return list(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        raise RuntimeError(f"Module dependency cycle detected: {exc}") from exc


@dataclass
class LoadResult:
    """Everything the caller (main.py, in a later plan) needs to finish
    wiring the live FastAPI app and manage shutdown."""

    instances: dict[str, object] = field(default_factory=dict)
    routers: list[tuple[str, APIRouter]] = field(default_factory=list)
    ui_routes: list[tuple[str, str]] = field(default_factory=list)
    collector_tasks: list[tuple[asyncio.Event, "asyncio.Task"]] = field(default_factory=list)


class ModuleLoader:
    """Orchestrates scan/resolve/instantiate/wire per D-08/D-09.

    `factory_by_id` maps module id -> a callable `create(deps: dict[type,
    object]) -> ModuleInstance` (D-08's constructor-injection factory
    signature). The loader resolves all of a manifest's `requires` from the
    registry *before* instantiating it, so a missing/conflicting dependency
    fails loudly at startup, never mid-request.
    """

    def __init__(self, registry: ModuleRegistry | None = None, event_bus: EventBus | None = None) -> None:
        self.registry = registry if registry is not None else ModuleRegistry()
        self.event_bus = event_bus if event_bus is not None else EventBus()

    def load(
        self,
        manifests: list[ModuleManifest],
        factory_by_id: dict[str, Callable[[dict[type, object]], object]],
    ) -> LoadResult:
        result = LoadResult()

        if not manifests:
            # Core app boots with zero modules enabled — empty manifest list
            # must not raise.
            return result

        manifest_by_id = {m.id: m for m in manifests}
        load_order = build_load_order(manifests)

        for module_id in load_order:
            manifest = manifest_by_id[module_id]
            deps = {req: self.registry.resolve(req) for req in manifest.requires}

            factory = factory_by_id[module_id]
            instance = factory(deps)
            result.instances[module_id] = instance

            for provided_type in manifest.provides:
                self.registry.register(provided_type, instance)

            self._wire_capabilities(module_id, instance, result)

        return result

    def _wire_capabilities(self, module_id: str, instance: object, result: LoadResult) -> None:
        if isinstance(instance, HasAPIRoutes):
            try:
                router = instance.get_router()
                result.routers.append((module_id, router))
            except Exception as exc:  # noqa: BLE001 — one bad module must not crash the loader
                print(f"[module_loader] {module_id} capability HasAPIRoutes failed: {exc}")

        if isinstance(instance, HasUIPage):
            try:
                ui_route = instance.get_ui_route()
                result.ui_routes.append((module_id, ui_route))
            except Exception as exc:  # noqa: BLE001
                print(f"[module_loader] {module_id} capability HasUIPage failed: {exc}")

        if isinstance(instance, HasEventSubscriptions):
            try:
                for event_type, handler in instance.get_subscriptions().items():
                    self.event_bus.subscribe(event_type, handler)
            except Exception as exc:  # noqa: BLE001
                print(f"[module_loader] {module_id} capability HasEventSubscriptions failed: {exc}")

        if isinstance(instance, HasCollector):
            try:
                stop_event = asyncio.Event()
                task = asyncio.create_task(instance.run_collector(stop_event))
                result.collector_tasks.append((stop_event, task))
            except Exception as exc:  # noqa: BLE001
                print(f"[module_loader] {module_id} capability HasCollector failed: {exc}")
