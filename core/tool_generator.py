"""
Auto-generate Claude tool definitions + system prompt from DataEngine schemas.
Fully generic — works with any board, any columns.
"""

import re
from typing import Any

from core.data_engine import DataEngine


def _safe_name(name: str) -> str:
    """Convert any board name into a valid tool-name slug."""
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "board"


class ToolGenerator:
    @staticmethod
    def generate_query_tool(board_name: str, engine: DataEngine) -> dict:
        """
        Build a Claude tool JSON for one board.
        The tool description embeds column names, types, and value hints
        so Claude knows what it can filter/aggregate on.
        """
        slug = _safe_name(board_name)
        tool_name = f"query_{slug}"

        groupable: list[str] = []
        numeric_cols: list[str] = []
        date_cols: list[str] = []
        col_descriptions: list[str] = []

        for col, info in engine.schema.items():
            ctype = info["type"]
            desc = f"{col} ({ctype}"

            if ctype == "categorical" and info.get("categories"):
                cats = info["categories"][:12]
                desc += f": {', '.join(cats)}"
                if len(info["categories"]) > 12:
                    desc += ", ..."
                groupable.append(col)
            elif ctype == "numeric":
                desc += f", range {info.get('min', '?')}–{info.get('max', '?')}"
                numeric_cols.append(col)
            elif ctype == "date":
                date_cols.append(col)
                groupable.append(col)
            elif ctype == "boolean":
                groupable.append(col)

            if info["null_pct"] > 10:
                desc += f", {info['null_pct']}% missing"
            desc += ")"
            col_descriptions.append(desc)

        tool_desc = (
            f"Query the '{board_name}' board ({len(engine.rows)} items). "
            f"Columns: {'; '.join(col_descriptions)}."
        )

        properties: dict[str, Any] = {
            "filters": {
                "type": "object",
                "description": (
                    "Key-value filter criteria. Keys are column names (case-insensitive). "
                    "Values can be: a string (exact match), a list of strings (IN), "
                    "or an object with 'min'/'max' (range) or 'contains' (substring)."
                ),
            },
            "search": {
                "type": "string",
                "description": "Full-text search across all columns.",
            },
            "group_by": {
                "type": "string",
                "description": (
                    f"Column to group results by. "
                    f"Good candidates: {', '.join(groupable[:10]) or 'any column'}."
                ),
            },
            "value_column": {
                "type": "string",
                "description": (
                    f"Numeric column to aggregate. "
                    f"Available: {', '.join(numeric_cols) or 'none detected'}."
                ),
            },
            "mode": {
                "type": "string",
                "enum": ["count", "sum", "avg", "min", "max"],
                "description": "Aggregation mode (default: count).",
            },
            "limit": {
                "type": "integer",
                "description": "Max items to return (default 50).",
            },
        }

        if date_cols:
            properties["date_filter"] = {
                "type": "object",
                "description": (
                    f"Date range filter. "
                    f"Date columns: {', '.join(date_cols)}."
                ),
                "properties": {
                    "column": {
                        "type": "string",
                        "description": "Date column name.",
                    },
                    "after": {
                        "type": "string",
                        "description": "Start date (YYYY-MM-DD, inclusive).",
                    },
                    "before": {
                        "type": "string",
                        "description": "End date (YYYY-MM-DD, inclusive).",
                    },
                },
            }

        return {
            "name": tool_name,
            "description": tool_desc,
            "input_schema": {
                "type": "object",
                "properties": properties,
            },
        }

    @staticmethod
    def generate_system_prompt(
        boards: list[dict],
    ) -> str:
        """
        Build a system-prompt section describing every board's schema,
        data quality, and available operations.
        """
        sections: list[str] = []

        for b in boards:
            name = b["name"]
            engine: DataEngine = b["engine"]
            qr = engine.quality_report

            lines = [
                f"## Board: {name}",
                f"- Items: {qr['total_rows']}",
                f"- Data completeness: {qr['completeness_pct']}%",
            ]

            if qr["columns_with_high_nulls"]:
                lines.append(
                    f"- Columns with >30% missing: "
                    f"{', '.join(qr['columns_with_high_nulls'])}"
                )

            lines.append("")
            lines.append("**Columns:**")
            for col, info in engine.schema.items():
                detail = f"  - {col}: {info['type']}"
                if info["type"] == "categorical" and info.get("categories"):
                    cats = info["categories"][:8]
                    detail += f" [{', '.join(cats)}]"
                elif info["type"] == "numeric":
                    detail += (
                        f" (range {info.get('min', '?')} – {info.get('max', '?')})"
                    )
                if info["null_pct"] > 0:
                    detail += f"  ({info['null_pct']}% null)"
                lines.append(detail)

            sections.append("\n".join(lines))

        return "\n\n".join(sections)
