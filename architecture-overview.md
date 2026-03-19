

```
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
```

The key flow: User asks a question → backend fetches fresh Monday.com data → builds in-memory query engines → auto-generates Claude tools from board schemas → Claude decides which queries to run via tool-use → DataEngine executes filters/aggregations locally → Claude synthesizes the answer → streams back to the frontend word-by-word.

Everything is stateless per request. No database, no cache, no preloaded data.