import os
import time
from typing import Dict, Any, Optional
from google import genai
from google.adk.agents import Agent
from google.adk.tools import FunctionTool, ToolContext
from google.adk import Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, UnsupportedOperationError, AgentSkill
from a2a.utils import new_agent_text_message
from a2a.utils.errors import ServerError
from vertexai.preview.reasoning_engines import A2aAgent
from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card

# Initialize the GenAI client
try:
    # Use GEMINI_API_KEY if present, otherwise fallback to GOOGLE_API_KEY
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
except Exception as e:
    raise RuntimeError(f"Failed to initialize GenAI Client: {e}") from e

def deep_research(query: str, interaction_id: Optional[str] = None, tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Performs deep research. Supports multiple concurrent research threads.
    """
    if "research_sessions" not in tool_context.state:
        tool_context.state["research_sessions"] = {}
    
    sessions = tool_context.state["research_sessions"]
    
    prev_id = None
    if interaction_id:
        if interaction_id in sessions:
            prev_id = interaction_id
        else:
            return {"status": "error", "message": f"Interaction ID {interaction_id} not found in history."}

    try:
        interaction = client.interactions.create(
            agent="deep-research-pro-preview-12-2025",
            input=query,
            previous_interaction_id=prev_id,
            background=True
        )
        
        start_time = time.time()
        timeout = 600  # 10 minutes
        while True:
            if time.time() - start_time > timeout:
                return {"status": "error", "message": "Research timed out."}
            interaction = client.interactions.get(interaction.id)
            if interaction.status == "completed":
                break
            if interaction.status in ["failed", "cancelled"]:
                return {"status": "error", "message": f"Research failed: {interaction.status}"}
            time.sleep(5)
        
        if not prev_id:
            sessions[interaction.id] = query[:50] + "..."
            tool_context.state["research_sessions"] = sessions
        
        report_text = "No output."
        if interaction.outputs:
            last = interaction.outputs[-1]
            report_text = getattr(last, "text", str(last))
            
        return {
            "status": "success", 
            "report": report_text,
            "current_interaction_id": interaction.id,
            "active_sessions": sessions
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_research_sessions(tool_context: ToolContext = None) -> Dict[str, Any]:
    """Returns a list of all active research sessions."""
    return {
        "status": "success",
        "active_sessions": tool_context.state.get("research_sessions", {})
    }

def clear_research_session(interaction_id: str, tool_context: ToolContext = None) -> Dict[str, Any]:
    """Clears a specific research session by its interaction ID."""
    sessions = tool_context.state.get("research_sessions", {})
    if interaction_id in sessions:
        del sessions[interaction_id]
        tool_context.state["research_sessions"] = sessions
        return {"status": "success", "message": f"Session {interaction_id} cleared."}
    return {"status": "error", "message": f"Session {interaction_id} not found."}

def clear_all_research_sessions(tool_context: ToolContext = None) -> Dict[str, Any]:
    """Clears all active research sessions."""
    tool_context.state["research_sessions"] = {}
    return {"status": "success", "message": "All sessions cleared."}

# Define tools
research_tool = FunctionTool(func=deep_research)
list_sessions_tool = FunctionTool(func=list_research_sessions)
clear_session_tool = FunctionTool(func=clear_research_session)
clear_all_sessions_tool = FunctionTool(func=clear_all_research_sessions)
all_tools = [research_tool, list_sessions_tool, clear_session_tool, clear_all_sessions_tool]

# 1. Standard ADK Agent (for adk run / local testing)
root_agent = Agent(
    model="gemini-3-flash-preview",
    name="deep_research_assistant",
    description="An AI research assistant powered by Google's Deep Research capability.",
    instruction="""
    You are an expert research assistant powered by Google's Deep Research capability.
    
    HOW TO MANAGE RESEARCH THREADS:
    1. **Resuming:** Before starting research, you can call 'list_research_sessions' to see if a relevant thread exists.
    2. **Using IDs:** If you find a relevant session, pass its key (the interaction_id) to the 'deep_research' tool.
    3. **New Topics:** If no relevant session exists, call 'deep_research' WITHOUT an interaction_id.
    4. **Maintenance:** If a user says "forget that research" or "start over", use 'clear_research_session' or 'clear_all_research_sessions'.
    """,
    tools=all_tools
)

# 2. Local A2A Server (for uvicorn agent:a2a_app)
a2a_app = to_a2a(root_agent)

# 3. Agent Engine A2A Agent (for adk deploy)
class DeepResearchExecutor(AgentExecutor):
    def __init__(self):
        self.agent = root_agent
        self.runner = Runner(
            app_name=self.agent.name,
            agent=self.agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise ServerError(error=UnsupportedOperationError())

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        try:
            query = context.get_user_input()
            if not context.current_task: await updater.submit()
            await updater.start_work()

            from google.genai import types as genai_types
            content = genai_types.Content(role='user', parts=[genai_types.Part(text=query)])
            session_id = context.context_id or "default-session"
            
            # TODO: Implement user_id
            user_id = 'a2a-user'

            async for event in self.runner.run_async(session_id=session_id, user_id=user_id, new_message=content):
                if event.is_final_response():
                    text_parts = [TextPart(text=part.text) for part in event.content.parts if part.text]
                    await updater.add_artifact(text_parts, name='result')
                    await updater.complete()
                    break
                await updater.update_status(TaskState.working, message=new_agent_text_message('Researching...'))
        except Exception as e:
            await updater.update_status(TaskState.failed, message=new_agent_text_message(f"Error: {str(e)}"))
            raise e

agent_skill = AgentSkill(
    id='deep_research', name='Deep Research',
    description='Performs deep, multi-step research on any topic.',
    tags=['Research'], examples=['Research the current state of quantum computing'],
)
agent_card = create_agent_card(
    agent_name='Deep Research Assistant',
    description='An AI research assistant powered by Google\'s Deep Research capability.',
    skills=[agent_skill]
)
a2a_agent = A2aAgent(agent_card=agent_card, agent_executor_builder=DeepResearchExecutor)
