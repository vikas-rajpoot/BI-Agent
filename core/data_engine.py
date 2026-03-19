"""
Generic, schema-agnostic data engine.
Auto-infers column types from data, normalizes messy values,
and supports filtering + aggregation on any dataset.
"""

import re
from datetime import datetime
from typing import Any, Optional


# Values treated as null regardless of column type
_NULL_INDICATORS = frozenset(
    {"", "null", "none", "n/a", "na", "-", "--", "nan", "undefined", "tbd", "tba"}
)

# ── helpers ──────────────────────────────────────────────────────────

_DATE_PATTERNS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}"), "%Y-%m-%d"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}T"), "%Y-%m-%dT%H:%M:%S"),
    (re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"), "%m/%d/%Y"),
    (re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$"), "%m/%d/%y"),
    (re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$"), "%d-%m-%Y"),
    (re.compile(r"^\w{3,9}\s+\d{1,2},?\s+\d{4}"), None),  # "Jan 15, 2024"
    (re.compile(r"^\d{1,2}\s+\w{3,9}\s+\d{4}"), None),     # "15 January 2024"
]

_DATE_PARSE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%SZ",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
    "%d %B %Y",
    "%d %b %Y",
]


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    return str(value).strip().lower() in _NULL_INDICATORS


def _looks_like_date(value: str) -> bool:
    s = value.strip()
    return any(pat.match(s) for pat, _ in _DATE_PATTERNS)


def _looks_like_number(value: str) -> bool:
    cleaned = re.sub(r"[$€£¥₹,\s]", "", value.strip())
    cleaned = cleaned.rstrip("%")
    if not cleaned:
        return False
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


def _parse_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    cleaned = re.sub(r"[$€£¥₹,\s]", "", s)
    is_pct = cleaned.endswith("%")
    cleaned = cleaned.rstrip("%")
    if not cleaned:
        return None
    try:
        result = float(cleaned)
        return result / 100 if is_pct else result
    except ValueError:
        return None


def _parse_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    # Fast path: already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    for fmt in _DATE_PARSE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Return original if unparseable — better than losing data
    return s


# ── DataEngine ───────────────────────────────────────────────────────


class DataEngine:
    """
    Feed it any list[dict] — it figures out the schema, cleans the data,
    and exposes filter / aggregate / search.
    """

    def __init__(self, rows: list[dict]):
        self.raw_rows = rows
        self.columns = self._discover_columns()
        self.schema = self._infer_schema()
        self.rows = [self._normalize_row(r) for r in rows]
        self.quality_report = self._build_quality_report()

    # ── schema inference ─────────────────────────────────────────────

    def _discover_columns(self) -> list[str]:
        seen: dict[str, None] = {}
        for row in self.raw_rows:
            for k in row:
                if k not in seen:
                    seen[k] = None
        return list(seen)

    def _sample_non_null(self, col: str, max_n: int = 100) -> list[str]:
        samples = []
        for row in self.raw_rows:
            v = row.get(col)
            if not _is_null(v):
                samples.append(str(v).strip())
                if len(samples) >= max_n:
                    break
        return samples

    def _detect_type(self, samples: list[str]) -> str:
        if not samples:
            return "text"

        n = len(samples)

        # Date check (before numeric — ISO dates like 2024-01-15 pass float())
        date_hits = sum(1 for s in samples if _looks_like_date(s))
        if date_hits / n > 0.6:
            return "date"

        # Numeric check
        num_hits = sum(1 for s in samples if _looks_like_number(s))
        if num_hits / n > 0.6:
            return "numeric"

        # Boolean check
        bool_vals = {"true", "false", "yes", "no", "1", "0"}
        bool_hits = sum(1 for s in samples if s.lower() in bool_vals)
        if bool_hits / n > 0.8:
            return "boolean"

        # Categorical vs free-text heuristic
        unique = set(s.lower() for s in samples)
        if len(unique) <= 30 or (len(unique) / n) < 0.3:
            return "categorical"

        return "text"

    def _infer_schema(self) -> dict:
        schema: dict[str, dict] = {}
        total = max(len(self.raw_rows), 1)

        for col in self.columns:
            samples = self._sample_non_null(col)
            col_type = self._detect_type(samples)

            null_count = sum(1 for r in self.raw_rows if _is_null(r.get(col)))
            unique_vals = set(
                str(r.get(col, "")).strip().lower()
                for r in self.raw_rows
                if not _is_null(r.get(col))
            )

            info: dict[str, Any] = {
                "type": col_type,
                "null_count": null_count,
                "total_count": total,
                "null_pct": round(null_count / total * 100, 1),
                "unique_count": len(unique_vals),
            }

            if col_type == "categorical":
                info["categories"] = sorted(unique_vals)[:30]
            elif col_type == "numeric" and samples:
                nums = [_parse_number(s) for s in samples]
                nums = [x for x in nums if x is not None]
                if nums:
                    info["min"] = min(nums)
                    info["max"] = max(nums)
                    info["mean"] = round(sum(nums) / len(nums), 2)

            schema[col] = info

        return schema

    # ── normalization ────────────────────────────────────────────────

    def _normalize_row(self, row: dict) -> dict:
        out: dict[str, Any] = {}
        for col in self.columns:
            raw = row.get(col)

            if _is_null(raw):
                out[col] = None
                continue

            col_type = self.schema[col]["type"]

            if col_type == "numeric":
                out[col] = _parse_number(raw)
            elif col_type == "date":
                out[col] = _parse_date(raw)
            elif col_type == "boolean":
                out[col] = str(raw).strip().lower() in {"true", "yes", "1"}
            elif col_type == "categorical":
                out[col] = str(raw).strip()
            else:
                out[col] = str(raw).strip()

        return out

    # ── filtering ────────────────────────────────────────────────────

    def _resolve_column(self, key: str) -> Optional[str]:
        """Case-insensitive + underscore-tolerant column lookup."""
        norm = key.lower().replace("_", " ")
        for col in self.columns:
            if col.lower() == key.lower():
                return col
            if col.lower().replace("_", " ") == norm:
                return col
        # Substring match as fallback
        for col in self.columns:
            if norm in col.lower().replace("_", " "):
                return col
        return None

    def filter(
        self,
        filters: Optional[dict] = None,
        date_filter: Optional[dict] = None,
        rows: Optional[list[dict]] = None,
    ) -> list[dict]:
        result = rows if rows is not None else list(self.rows)

        if filters:
            for key, value in filters.items():
                col = self._resolve_column(key)
                if not col:
                    continue
                col_type = self.schema[col]["type"]

                if isinstance(value, list):
                    lower_vals = [str(v).lower() for v in value]
                    result = [
                        r
                        for r in result
                        if r.get(col) is not None
                        and str(r[col]).lower() in lower_vals
                    ]

                elif isinstance(value, dict):
                    if "min" in value:
                        result = [
                            r
                            for r in result
                            if r.get(col) is not None and r[col] >= value["min"]
                        ]
                    if "max" in value:
                        result = [
                            r
                            for r in result
                            if r.get(col) is not None and r[col] <= value["max"]
                        ]
                    if "contains" in value:
                        needle = str(value["contains"]).lower()
                        result = [
                            r
                            for r in result
                            if r.get(col) is not None
                            and needle in str(r[col]).lower()
                        ]

                else:
                    if col_type in ("categorical", "text"):
                        target = str(value).lower()
                        result = [
                            r
                            for r in result
                            if r.get(col) is not None
                            and str(r[col]).lower() == target
                        ]
                    else:
                        result = [
                            r for r in result if r.get(col) == value
                        ]

        if date_filter:
            col = self._resolve_column(date_filter.get("column", ""))
            if col:
                if "after" in date_filter:
                    result = [
                        r
                        for r in result
                        if r.get(col) is not None and r[col] >= date_filter["after"]
                    ]
                if "before" in date_filter:
                    result = [
                        r
                        for r in result
                        if r.get(col) is not None and r[col] <= date_filter["before"]
                    ]

        return result

    # ── aggregation ──────────────────────────────────────────────────

    def aggregate(
        self,
        group_by: str,
        value_column: Optional[str] = None,
        mode: str = "count",
        rows: Optional[list[dict]] = None,
    ) -> list[dict]:
        target = rows if rows is not None else self.rows
        gb_col = self._resolve_column(group_by)
        val_col = self._resolve_column(value_column) if value_column else None

        groups: dict[str, dict] = {}
        for row in target:
            key = row.get(gb_col) if gb_col else row.get(group_by)
            key = str(key) if key is not None else "(Missing)"

            if key not in groups:
                groups[key] = {"count": 0, "values": []}

            groups[key]["count"] += 1

            if val_col:
                v = row.get(val_col)
                if v is not None and isinstance(v, (int, float)):
                    groups[key]["values"].append(v)

        result = []
        for group, data in groups.items():
            entry: dict[str, Any] = {"group": group, "count": data["count"]}
            nums = data["values"]

            if mode == "sum" and nums:
                entry["sum"] = round(sum(nums), 2)
            elif mode == "avg" and nums:
                entry["avg"] = round(sum(nums) / len(nums), 2)
            elif mode == "min" and nums:
                entry["min"] = min(nums)
            elif mode == "max" and nums:
                entry["max"] = max(nums)

            result.append(entry)

        sort_key = mode if mode in ("sum", "avg", "min", "max") else "count"
        result.sort(key=lambda x: x.get(sort_key, 0) or 0, reverse=True)
        return result

    # ── full-text search ─────────────────────────────────────────────

    def search(
        self,
        query: str,
        columns: Optional[list[str]] = None,
        rows: Optional[list[dict]] = None,
    ) -> list[dict]:
        target = rows if rows is not None else self.rows
        q = query.lower()
        cols = columns or self.columns
        hits = []
        for row in target:
            for col in cols:
                val = row.get(col)
                if val is not None and q in str(val).lower():
                    hits.append(row)
                    break
        return hits

    # ── quality report ───────────────────────────────────────────────

    def _build_quality_report(self) -> dict:
        total_cells = len(self.raw_rows) * max(len(self.columns), 1)
        null_cells = sum(info["null_count"] for info in self.schema.values())
        high_null_cols = [
            col for col, info in self.schema.items() if info["null_pct"] > 30
        ]
        return {
            "total_rows": len(self.raw_rows),
            "total_columns": len(self.columns),
            "total_cells": total_cells,
            "null_cells": null_cells,
            "completeness_pct": round(
                (1 - null_cells / max(total_cells, 1)) * 100, 1
            ),
            "columns_with_high_nulls": high_null_cols,
            "column_types": {
                col: info["type"] for col, info in self.schema.items()
            },
        }
