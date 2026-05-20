"""In-process event hubs for dashboard SSE fan-out."""
from __future__ import annotations

import asyncio
from typing import Generic, TypeVar

T = TypeVar("T")


class HubSubscription(Generic[T]):
    def __init__(self, hub: "EventHub[T]", queue: asyncio.Queue[T]) -> None:
        self._hub = hub
        self._queue = queue

    async def events(self, timeout: float | None = None):
        while True:
            try:
                if timeout is not None:
                    item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                else:
                    item = await self._queue.get()
            except asyncio.TimeoutError:
                break
            except asyncio.CancelledError:
                break
            yield item

    def close(self) -> None:
        self._hub._unsubscribe(self._queue)


class EventHub(Generic[T]):
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[T]] = []

    def publish(self, item: T) -> None:
        for q in list(self._queues):
            try:
                q.put_nowait(item)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> HubSubscription[T]:
        q: asyncio.Queue[T] = asyncio.Queue(maxsize=256)
        self._queues.append(q)
        return HubSubscription(self, q)

    def _unsubscribe(self, queue: asyncio.Queue[T]) -> None:
        try:
            self._queues.remove(queue)
        except ValueError:
            pass
