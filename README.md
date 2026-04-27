<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/fe854d31-d35d-4249-b224-2411ddfe2724

## Run Locally

**Prerequisites:** Node.js

1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

## Backend entrypoint (important)

The full-stack dev server starts the Python backend via [backend/server.ts](backend/server.ts), which runs:

- `python -m app.api.server`

That means the canonical FastAPI backend is [app/api/server.py](app/api/server.py).

A legacy backend entrypoint previously lived under `backend/app/api/server.py`; it has been relocated to
[backend/deprecated/legacy_server.py](backend/deprecated/legacy_server.py) to avoid accidental development on the wrong process.

# GraphRAG
