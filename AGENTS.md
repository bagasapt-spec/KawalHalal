# AGENTS.md

## Google Cloud
- Project: <GCP_PROJECT_ID>
- Region: asia-southeast2, model location: global
- Allowed: Agent Platform, Cloud Run, BigQuery

## Building the agent
- Use the Agents CLI skills to scaffold, eval and deploy
- ADK 2.0 in Python, packages managed with uv or pip
- Main model: gemini-2.0-flash
- Light steps: gemini-2.0-flash-lite

## Infrastructure
- Keep it minimal: nothing the demo does not need
- Deploy to Cloud Run, min-instances 0
- No VMs, GKE, Cloud SQL or GPUs
- Authentication: Support ADC and API key fallback for local testing