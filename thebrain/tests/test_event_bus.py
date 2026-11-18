import asyncio
from app.core.event_bus import publish, subscribe
from app.core.contracts import StageEvent

def test_event_bus_pub_sub():
    async def _test():
        trace_id = "test-bus-1"
        event = StageEvent(stage="test", status="ok", message="hello")
        
        async def read_one():
            gen = subscribe(trace_id)
            return await gen.__anext__()
            
        reader_task = asyncio.create_task(read_one())
        await asyncio.sleep(0.01) # let the subscriber register
        
        await publish(trace_id, event)
        received = await reader_task
        assert received.message == "hello"
        
    asyncio.run(_test())
