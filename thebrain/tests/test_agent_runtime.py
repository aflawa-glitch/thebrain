import pytest
import asyncio
from app.core.agent_runtime import AgentInstance
from app.core.contracts import RequestContext

def test_agent_spawn_mocked(monkeypatch):
    async def _test():
        from app.core import agent_runtime
        class FakeLLM:
            async def chat(self, messages, **kwargs):
                return "Fake Agent Result"
                
        monkeypatch.setattr(agent_runtime, "for_role", lambda role: FakeLLM())
        
        context = RequestContext(conversation_id="test-agent")
        agent = AgentInstance("tester", "Just return a string", context)
        result = await agent.run("Do this")
        assert result == "Fake Agent Result"
        
    asyncio.run(_test())
