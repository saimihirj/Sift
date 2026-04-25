"""Runtime client heartbeat tracking for local auto-stop mode."""

from __future__ import annotations

import asyncio
import os
import signal
import time


ACTIVE_CLIENTS: dict[str, float] = {}
HAS_SEEN_BROWSER = False


def register_heartbeat(client_id: str) -> None:
    global HAS_SEEN_BROWSER
    ACTIVE_CLIENTS[client_id] = time.monotonic()
    HAS_SEEN_BROWSER = True


def prune_stale_clients(window_seconds: float = 20.0) -> None:
    now = time.monotonic()
    stale = [
        client_id
        for client_id, last_seen in ACTIVE_CLIENTS.items()
        if now - last_seen > window_seconds
    ]
    for client_id in stale:
        ACTIVE_CLIENTS.pop(client_id, None)


async def auto_stop_monitor() -> None:
    auto_stop_seconds = float(os.environ.get("SIFT_AUTO_STOP_SECONDS", "0") or "0")
    if auto_stop_seconds <= 0:
        return

    while True:
        await asyncio.sleep(5)
        prune_stale_clients(window_seconds=auto_stop_seconds)
        if HAS_SEEN_BROWSER and not ACTIVE_CLIENTS:
            os.kill(os.getpid(), signal.SIGINT)
