import asyncio
from app.core import task_registry

def test_register_and_pop():
    async def _test():
        trace_id = "test-trace-1"
        event = asyncio.Event()
        task = asyncio.create_task(asyncio.sleep(10))
        
        task_registry.register(trace_id, task, event)
        assert task_registry.get_task(trace_id) is task
        assert task_registry.get_cancel_event(trace_id) is event
        
        task_registry.pop(trace_id)
        assert task_registry.get_task(trace_id) is None
        assert task_registry.get_cancel_event(trace_id) is None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    asyncio.run(_test())

def test_cancel_unknown_trace_returns_false():
    assert task_registry.cancel("does-not-exist") is False

def test_cancel_active_trace():
    async def _test():
        trace_id = "test-trace-2"
        event = asyncio.Event()
        task = asyncio.create_task(asyncio.sleep(10))
        
        task_registry.register(trace_id, task, event)
        success = task_registry.cancel(trace_id)
        
        assert success is True
        assert event.is_set() is True
        assert task.cancelled() is True or task.cancelling() > 0
        
        task_registry.pop(trace_id)
        try:
            await task
        except asyncio.CancelledError:
            pass
    asyncio.run(_test())
