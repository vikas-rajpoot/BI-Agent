"""
BI Agent — Claude-powered business intelligence over Monday.com boards.
Every query triggers live Monday.com API calls (no caching).
"""

import json
import re
import time
from typing import Any, Optional

import anthropic

from core.data_engine import DataEngine
from core.monday_client import MondayClient
from core.tool_generator import ToolGenerator


def _safe_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "board"


class BIAgent:
    def __init__(
        self,
        monday_api_key: str,
        anthropic_api_key: str,
        board_ids: Optional[list[str]] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.monday = MondayClient(monday_api_key)
        self.claude = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        self.board_ids = board_ids
        self.model = model

        # Populated per-request by _load_boards
        self.engines: dict[str, DataEngine] = {}
        self.tools: list[dict] = []
        self.board_meta: list[dict] = []
        self.traces: list[dict] = []

    # ── live data loading ────────────────────────────────────────────

    async def _load_boards(self) -> None:
        """Fetch boards + items from Monday.com, build DataEngines."""
        t0 = time.time()

        boards = await self.monday.get_boards_with_items(
            board_ids=self.board_ids, items_limit=500
        )

        self.engines.clear()
        self.tools.clear()
        self.board_meta.clear()

        for b in boards:
            engine = DataEngine(b["rows"])
            tool_name = f"query_{_safe_name(b['name'])}"
            self.engines[tool_name] = engine
            self.tools.append(
                ToolGenerator.generate_query_tool(b["name"], engine)
            )
            self.board_meta.append({"name": b["name"], "engine": engine})

        elapsed = round((time.time() - t0) * 1000)
        self.traces.append(
            {
                "type": "api_call",
                "action": f"Monday.com → fetched {sum(len(b['rows']) for b in boards)} items from {len(boards)} board(s)",
                "boards": [b["name"] for b in boards],
                "duration_ms": elapsed,
                "api_calls": self.monday.call_log[-len(boards) - 1 :],
            }
        )

    # ── system prompt ────────────────────────────────────────────────

    def _system_prompt(self) -> str:
        data_section = ToolGenerator.generate_system_prompt(self.board_meta)
        return f"""You are a Business Intelligence agent connected to live Monday.com data.
You help founders and executives get quick, accurate answers to business questions.

## Available Data (live from Monday.com)
{data_section}

## Instructions
1. ALWAYS use the query tools to fetch data — never fabricate numbers.
2. When a question spans multiple boards, query each board separately and correlate.
3. Use group_by + value_column + mode for aggregations (e.g., revenue by sector).
4. Use filters for narrowing down (exact match, list, range, or contains).
5. Mention data-quality caveats when columns have significant missing values.
6. Provide concrete numbers, percentages, and comparisons.
7. If the question is ambiguous, ask a clarifying question.
8. Keep answers concise but insightful — think like a strategic advisor.
9. Format numbers nicely (e.g., $1,234,567 instead of 1234567).
10. When showing lists of items, use tables or bullet points for readability."""

    # ── tool execution ───────────────────────────────────────────────

    def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        engine = self.engines.get(tool_name)
        if not engine:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            # Full-text search
            if tool_input.get("search"):
                items = engine.search(tool_input["search"])
                limit = tool_input.get("limit", 50)
                return {
                    "items": items[:limit],
                    "total_found": len(items),
                    "showing": min(limit, len(items)),
                }

            # Filter first
            filtered = engine.filter(
                filters=tool_input.get("filters"),
                date_filter=tool_input.get("date_filter"),
            )

            # Aggregate if requested
            if tool_input.get("group_by"):
                agg = engine.aggregate(
                    group_by=tool_input["group_by"],
                    value_column=tool_input.get("value_column"),
                    mode=tool_input.get("mode", "count"),
                    rows=filtered,
                )
                return {
                    "aggregation": agg,
                    "total_items_analyzed": len(filtered),
                    "quality": self._quality_note(engine, tool_input),
                }

            # Return filtered items
            limit = tool_input.get("limit", 50)
            return {
                "items": filtered[:limit],
                "total_found": len(filtered),
                "showing": min(limit, len(filtered)),
                "quality": self._quality_note(engine, tool_input),
            }

        except Exception as exc:
            return {"error": str(exc)}

    def _quality_note(self, engine: DataEngine, tool_input: dict) -> str:
        cols_used: set[str] = set()
        if tool_input.get("filters"):
            cols_used.update(tool_input["filters"].keys())
        if tool_input.get("group_by"):
            cols_used.add(tool_input["group_by"])
        if tool_input.get("value_column"):
            cols_used.add(tool_input["value_column"])

        notes = []
        for c in cols_used:
            resolved = engine._resolve_column(c)
            if resolved and engine.schema[resolved]["null_pct"] > 10:
                notes.append(
                    f"'{resolved}' has {engine.schema[resolved]['null_pct']}% missing values"
                )
        return "; ".join(notes) if notes else "Good data quality"

    @staticmethod
    def _result_summary(result: dict) -> str:
        if "error" in result:
            return f"Error: {result['error']}"
        if "aggregation" in result:
            return (
                f"{len(result['aggregation'])} groups, "
                f"{result['total_items_analyzed']} items"
            )
        return (
            f"{result.get('total_found', 0)} found, "
            f"showing {result.get('showing', 0)}"
        )

    # ── main chat loop ───────────────────────────────────────────────

    async def chat(self, messages: list[dict]) -> dict:
        """
        Process a conversation. Returns {"response": str, "traces": list}.
        Fetches fresh Monday.com data on every call.
        """
        self.traces = []
        self.monday.call_log = []

        # 1. Live-load boards
        await self._load_boards()

        if not self.engines:
            return {
                "response": "No Monday.com boards found. Please check your MONDAY_BOARD_IDS configuration.",
                "traces": self.traces,
            }

        system = self._system_prompt()

        # 2. Initial Claude call
        t0 = time.time()
        response = await self.claude.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            tools=self.tools,
            messages=messages,
        )
        self.traces.append(
            {
                "type": "llm_call",
                "action": "Claude → analyzing query",
                "model": self.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "duration_ms": round((time.time() - t0) * 1000),
            }
        )

        # 3. Tool-use loop
        loop_messages = list(messages)

        while response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                self.traces.append(
                    {
                        "type": "tool_call",
                        "action": f"Tool → {block.name}",
                        "input": block.input,
                    }
                )

                result = self._execute_tool(block.name, block.input)

                self.traces.append(
                    {
                        "type": "tool_result",
                        "action": f"Result ← {block.name}",
                        "summary": self._result_summary(result),
                    }
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    }
                )

            # Build follow-up messages
            # Serialize content blocks for the assistant message
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append(
                        {"type": "text", "text": block.text}
                    )
                elif block.type == "tool_use":
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )

            loop_messages.append(
                {"role": "assistant", "content": assistant_content}
            )
            loop_messages.append({"role": "user", "content": tool_results})

            t0 = time.time()
            response = await self.claude.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                tools=self.tools,
                messages=loop_messages,
            )
            self.traces.append(
                {
                    "type": "llm_call",
                    "action": "Claude → synthesizing answer",
                    "model": self.model,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "duration_ms": round((time.time() - t0) * 1000),
                }
            )

        # 4. Extract final text
        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )

        return {"response": text, "traces": self.traces}






