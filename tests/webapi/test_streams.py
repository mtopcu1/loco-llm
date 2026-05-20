import asyncio

import pytest

from llm_cli.webapi.streams import EventHub


@pytest.mark.webapi
@pytest.mark.asyncio
async def test_event_hub_delivers_to_subscribers():
    hub = EventHub[dict]()

    received = []
    sub = hub.subscribe()

    async def consume():
        async for ev in sub.events(timeout=0.5):
            received.append(ev)
            if len(received) == 2:
                break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    hub.publish({"v": 1})
    hub.publish({"v": 2})
    await asyncio.wait_for(task, timeout=1.0)
    assert received == [{"v": 1}, {"v": 2}]


@pytest.mark.webapi
@pytest.mark.asyncio
async def test_event_hub_multiple_subscribers_each_get_all_events():
    hub = EventHub[int]()
    s1, s2 = hub.subscribe(), hub.subscribe()
    out1, out2 = [], []

    async def drain(sub, out):
        async for ev in sub.events(timeout=0.5):
            out.append(ev)
            if len(out) == 3:
                break

    t1 = asyncio.create_task(drain(s1, out1))
    t2 = asyncio.create_task(drain(s2, out2))
    await asyncio.sleep(0.05)
    for i in range(3):
        hub.publish(i)
    await asyncio.wait_for(asyncio.gather(t1, t2), timeout=1.0)
    assert out1 == [0, 1, 2]
    assert out2 == [0, 1, 2]
