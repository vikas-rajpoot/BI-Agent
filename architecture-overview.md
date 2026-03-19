User (Browser)
     │
     │  useChat() — Vercel AI SDK streaming protocol
     ▼
┌─────────────────────┐
│  Next.js Frontend   │  (Vercel — separate project)
│  - Chat UI          │
│  - Sidebar history  │
│  - localStorage     │
└────────┬────────────┘
         │  POST /api/stream
         ▼
┌─────────────────────┐
│  FastAPI Backend     │  (Vercel Python serverless)
│  api/index.py        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  BIAgent (core/agent.py)                    │
│                                             │
│  1. Fetch live data ──► MondayClient        │
│     (GraphQL, paginated)   │                │
│                            ▼                │
│  2. Build engines ──► DataEngine (per board) │
│     (schema inference, type detection)      │
│                            │                │
│  3. Generate tools ──► ToolGenerator        │
│     (auto-generates Claude tool defs        │
│      from discovered schemas)               │
│                            │                │
│  4. Claude tool-use loop:                   │
│     Claude ◄──► Tools (filter/agg/search)   │
│     (repeats until Claude has enough data)  │
│                            │                │
│  5. Stream final answer back to frontend    │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Monday.com API v2   │
│  (GraphQL, live)     │
└─────────────────────┘
