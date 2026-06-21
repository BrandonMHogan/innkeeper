"""EventBus — minimal fire-and-forget asyncio pub/sub (D-10).

Carried over unchanged from the superseded Phase 5 bolt-on-plugin research
(`_superseded-bolt-on-plugin-model/05-RESEARCH.md`); only the
module-loading/contract layer around it is new this phase. Publishing an
event_type with zero subscribers is a no-op that raises nothing. A
subscribed handler that raises does not propagate to the caller of
`publish()` and does not prevent other subscribers on the same event_type
from running (`_safe_call`'s broad except).
"""

import asyncio
from collections import defaultdict
from typing import Callable


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, payload: dict) -> None:
        for handler in self._subscribers.get(event_type, []):
            asyncio.create_task(self._safe_call(handler, payload))

    @staticmethod
    async def _safe_call(handler, payload):
        try:
            await handler(payload)
        except Exception as exc:  # noqa: BLE001 — one module must never crash the bus
            print(f"[event_bus] handler {handler} failed: {exc}")
