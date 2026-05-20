"""In-process event hubs + SSE helpers."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Generic, TypeVar

T = TypeVar("T")


class _Subscription(Generic[T]):
    def __init__(self) -> None:
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=1024)
        self._closed = False

    async def events(self, *, timeout: float | None = None) -> AsyncIterator[T]:
        while not self._closed:
            try:
                if timeout is None:
                    item = await self._queue.get()
                else:
                    item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                return
            yield item

    def close(self) -> None:
        self._closed = True

    def _publish(self, item: T) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            # Drop oldest to keep up.
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(item)
            except asyncio.QueueFull:
                pass


class EventHub(Generic[T]):
    def __init__(self) -> None:
        self._subs: list[_Subscription[T]] = []

    def subscribe(self) -> _Subscription[T]:
        s = _Subscription[T]()
        self._subs.append(s)
        return s

    def publish(self, item: T) -> None:
        for s in self._subs:
            s._publish(item)

    def unsubscribe(self, sub: _Subscription[T]) -> None:
        sub.close()
        if sub in self._subs:
            self._subs.remove(sub)
