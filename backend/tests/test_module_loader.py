import asyncio
from typing import Protocol, runtime_checkable

import pytest

from src.host.loader import ModuleLoader, build_load_order
from src.host.manifest import ModuleManifest


@runtime_checkable
class ProtocolX(Protocol):
    def x(self) -> None: ...


@runtime_checkable
class ProtocolY(Protocol):
    def y(self) -> None: ...


@runtime_checkable
class ProtocolZ(Protocol):
    def z(self) -> None: ...


def _manifest(id_, provides=None, requires=None):
    return ModuleManifest(
        id=id_,
        display_name=id_,
        version="1",
        kind="feature",
        provides=provides or [],
        requires=requires or [],
        db_schema=None,
    )


def test_build_load_order_respects_provides_requires_edges():
    manifests = [
        _manifest("a", provides=[ProtocolX]),
        _manifest("b", provides=[ProtocolY], requires=[ProtocolX]),
        _manifest("c", requires=[ProtocolY]),
    ]

    order = build_load_order(manifests)

    assert order.index("a") < order.index("b") < order.index("c")


def test_build_load_order_unsatisfied_requires_raises_runtime_error():
    manifests = [_manifest("a", requires=[ProtocolZ])]

    with pytest.raises(RuntimeError) as exc_info:
        build_load_order(manifests)

    message = str(exc_info.value)
    assert "ProtocolZ" in message
    assert "a" in message


def test_provides_conflict_fails_fast():
    manifests = [
        _manifest("a", provides=[ProtocolX]),
        _manifest("b", provides=[ProtocolX]),
    ]

    with pytest.raises(RuntimeError) as exc_info:
        build_load_order(manifests)

    message = str(exc_info.value)
    assert "a" in message
    assert "b" in message
    assert "ProtocolX" in message


class _UIPageModule:
    def get_ui_route(self) -> str:
        return "/modules/ui-page"


class _NoCapabilityModule:
    pass


def test_ui_page_registration():
    from src.host.protocols import HasAPIRoutes, HasUIPage

    ui_instance = _UIPageModule()
    none_instance = _NoCapabilityModule()

    assert isinstance(ui_instance, HasUIPage)
    assert not isinstance(none_instance, HasUIPage)
    assert not isinstance(none_instance, HasAPIRoutes)

    manifests = [_manifest("ui_mod")]
    loader = ModuleLoader()
    result = loader.load(manifests, {"ui_mod": lambda deps: ui_instance})

    assert ("ui_mod", "/modules/ui-page") in result.ui_routes


def test_loader_supports_empty_manifest_list():
    loader = ModuleLoader()
    result = loader.load([], {})

    assert result.instances == {}
    assert result.routers == []


class _CollectorModule:
    def __init__(self):
        self.ran = False

    async def run_collector(self, stop_event: asyncio.Event) -> None:
        self.ran = True
        await stop_event.wait()


@pytest.mark.asyncio
async def test_collector_lifecycle():
    instance = _CollectorModule()
    manifests = [_manifest("collector_mod")]
    loader = ModuleLoader()
    result = loader.load(manifests, {"collector_mod": lambda deps: instance})

    assert len(result.collector_tasks) == 1
    stop_event, task = result.collector_tasks[0]

    # Give the task a moment to actually start running.
    await asyncio.sleep(0.01)
    assert instance.ran is True

    stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


class _BadArityRouterModule:
    def get_router(self, extra_arg):  # wrong arity — Pitfall 2
        return None


def test_bad_arity_capability_is_caught_and_logged_not_raised():
    instance = _BadArityRouterModule()
    manifests = [_manifest("bad_mod")]
    loader = ModuleLoader()

    # Must not raise even though get_router() has the wrong arity.
    result = loader.load(manifests, {"bad_mod": lambda deps: instance})

    assert result.routers == []
