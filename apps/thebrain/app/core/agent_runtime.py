from __future__ import annotations
import asyncio
import uuid
from typing import Any
from app.core.contracts import RequestContext, CapabilityResult
from app.core.llm_factory import for_role
from app.core.event_bus import publish
from app.core.contracts import StageEvent, utc_now

class AgentInstance:
    def __init__(self, role: str, instruction: str, context: RequestContext):
        self.agent_id = str(uuid.uuid4())
        self.role = role
        self.instruction = instruction
        self.context = context
        
    async def run(self, task: str) -> str:
        """Executes the agent's task in an isolated loop and returns the result."""
        await publish(self.context.trace_id, StageEvent(
            stage="agent", status="started", message=f"Agent {self.role} spawned."
        ))
        
        llm = for_role("primary")
        messages = [
            {"role": "system", "content": f"You are a specialized {self.role} agent working under Julian. Follow these instructions strictly: {self.instruction}. Do not hallucinate. If you need a tool, ask Julian."},
            {"role": "user", "content": task}
        ]
        
        try:
            result = await llm.chat(messages, temperature=0.3, max_tokens=2000)
            await publish(self.context.trace_id, StageEvent(
                stage="agent", status="completed", message=f"Agent {self.role} finished."
            ))
            return result
        except Exception as e:
            await publish(self.context.trace_id, StageEvent(
                stage="agent", status="failed", message=f"Agent {self.role} crashed: {str(e)}"
            ))
            return f"Agent failed: {str(e)}"

async def spawn_agent(role: str, instruction: str, task: str, context: RequestContext) -> CapabilityResult:
    agent = AgentInstance(role, instruction, context)
    result = await agent.run(task)
    return CapabilityResult("spawn_agent", "completed", result)

