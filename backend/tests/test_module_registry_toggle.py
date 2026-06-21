import pytest

from src.host.registry import ModuleRegistry
from typing import Protocol, runtime_checkable


@runtime_checkable
class SomeProtocol(Protocol):
    def do_thing(self) -> None: ...


class SomeImpl:
    def do_thing(self) -> None:
        pass


def test_register_then_resolve_returns_same_instance():
    registry = ModuleRegistry()
    instance = SomeImpl()

    registry.register(SomeProtocol, instance)

    assert registry.resolve(SomeProtocol) is instance


def test_register_same_protocol_twice_raises_runtime_error_naming_both():
    registry = ModuleRegistry()
    first = SomeImpl()
    second = SomeImpl()

    registry.register(SomeProtocol, first)

    with pytest.raises(RuntimeError) as exc_info:
        registry.register(SomeProtocol, second)

    message = str(exc_info.value)
    assert repr(first) in message
    assert repr(second) in message


def test_resolve_unregistered_protocol_raises_runtime_error_not_keyerror():
    registry = ModuleRegistry()

    with pytest.raises(RuntimeError) as exc_info:
        registry.resolve(SomeProtocol)

    assert "SomeProtocol" in str(exc_info.value)
    assert not isinstance(exc_info.value, KeyError)
