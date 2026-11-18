import asyncio
from typing import AsyncIterator, Dict, Set
from app.core.contracts import StageEvent

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, trace_id: str, event: StageEvent):
        async with self._lock:
            queues = self._subscribers.get(trace_id, set())
            for q in queues:
                await q.put(event)

    async def subscribe(self, trace_id: str) -> AsyncIterator[StageEvent]:
        q = asyncio.Queue()
        async with self._lock:
            if trace_id not in self._subscribers:
                self._subscribers[trace_id] = set()
            self._subscribers[trace_id].add(q)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            async with self._lock:
                if trace_id in self._subscribers:
                    self._subscribers[trace_id].discard(q)
                    if not self._subscribers[trace_id]:
                        del self._subscribers[trace_id]

bus = EventBus()

def publish(trace_id: str, event: StageEvent):
    return bus.publish(trace_id, event)

def subscribe(trace_id: str):
    return bus.subscribe(trace_id)
