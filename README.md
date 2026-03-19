# BI Agent — Monday.com Business Intelligence

AI-powered business intelligence agent that connects to your Monday.com boards and answers questions about your data using Claude.

Ask natural language questions like "How's our pipeline looking?" or "Revenue breakdown by sector" and get instant, data-backed answers from your live Monday.com data.

## Architecture

```
frontend/          → Next.js app with Vercel AI SDK chat UI
api/index.py       → FastAPI backend (Vercel Python serverless)
core/
  agent.py         → Claude-powered BI agent with tool-use loop
  data_engine.py   → In-memory query engine (filter, aggregate, search)
  monday_client.py → Monday.com GraphQL API client
  tool_generator.py→ Auto-generates Claude tools from board schemas
```

The backend fetches live data from Monday.com on every query, builds a schema-aware tool for each board, and lets Claude decide which queries to run. The frontend streams responses using the Vercel AI SDK Data Stream protocol.

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Monday.com API key
- Anthropic API key

### Backend

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local with your backend URL
```

## Environment Variables

| Variable | Description |
|---|---|
| `MONDAY_API_KEY` | Your Monday.com API token |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `MONDAY_BOARD_IDS` | Comma-separated board IDs (optional — discovers all boards if empty) |
| `CLAUDE_MODEL` | Claude model to use (default: `claude-sonnet-4-20250514`) |

Frontend:

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend URL (e.g. `https://your-backend.vercel.app`) |

## Local Development

Start the backend:

```bash
python3 api/index.py
# Runs on http://localhost:8000
```

Start the frontend:

```bash
cd frontend
npm run dev
# Runs on http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`.

## Deploy to Vercel

### Backend (from project root)

```bash
vercel link
vercel env add MONDAY_API_KEY
vercel env add ANTHROPIC_API_KEY
vercel env add MONDAY_BOARD_IDS
vercel --prod
```

### Frontend (from frontend/)

```bash
cd frontend
vercel link    # Create as a separate project
vercel env add NEXT_PUBLIC_API_URL   # Set to your backend URL
vercel --prod
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check — shows API key status |
| POST | `/api/chat` | JSON chat endpoint (non-streaming) |
| POST | `/api/stream` | Streaming chat endpoint (Vercel AI SDK protocol) |

## Features

- Live Monday.com data on every query — no stale cache
- Auto-discovers board schemas and generates query tools
- Supports filtering, aggregation, date ranges, full-text search
- Streaming responses with Vercel AI SDK
- Chat history persisted in localStorage
- Dark theme UI with sidebar navigation
