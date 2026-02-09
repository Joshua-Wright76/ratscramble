from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def publish(self, event: dict[str, Any]) -> None:
        await self._queue.put(event)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            yield await self._queue.get()