class BIAgentStreaming(BIAgent):
    """Extends BIAgent to yield Vercel AI SDK Data Stream Protocol chunks."""

    async def _run_tool_loop(self, system: str, loop_messages: list[dict]):
        """
        Run the tool-use loop non-streaming. Returns the final loop_messages
        ready for the synthesis call (which will be streamed).
        If no tools are needed at all, returns None (caller should stream directly).
        """
        response = await self.claude.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            tools=self.tools,
            messages=loop_messages,
        )

        if response.stop_reason != "tool_use":
            # No tools needed — caller should stream from original messages
            return None

        while response.stop_reason == "tool_use":
            tool_results = []
            assistant_content = []

            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
                    self.traces.append({
                        "type": "tool_call",
                        "action": f"Tool → {block.name}",
                        "input": block.input,
                    })
                    result = self._execute_tool(block.name, block.input)
                    self.traces.append({
                        "type": "tool_result",
                        "action": f"Result ← {block.name}",
                        "summary": self._result_summary(result),
                    })
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })

            loop_messages.append({"role": "assistant", "content": assistant_content})
            loop_messages.append({"role": "user", "content": tool_results})

            # Check if more tools are needed
            response = await self.claude.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                tools=self.tools,
                messages=loop_messages,
            )

        # Tool loop done. But we consumed the final answer non-streaming.
        # Return the text so we can stream it word-by-word.
        final_text = "".join(
            b.text for b in response.content if hasattr(b, "text")
        )
        return final_text

    async def chat_stream(self, messages: list[dict]):
        """
        Async generator yielding Vercel AI SDK Data Stream Protocol lines.
        """
        self.traces = []
        self.monday.call_log = []

        await self._load_boards()

        if not self.engines:
            yield f'0:{json.dumps("No Monday.com boards found. Please check config.")}\n'
            yield 'd:{"finishReason":"stop","usage":{}}\n'
            return

        system = self._system_prompt()
        loop_messages = list(messages)

        result = await self._run_tool_loop(system, loop_messages)

        if result is None:
            # No tools used — stream the answer directly from Claude
            async with self.claude.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield f'0:{json.dumps(text)}\n'
        else:
            # Tools were used, we have the final text — stream word by word
            import asyncio
            words = result.split(' ')
            for i, word in enumerate(words):
                chunk = word if i == len(words) - 1 else word + ' '
                yield f'0:{json.dumps(chunk)}\n'
                await asyncio.sleep(0.02)  # Small delay for streaming feel

        yield f'2:{json.dumps([{"traces": self.traces}])}\n'
        yield 'd:{"finishReason":"stop","usage":{}}\n'






