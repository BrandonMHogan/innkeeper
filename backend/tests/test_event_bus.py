import asyncio

import pytest

from src.host.event_bus import EventBus


@pytest.mark.asyncio
async def test_publish_invokes_subscribed_handler():
    bus = EventBus()
    received = {}
    done = asyncio.Event()

    async def handler(payload):
        received.update(payload)
        done.set()

    bus.subscribe("new_device", handler)
    await bus.publish("new_device", {"foo": "bar"})
    await asyncio.wait_for(done.wait(), timeout=1)

    assert received == {"foo": "bar"}


@pytest.mark.asyncio
async def test_publish_with_zero_subscribers_is_noop():
    bus = EventBus()
    called = False

    async def handler(payload):
        nonlocal called
        called = True

    bus.subscribe("other_event", handler)
    # publish to an event_type nobody is subscribed to
    await bus.publish("new_device", {"foo": "bar"})
    await asyncio.sleep(0.05)

    assert called is False


@pytest.mark.asyncio
async def test_handler_exception_does_not_propagate_or_block_other_subscribers():
    bus = EventBus()
    second_called = asyncio.Event()

    async def failing_handler(payload):
        raise ValueError("boom")

    async def second_handler(payload):
        second_called.set()

    bus.subscribe("new_device", failing_handler)
    bus.subscribe("new_device", second_handler)

    # Must not raise even though failing_handler raises internally.
    await bus.publish("new_device", {"foo": "bar"})
    await asyncio.wait_for(second_called.wait(), timeout=1)

    assert second_called.is_set()
