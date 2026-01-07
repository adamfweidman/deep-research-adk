# Deep Research Agent (ADK + Agent Engine)

This project implements an AI agent using the Google Agent Development Kit (ADK) that interfaces with Google's **Deep Research** capability (`deep-research-pro-preview-12-2025`).

It is designed to be deployed to **Vertex AI Agent Engine**.

## Features
*   **Deep Research Integration**: Wraps the Interactions API to perform long-running research tasks.
*   **Session Memory**: Uses ADK's `ToolContext` state to persist the `interaction_id`. This allows users to ask follow-up questions and refine the research within the same session.
*   **Agent Engine Ready**: Configured for deployment to Google Cloud's managed agent runtime.

## Prerequisites

1.  **Google Cloud Project**: You need a GCP project with billing enabled.
2.  **APIs Enabled**:
    *   Vertex AI API (`aiplatform.googleapis.com`)
    *   Generative Language API (for Deep Research)
3.  **ADK Installed**: `pip install "google-adk[a2a]"`
4.  **Google Cloud Storage Bucket**: A bucket is required for staging the deployment.

## Local Development

1.  **Create and Initialize Virtual Environment**:
    ```bash
    uv venv .venv
    source .venv/bin/activate
    uv pip install -r requirements.txt
    ```

2.  **Set Environment Variables**:
    Create a `.env` file or export your API key:
    ```bash
    export GOOGLE_API_KEY="your-gemini-api-key"
    ```

3.  **Run Locally (CLI)**:
    ```bash
    adk run .
    ```

## A2A Discovery & Serving

This agent is configured to automatically host an A2A Discovery Card (AgentCard).

1.  **Start the Server**:
    ```bash
    uvicorn agent:a2a_app --host localhost --port 8001
    ```

2.  **Access Agent Card**:
    The discovery card is available at:
    `http://localhost:8001/.well-known/agent-card.json`

## Deployment to Agent Engine

To deploy this agent to Google Cloud, use the `adk deploy` command.

1.  **Authenticate**:
    ```bash
    gcloud auth login
    gcloud auth application-default login
    ```

2.  **Deploy**:
    Replace the placeholders with your project details.

    ```bash
    # Set your variables
    PROJECT_ID="your-project-id"
    REGION="us-central1"
    BUCKET="gs://your-staging-bucket"

    # Run deployment
    adk deploy agent_engine \
      --project=$PROJECT_ID \
      --region=$REGION \
      --staging_bucket=$BUCKET \
      --display_name="Deep Research Agent" \
      .
    ```

3.  **Test Deployment**:
    Once deployed, the CLI will output a `RESOURCE_ID`. You can use the Google Cloud Console or the ADK CLI to query your deployed agent.

## Project Structure

*   `agent.py`: Contains the `root_agent` definition and the `deep_research` tool implementation.
*   `requirements.txt`: Python dependencies.
*   `deep_research_docs.md`: Reference documentation for the Interactions API.
*   `GEMINI.md`: Project memory and configuration notes.
