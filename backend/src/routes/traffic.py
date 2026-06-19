"""GET /api/traffic/* — SSE live feed (TRAF-01) and historical bandwidth/
destinations query routes (TRAF-02..04). Every route is gated behind the
existing session-cookie auth (Depends(require_auth)) per ASVS V4/V12 — no
new auth surface is introduced (T-03-09: accepted, single-user/household
threat model).
"""

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from src.auth import require_auth
from src.services.traffic_broadcaster import get_latest_snapshot

router = APIRouter()


@router.get("/stream")
async def traffic_stream(request: Request, _: None = Depends(require_auth)):
    """D-13: single global SSE channel — polls the shared in-memory
    snapshot (updated by traffic_broadcaster.update_snapshot_loop) every 1s,
    yielding a new event only when the snapshot has changed since the last
    tick sent to this client."""

    async def event_generator():
        last_sent = None
        while True:
            if await request.is_disconnected():
                break
            snapshot = get_latest_snapshot()
            if snapshot != last_sent:
                yield {"event": "snapshot", "data": json.dumps(snapshot)}
                last_sent = dict(snapshot)
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator(), ping=15)
