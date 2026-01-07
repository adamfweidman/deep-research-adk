"""Deep Research ADK Agent - Simplified implementation supporting ADK CLI, A2A Server, and Agent Engine."""

import os
import logging
import warnings
from typing import Dict, Any, Optional

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("deep_research_agent")

# Suppress ADK experimental warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

from google import genai
from google.adk.agents import Agent
from google.adk.tools import ToolContext
from google.adk.models.google_llm import Gemini
from google.adk.a2a.utils.agent_to_a2a import to_a2a

MAX_POLL_SECONDS = 900  # 15 minutes


def _get_api_key() -> str:
    """Get API key from environment (loaded from .env or set directly)."""
    return os.environ.get("GEMINI_API_KEY")


def _extract_text(report) -> str:
    """Extract text content from a Deep Research interaction report."""
    # Try common output locations
    if hasattr(report, "output") and report.output:
        return str(report.output)
    if hasattr(report, "parts"):
        texts = [p.text for p in report.parts if hasattr(p, "text") and p.text]
        if texts:
            return "\n".join(texts)
    if hasattr(report, "result") and report.result:
        return str(report.result)
    if hasattr(report, "outputs") and report.outputs:
        texts = []
        for out in report.outputs:
            if hasattr(out, "text") and out.text:
                texts.append(out.text)
            elif isinstance(out, dict) and "text" in out:
                texts.append(out["text"])
        if texts:
            return "\n".join(texts)
    # Fallback: try model_dump
    if hasattr(report, "model_dump"):
        dump = report.model_dump()
        if "outputs" in dump and isinstance(dump["outputs"], list):
            texts = [o.get("text", "") for o in dump["outputs"] if isinstance(o, dict) and "text" in o]
            if texts:
                return "\n".join(texts)
        if "output" in dump:
            return str(dump["output"])
    return "No text content found in report."


