"""In-process event hubs for dashboard SSE fan-out."""
from __future__ import annotations

import asyncio
from typing import Generic, TypeVar

T = TypeVar("T")


class HubSubscription(Generic[T]):
    def __init__(
        self,
        hub: "EventHub[T]",
        queue: asyncio.Queue[T],
        loop: asyncio.AbstractEventLoop | None,
    ) -> None:
        self._hub = hub
        self._queue = queue
        self._loop = loop

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

    def deliver(self, item: T) -> None:
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._put_nowait, item)
            return
        self._put_nowait(item)

    def _put_nowait(self, item: T) -> None:
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            pass

    def close(self) -> None:
        self._hub._unsubscribe(self)


class EventHub(Generic[T]):
    def __init__(self) -> None:
        self._subscriptions: list[HubSubscription[T]] = []

    def publish(self, item: T) -> None:
        for sub in list(self._subscriptions):
            sub.deliver(item)

    def subscribe(self) -> HubSubscription[T]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        q: asyncio.Queue[T] = asyncio.Queue(maxsize=256)
        sub = HubSubscription(self, q, loop)
        self._subscriptions.append(sub)
        return sub

    def _unsubscribe(self, sub: HubSubscription[T]) -> None:
        try:
            self._subscriptions.remove(sub)
        except ValueError:
            pass
