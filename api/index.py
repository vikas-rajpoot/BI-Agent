"""
FastAPI application.
Works both as a Vercel serverless function and as a local dev server.
"""

import os
import sys
import traceback
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load .env when running locally (no-op on Vercel)
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from core.agent import BIAgent, BIAgentStreaming

app = FastAPI(title="BI Agent", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── CORS preflight handler ──────────────────────────────────────────
# Explicit OPTIONS handler to ensure Vercel doesn't swallow preflight requests

@app.options("/api/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )


# ── request / response models ───────────────────────────────────────


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[ChatMessage] = []


class AIChatMessage(BaseModel):
    role: str
    content: str


class AIChatRequest(BaseModel):
    messages: list[AIChatMessage]


# ── health check ─────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    monday_ok = bool(os.environ.get("MONDAY_API_KEY"))
    anthropic_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {
        "status": "ok" if (monday_ok and anthropic_ok) else "misconfigured",
        "monday_api_key": "set" if monday_ok else "missing",
        "anthropic_api_key": "set" if anthropic_ok else "missing",
    }


# ── chat endpoint ────────────────────────────────────────────────────


@app.post("/api/chat")
async def chat(req: ChatRequest):
    monday_key = os.environ.get("MONDAY_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not monday_key or not anthropic_key:
        return JSONResponse(
            status_code=500,
            content={
                "response": "Server misconfigured — missing API keys.",
                "traces": [],
            },
        )

    board_ids_raw = os.environ.get("MONDAY_BOARD_IDS", "")
    board_ids = [b.strip() for b in board_ids_raw.split(",") if b.strip()] or None

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    agent = BIAgent(
        monday_api_key=monday_key,
        anthropic_api_key=anthropic_key,
        board_ids=board_ids,
        model=model,
    )

    # Build messages list: history + current message
    messages: list[dict] = []
    for msg in req.conversation_history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.message})

    try:
        result = await agent.chat(messages)
        return JSONResponse(content=result)
    except Exception:
        tb = traceback.format_exc()
        return JSONResponse(
            status_code=500,
            content={
                "response": f"Something went wrong. Please try again.",
                "traces": [{"type": "error", "action": "Server error", "detail": tb}],
            },
        )


# ── streaming chat endpoint (Vercel AI SDK compatible) ───────────────


@app.post("/api/stream")
async def stream_chat(req: AIChatRequest):
    monday_key = os.environ.get("MONDAY_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not monday_key or not anthropic_key:
        return JSONResponse(
            status_code=500,
            content={"error": "Server misconfigured — missing API keys."},
        )

    board_ids_raw = os.environ.get("MONDAY_BOARD_IDS", "")
    board_ids = [b.strip() for b in board_ids_raw.split(",") if b.strip()] or None
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    agent = BIAgentStreaming(
        monday_api_key=monday_key,
        anthropic_api_key=anthropic_key,
        board_ids=board_ids,
        model=model,
    )

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    return StreamingResponse(
        agent.chat_stream(messages),
        media_type="text/plain; charset=utf-8",
        headers={
            "X-Vercel-AI-Data-Stream": "v1",
            "Cache-Control": "no-cache",
        },
    )


# ── serve frontend (local dev & fallback) ────────────────────────────


@app.get("/")
async def root():
    index_path = PROJECT_ROOT / "public" / "index.html"
    return HTMLResponse(index_path.read_text())


# ── local dev entrypoint ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print("Starting BI Agent locally → http://localhost:8000")
    uvicorn.run(
        "api.index:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(PROJECT_ROOT)],
    )
