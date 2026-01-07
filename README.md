# Deep Research ADK Agent

An [A2A](https://github.com/google/A2A) agent that gives any A2A-compatible client (like [Gemini CLI](https://github.com/google-gemini/gemini-cli)) access to Google's [Deep Research](https://blog.google/products/gemini/google-gemini-deep-research/) capability.

Built with the [Agent Development Kit (ADK)](https://github.com/google/adk-python), powered by the [Interactions API](https://ai.google.dev/gemini-api/docs/thinking#interact), and deployed to [Cloud Run](https://cloud.google.com/run). It's Google all the way down.

## Prerequisites

- [Google Cloud project](https://console.cloud.google.com/) with billing enabled
- [Gemini API key](https://aistudio.google.com/) for Deep Research
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) authenticated (`gcloud auth login`)
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) installed

## Quick Start

### 1. Deploy to Cloud Run

```bash
git clone https://github.com/adamfweidman/deep-research-adk.git
cd deep-research-adk

# Store your Gemini API key in Secret Manager
echo -n "your-api-key" | gcloud secrets create GEMINI_API_KEY \
  --data-file=- --project=YOUR_PROJECT

# Grant the default compute SA access to the secret
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --project=YOUR_PROJECT \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Deploy (authenticated — requires identity token to call)
gcloud run deploy deep-research-agent \
  --source . \
  --port 8080 \
  --region us-central1 \
  --project YOUR_PROJECT \
  --no-allow-unauthenticated \
  --timeout=1200 \
  --memory=1Gi \
  --update-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest

# Set APP_URL so the agent card has the correct public URL
URL=$(gcloud run services describe deep-research-agent \
  --region us-central1 --project YOUR_PROJECT \
  --format='value(status.url)')

gcloud run services update deep-research-agent \
  --region us-central1 --project YOUR_PROJECT \
  --update-env-vars="APP_URL=$URL"

# Grant yourself permission to invoke the service
gcloud run services add-iam-policy-binding deep-research-agent \
  --region us-central1 --project YOUR_PROJECT \
  --member="user:YOUR_EMAIL" \
  --role="roles/run.invoker"
```

### 2. Connect Gemini CLI

Create `~/.gemini/agents/deep-research.md`:

```yaml
---
kind: remote
name: deep-research
agent_card_url: https://YOUR_SERVICE_URL/.well-known/agent.json
auth:
  type: http
  scheme: Bearer
  token: "!gcloud auth print-identity-token"
---
```

### 3. Use it

Boot up Gemini CLI and ask it to run research for you:

```bash
gemini
> delegate to deep-research: research the history of espresso
```

Research typically takes 2-5 minutes. The full report is returned in one shot.

## Local Development

```bash
# Create .env with your API key
echo "GEMINI_API_KEY=your-api-key" > .env

pip install -r requirements.txt

uvicorn agent:get_a2a_app --factory --host 127.0.0.1 --port 8000
```

Verify: `curl http://127.0.0.1:8000/.well-known/agent.json`

## Architecture

```
Gemini CLI ──(A2A/HTTPS)──> Cloud Run ──(poll)──> Deep Research API
                               │
                          uvicorn + ADK
                          to_a2a(root_agent)
```

- Deep Research is a background job — the agent polls every 5s until the report is ready
- Cloud Run timeout is 20 min to accommodate research that typically takes 2-5 min
- No streaming — the full report is returned after research completes

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Gemini API key from [AI Studio](https://aistudio.google.com/) |
| `APP_URL` | Public URL for agent card (set automatically on Cloud Run) |
