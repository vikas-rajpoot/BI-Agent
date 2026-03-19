# Decision Log — BI Agent

## 1. Tech Stack Choices

### Backend: Python + FastAPI on Vercel Serverless

Chose Python because the Anthropic SDK, data manipulation, and Monday.com GraphQL integration are all first-class in Python. FastAPI gives async support out of the box, which matters since every query makes multiple live API calls to Monday.com and Claude. Deployed as a Vercel Python serverless function for zero-ops hosting — no server to manage, scales automatically.

### Frontend: Next.js + Vercel AI SDK

Chose Next.js with the `@ai-sdk/react` `useChat` hook for the conversational interface. The Vercel AI SDK handles streaming protocol, message state, and loading states out of the box — no need to build custom SSE/WebSocket handling. Deployed as a separate Vercel project to keep frontend and backend independently deployable.

### LLM: Claude (Anthropic) with Tool Use

Claude's tool-use capability is the core of the agent. Rather than hardcoding query logic, the agent auto-generates tool definitions from board schemas at runtime. Claude decides which boards to query, what filters to apply, and how to aggregate — then synthesizes a natural language answer. This means the agent adapts to any board structure without code changes.

## 2. Architecture Decisions

### No Caching — Live Data on Every Query

Per the requirement, every query triggers fresh Monday.com API calls. The agent fetches all board data, builds in-memory DataEngine instances, and discards them after each request. This ensures answers always reflect current board state.

### Auto-Generated Tool Schemas

Instead of hardcoding tools per board, `ToolGenerator` inspects each board's columns at runtime — detects types (categorical, numeric, date, boolean), enumerates categories, identifies ranges — and generates Claude tool definitions dynamically. This makes the agent board-agnostic. Add a new board, and the agent can query it immediately.

### In-Memory DataEngine (No Database)

Built a lightweight query engine (`DataEngine`) that operates on the fetched rows in memory. Supports filtering (exact, contains, range, IN), aggregation (count, sum, avg, min, max with group_by), date filtering, and full-text search. This avoids external database dependencies while handling the data volumes typical of Monday.com boards (hundreds to low thousands of items).

### Streaming with Simulated Tokens for Tool-Use Path

The Vercel AI SDK expects a streaming text protocol. When Claude doesn't use tools, the response streams natively from the Anthropic streaming API. When tools are used, the tool-use loop runs non-streaming (since we need complete tool results before proceeding), and the final answer is streamed word-by-word to the client. This gives a responsive typing feel in both paths.

## 3. Data Resilience Strategy

### Schema Inference

`DataEngine` samples column values and auto-detects types — numeric, date, categorical, or boolean. This handles the messy data without requiring predefined schemas.

### Null Handling

Every column tracks its null percentage. The system prompt includes data quality info per column, and tool results include quality notes when queried columns have significant missing values. Claude is instructed to mention caveats in its answers.

### Format Normalization

Numbers are parsed from strings with currency symbols, commas, and units. Dates are normalized to ISO format. Case-insensitive column resolution handles inconsistent naming.

## 4. Agent Visibility

### Action Traces

Every step is logged: Monday.com API calls (with duration), Claude LLM calls (with token counts), tool invocations (with inputs), and tool results (with summaries). These traces are sent alongside the response as structured data, giving full transparency into what the agent did to answer each question.

## 5. Chat History

Conversations are persisted in `localStorage` with a sidebar UI for switching between chats. Each conversation is isolated — switching chats fully remounts the chat component to avoid state leakage. Titles auto-generate from the first user message.

## 6. Deployment Architecture

Backend and frontend are separate Vercel projects from the same repo. The backend serves `/api/*` routes as Python serverless functions. The frontend calls the backend directly via `NEXT_PUBLIC_API_URL`. CORS is configured to allow cross-origin requests. This separation keeps deployments independent and avoids routing conflicts.
