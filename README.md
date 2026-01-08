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
5.  **API Key**: Create a `.env` file in the root directory with `GEMINI_API_KEY=your_key_here`.

## Local Development

`uvicorn agent:a2a_app --host localhost --port 8000`

## Deployment to Agent Engine

To deploy with A2A endpoints exposed on Vertex AI:

1.  **Authenticate**:
    ```bash
    gcloud auth application-default login
    ```

2.  **Deploy**:
    Run the following command from the **parent directory** of the project:
    ```bash
    adk deploy agent_engine \
      --project=YOUR_PROJECT_ID \
      --region=us-central1 \
      --staging_bucket=gs://YOUR_STAGING_BUCKET \
      --display_name="Deep Research Agent" \
      deep-research-adk
    ```
## Project Structure

*   `agent.py`: Unified agent implementation (Standard ADK + A2A + Session Tools).
*   `requirements.txt`: Python dependencies.
*   `GEMINI.md`: Project memory and configuration notes.
