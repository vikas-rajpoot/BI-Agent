"""
Monday.com API v2 client.
Every call is live — no caching.
"""

import json
import time
from typing import Any, Optional

import httpx

MONDAY_API_URL = "https://api.monday.com/v2"


class MondayClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "API-Version": "2024-10",
        }
        self.call_log: list[dict] = []

    # ── low-level GraphQL executor ───────────────────────────────────

    async def _execute(
        self, query: str, variables: Optional[dict] = None
    ) -> dict:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        t0 = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                MONDAY_API_URL, headers=self.headers, json=payload
            )
            resp.raise_for_status()
            body = resp.json()

        elapsed_ms = round((time.time() - t0) * 1000)
        self.call_log.append(
            {
                "query_preview": query.strip()[:120],
                "duration_ms": elapsed_ms,
                "status": resp.status_code,
            }
        )

        if "errors" in body:
            raise RuntimeError(f"Monday.com API error: {body['errors']}")
        if "error_message" in body:
            raise RuntimeError(f"Monday.com API error: {body['error_message']}")

        return body["data"]

    # ── public API ───────────────────────────────────────────────────

    async def get_boards_with_items(
        self,
        board_ids: Optional[list[str]] = None,
        items_limit: int = 500,
    ) -> list[dict]:
        """
        Fetch boards with columns + items in as few calls as possible.
        Returns list of {"id", "name", "rows": list[dict], "columns": dict}.
        """
        if board_ids:
            query = """
            query ($ids: [ID!]!, $limit: Int!) {
              boards(ids: $ids) {
                id
                name
                columns { id title type }
                items_page(limit: $limit) {
                  cursor
                  items {
                    id
                    name
                    column_values { id text value type }
                  }
                }
              }
            }
            """
            data = await self._execute(
                query, {"ids": board_ids, "limit": items_limit}
            )
        else:
            query = """
            query ($limit: Int!) {
              boards(limit: 50) {
                id
                name
                items_count
                columns { id title type }
                items_page(limit: $limit) {
                  cursor
                  items {
                    id
                    name
                    column_values { id text value type }
                  }
                }
              }
            }
            """
            data = await self._execute(query, {"limit": items_limit})

        results = []
        for board in data["boards"]:
            # Skip empty boards when auto-discovering
            if not board_ids and board.get("items_count", 0) == 0:
                continue

            col_map = {c["id"]: c for c in board["columns"]}
            page = board["items_page"]
            items = list(page["items"])
            cursor = page.get("cursor")

            # Paginate remaining items
            while cursor:
                next_data = await self._execute(
                    """
                    query ($cursor: String!, $limit: Int!) {
                      next_items_page(cursor: $cursor, limit: $limit) {
                        cursor
                        items {
                          id
                          name
                          column_values { id text value type }
                        }
                      }
                    }
                    """,
                    {"cursor": cursor, "limit": items_limit},
                )
                next_page = next_data["next_items_page"]
                items.extend(next_page["items"])
                cursor = next_page.get("cursor")

            # Flatten into row dicts
            rows = []
            for item in items:
                row: dict[str, Any] = {"Name": item["name"]}
                for cv in item["column_values"]:
                    title = col_map.get(cv["id"], {}).get("title", cv["id"])
                    row[title] = self._extract_value(cv)
                rows.append(row)

            results.append(
                {
                    "id": board["id"],
                    "name": board["name"],
                    "rows": rows,
                    "columns": col_map,
                }
            )

        return results

    # ── column value extraction ──────────────────────────────────────

    @staticmethod
    def _extract_value(cv: dict) -> Any:
        """
        Return the most useful Python value from a Monday column_value.
        Prefer `text` (human-readable); fall back to parsing `value` JSON.
        """
        text = cv.get("text")
        if text:
            return text

        raw = cv.get("value")
        if not raw:
            return None

        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return raw

        if isinstance(parsed, (int, float, str, bool)):
            return parsed

        if isinstance(parsed, dict):
            # status / color
            if "label" in parsed:
                return parsed["label"]
            # date
            if "date" in parsed:
                return parsed["date"]
            # people
            if "personsAndTeams" in parsed:
                ids = [str(p["id"]) for p in parsed["personsAndTeams"]]
                return ", ".join(ids)
            # link
            if "url" in parsed:
                return parsed["url"]
            # generic fallback
            return parsed.get("text") or parsed.get("value")

        return raw
