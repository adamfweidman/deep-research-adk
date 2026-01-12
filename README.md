# Deep Research Agent (ADK + Agent Engine)

This project implements an AI agent using the Google Agent Development Kit (ADK) that interfaces with Google's **Deep Research** capability (`deep-research-pro-preview-12-2025`).

It is designed to be deployed to **Vertex AI Agent Engine** and exposed via the **Agent2Agent (A2A)** protocol.

## Features
*   **Deep Research Integration**: Wraps the Interactions API to perform long-running research tasks.
*   **Session Memory**: Uses ADK's `ToolContext` state to persist `interaction_id`s across turns.
*   **Memory Management**: Built-in tools to list, clear individual, or wipe all research sessions.
*   **A2A Ready**: Native support for the Agent2Agent protocol for multi-agent collaboration.

## Prerequisites

1.  **Google Cloud Project**: You need a GCP project (e.g., `adamfweidman-test`) with billing enabled.
2.  **APIs Enabled**:
    *   Vertex AI API (`aiplatform.googleapis.com`)
    *   Generative Language API (for Deep Research)
3.  **ADK Installed**: `pip install "google-adk[a2a]"`
4.  **Google Cloud Storage Bucket**: Required for staging (e.g., `gs://adamfweidman-test-adk-staging-a2a`).

## How to Run & Test

There are four ways to interact with this agent, depending on your needs:

### 1. CLI Mode (Standard ADK)
Quick terminal-based interaction.
```bash
adk run .
```

### 2. Web Mode (Graphical Debugger)
The ADK Web UI. **Note:** Since `adk web` scans for subdirectories, run this from the project root pointing to the parent folder.
```bash
adk web ..
```

### 3. Local A2A Server (API Mode)
Start a local A2A-compliant server (default port 8000). Useful for testing multi-agent delegation. Use `DEBUG=1` to see session IDs and research status.
```bash
# Enable verbose logging
export DEBUG=1
uv run uvicorn agent:a2a_app --host localhost --port 8000
```
*   **Agent Card:** `http://localhost:8000/.well-known/agent-card.json`

### 4. Remote Deployment (Agent Engine)
Deploy to Google Cloud Vertex AI Agent Engine. **Note:** Run this from the **parent directory** of the project.
```bash
# From the parent directory (e.g., ~/Desktop/a2a/)
adk deploy agent_engine \
  --project="YOUR_PROJECT_ID" \
  --region="us-central1" \
  --staging_bucket="gs://YOUR_BUCKET_NAME" \
  --display_name="Deep Research Agent A2A" \
  --adk_app_object app \
  deep_research_adk
```

## Session Management Tools
You can now manage your research history using natural language:
*   **"List my research sessions"**: Displays all active thread IDs and topics.
*   **"Clear research session [ID]"**: Removes a specific research thread from memory.
*   **"Clear all research sessions"**: Wipes the entire session history.

## How Memory Works
This agent uses **Persistent State**:
1.  **Registry**: Every time a research task starts, its `interaction_id` is saved in `tool_context.state`.
2.  **Mapping**: The registry maps these IDs to a short summary of the query.
3.  **Persistence**: 
    *   **Locally**: State is kept in memory (reset on restart unless saved).
    *   **On Agent Engine**: State is automatically persisted to a managed backend, meaning your research history survives across different user sessions and agent restarts.

## Deployment to Agent Engine

To deploy with A2A endpoints exposed on Vertex AI:

1.  **Authenticate**:
    ```bash
    gcloud auth application-default login
    ```

2.  **Clean Deployment**:
    Deploy using the `A2aAgent` class to ensure protocol compatibility:
    ```bash
    # Prepare a clean directory (excluding .venv)
    mkdir -p ../deploy_tmp
    cp agent.py requirements.txt ../deploy_tmp/
    
    # Deploy
    adk deploy agent_engine \
      --project=adamfweidman-test \
      --region=us-central1 \
      --staging_bucket=gs://adamfweidman-test-adk-staging-a2a \
      --display_name="Deep Research Agent A2A" \
      ../deploy_tmp
    ```

## Project Structure

*   `agent.py`: Unified agent implementation (Standard ADK + A2A + Session Tools).
*   `requirements.txt`: Python dependencies.
*   `GEMINI.md`: Project memory and configuration notes.