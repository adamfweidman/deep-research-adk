import os
import time
from typing import Dict, Any, Optional
from google.adk.agents import Agent
from google.adk.tools import FunctionTool, ToolContext
from google import genai
from google.adk.a2a.utils.agent_to_a2a import to_a2a

# Initialize the GenAI client
# Ensure GOOGLE_API_KEY is set in your environment or .env file
# For Agent Engine deployment, authentication is handled automatically via Google Cloud credentials
try:
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
except Exception as e:
    print(f"Warning: Client initialization failed (expected during build/deploy if env vars missing): {e}")

def deep_research(query: str, interaction_id: Optional[str] = None, tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Performs deep research. Supports multiple concurrent research threads.
    
    Args:
        query: The research topic or question.
        interaction_id: (Optional) The ID of a previous interaction to resume/continue. 
                        If provided, the agent continues that specific research thread.
                        If NOT provided, a NEW research thread is started.
        tool_context: Automatically injected ADK context.
        
    Returns:
        Status, report, and a list of active research sessions.
    """
    print(f"Request: {query} | Resuming ID: {interaction_id}")
    
    # Initialize session registry if it doesn't exist
    if "research_sessions" not in tool_context.state:
        tool_context.state["research_sessions"] = {}
    
    sessions = tool_context.state["research_sessions"]
    
    # Validate provided ID
    prev_id = None
    if interaction_id:
        if interaction_id in sessions:
            prev_id = interaction_id
            print(f"Resuming valid session: {prev_id} ({sessions[prev_id]})")
        else:
            return {"status": "error", "message": f"Interaction ID {interaction_id} not found in history."}
    else:
        print("Starting NEW research thread.")

    try:
        # Start or continue interaction
        interaction = client.interactions.create(
            agent="deep-research-pro-preview-12-2025",
            input=query,
            previous_interaction_id=prev_id,
            background=True
        )
        
        print(f"Interaction running (ID: {interaction.id}). Polling...")
        
        # Poll for completion
        while True:
            interaction = client.interactions.get(interaction.id)
            if interaction.status == "completed":
                break
            if interaction.status in ["failed", "cancelled"]:
                return {"status": "error", "message": f"Research failed: {interaction.status}"}
            time.sleep(5)
        
        # Save session metadata
        # We use the first 50 chars of the query as a topic label if it's new
        if not prev_id:
            sessions[interaction.id] = query[:50] + "..."
            tool_context.state["research_sessions"] = sessions # Persist update
        
        # Get report
        report_text = "No output."
        if interaction.outputs:
            last = interaction.outputs[-1]
            report_text = getattr(last, "text", str(last))
            
        return {
            "status": "success", 
            "report": report_text,
            "current_interaction_id": interaction.id,
            "active_sessions": sessions # Return list so LLM knows what's available
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


# Create the FunctionTool
research_tool = FunctionTool(func=deep_research)

# Define the Agent
root_agent = Agent(
    model="gemini-3-flash-preview",
    name="deep_research_assistant",
    description="An AI research assistant powered by Google's Deep Research capability with persistent multi-session memory.",
    instruction="""
    You are an expert research assistant powered by Google's Deep Research capability.
    
    CAPABILITIES:
    1. **Deep Research:** You can perform deep, multi-step research on new topics using the 'deep_research' tool.
    2. **Memory:** You can remember and continue specific research threads using the `interaction_id` from the tool's output.
    3. **Conversation:** You can chat normally, summarize findings, and answer questions based on reports you have already retrieved.
    
    GUIDELINES:
    - **WHEN TO USE TOOL:** 
      - If the user asks a complex question requiring *new* external information.
      - If the user explicitly asks to "research" or "find out" something.
      - If the user wants to *continue* a previous research thread (pass the correct `interaction_id`).
    
    - **WHEN TO ANSWER DIRECTLY (NO TOOL):**
      - If the user is just saying hello or making small talk.
      - If the user asks a question about the *current* conversation context or a report you just generated.
      - If the user asks for a summary, rewrite, or analysis of the information you already have.
    
    - **Managing Context:**
      - The 'deep_research' tool returns a list of 'active_sessions'. Use this to map topics to IDs.
      - To continue a topic, pass the matching `interaction_id`.
      - To start a new topic, pass NO `interaction_id`.
    """,
    tools=[research_tool]
)

# A2A Discovery Hoisting
# This automatically generates an AgentCard based on the root_agent's 
# name, description, and tools, making it discoverable via A2A.
a2a_app = to_a2a(root_agent)