async def deep_research(query: str, interaction_id: Optional[str] = None, tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Performs deep research on a topic using Google's Deep Research API.

    Args:
        query: The research question or topic to investigate.
        interaction_id: Optional ID to resume a previous research session.
        tool_context: ADK tool context for state management.

    Returns:
        Dict with status, report text, and interaction ID.
    """
    logger.info(f"[DEEP_RESEARCH] Starting research for query: {query[:100]}...")

    api_key = _get_api_key()
    if not api_key:
        logger.error("[DEEP_RESEARCH] No API key found")
        return {"status": "error", "message": "GEMINI_API_KEY environment variable not set."}

    logger.info("[DEEP_RESEARCH] API key loaded successfully")

    # Initialize session state
    if "research_sessions" not in tool_context.state:
        tool_context.state["research_sessions"] = {}

    sessions = tool_context.state["research_sessions"]

    # Note: interaction_id is a Google API ID, no local validation needed

    try:
        import time
        # Deep Research requires AI Studio endpoint (not Vertex AI)
        logger.info("[DEEP_RESEARCH] Creating genai client...")
        client = genai.Client(api_key=api_key, vertexai=False, http_options={"api_version": "v1beta"})

        if interaction_id:
            # Resume polling an existing interaction
            logger.info(f"[DEEP_RESEARCH] Resuming interaction {interaction_id}")
            interaction = client.interactions.get(id=interaction_id)
        else:
            # Create new background interaction (required for agent interactions)
            logger.info("[DEEP_RESEARCH] Creating interaction...")
            interaction = client.interactions.create(
                agent="deep-research-pro-preview-12-2025",
                input=query,
                tools=[{"type": "google_search"}],
                background=True,
            )
            logger.info(f"[DEEP_RESEARCH] Interaction created with ID: {interaction.id}, status: {interaction.status}")
            # Save to session state immediately
            tool_context.state["interaction_id"] = interaction.id
            sessions[interaction.id] = {"query": query}

        start = time.time()
        while interaction.status not in ("COMPLETED", "FAILED", "completed", "failed"):
            elapsed = time.time() - start
            if elapsed > MAX_POLL_SECONDS:
                logger.info(f"[DEEP_RESEARCH] Poll timeout after {elapsed:.0f}s, returning in_progress")
                return {
                    "status": "in_progress",
                    "message": f"Research is still in progress. Call deep_research again with interaction_id='{interaction.id}' to check for results.",
                    "current_interaction_id": interaction.id
                }
            time.sleep(5)
            interaction = client.interactions.get(id=interaction.id)
            logger.info(f"[DEEP_RESEARCH] Polling... status: {interaction.status} ({elapsed:.0f}s elapsed)")

        if interaction.status in ("FAILED", "failed"):
            return {"status": "error", "message": "Deep Research interaction failed."}

        logger.info(f"[DEEP_RESEARCH] Interaction completed")

        logger.info("[DEEP_RESEARCH] Extracting text from report...")
        report_text = _extract_text(interaction)
        logger.info(f"[DEEP_RESEARCH] Extracted {len(report_text)} characters")

        return {
            "status": "success",
            "report": report_text,
            "current_interaction_id": interaction.id
        }
    except Exception as e:
        logger.exception(f"[DEEP_RESEARCH] Exception occurred: {e}")
        return {"status": "error", "message": f"Deep Research failed: {str(e)}"}


def list_research_sessions(tool_context: ToolContext = None) -> Dict[str, Any]:
    """Returns a list of all active research sessions."""
    logger.info("[LIST_SESSIONS] Listing research sessions")
    sessions = tool_context.state.get("research_sessions", {})
    logger.info(f"[LIST_SESSIONS] Found {len(sessions)} sessions")
    return {
        "status": "success",
        "active_sessions": sessions
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


def sleep_test(seconds: int) -> Dict[str, Any]:
    """Sleeps for the specified number of seconds and returns a message. Used for testing Agent Engine timeouts.

    Args:
        seconds: Number of seconds to sleep.

    Returns:
        Dict with status and elapsed time.
    """
    import time
    logger.info(f"[SLEEP_TEST] Sleeping for {seconds} seconds...")
    start = time.time()
    time.sleep(seconds)
    elapsed = time.time() - start
    logger.info(f"[SLEEP_TEST] Woke up after {elapsed:.1f}s")
    return {"status": "success", "message": f"Slept for {elapsed:.1f} seconds. Hello!"}


# Initialize API key and model
logger.info("[INIT] Initializing Deep Research Agent...")
api_key = _get_api_key()
logger.info(f"[INIT] API key loaded: {'Yes' if api_key else 'No'}")
model = Gemini(model="gemini-2.5-flash")
logger.info("[INIT] Model initialized: gemini-2.5-flash")

# Root agent definition
root_agent = Agent(
    model=model,
    name="deep_research_assistant",
    description="An AI research assistant powered by Google's Deep Research capability.",
    instruction="""You are an expert research assistant powered by Google's Deep Research capability.

WORKFLOW:
1. Call 'deep_research' with the user's query. Only call this tool ONCE per turn.
2. If the result status is "success", present the full report to the user.
3. If the result status is "in_progress", respond with EXACTLY this format:
   "Research is still in progress. Please try again in a moment to get the results."
   Include the interaction_id in your response so it can be used to resume.
4. If the result status is "error", report the error to the user.

RESUMING RESEARCH:
- If the user's message contains an interaction_id or mentions resuming, call 'deep_research' with that interaction_id.
- Call 'list_research_sessions' to see existing sessions.
- Use 'clear_research_session' or 'clear_all_research_sessions' when asked to forget research.""",
    tools=[deep_research, list_research_sessions, clear_research_session, clear_all_research_sessions, sleep_test]
)


def get_a2a_app():
    """Factory function for creating A2A ASGI app. Use with: uvicorn agent:get_a2a_app --factory"""
    logger.info("[A2A] Creating A2A ASGI app...")
    app_url = os.environ.get("APP_URL")
    if app_url:
        from urllib.parse import urlparse
        parsed = urlparse(app_url)
        a2a_app = to_a2a(
            root_agent,
            host=parsed.hostname,
            port=parsed.port or (443 if parsed.scheme == "https" else 80),
            protocol=parsed.scheme,
        )
        logger.info(f"[A2A] A2A app created with URL: {app_url}")
    else:
        a2a_app = to_a2a(root_agent)
        logger.info("[A2A] A2A app created (localhost default)")
    return a2a_app
