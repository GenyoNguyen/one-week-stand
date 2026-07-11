"""Local MCP tools for MiroFish report generation."""

import csv
import fnmatch
import heapq
import io
import json
import math
import os
import re
from pathlib import Path
from typing import Any

import fitz
from charset_normalizer import from_bytes
from mcp.server.fastmcp import FastMCP


BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("MIROFISH_MCP_DATA_DIR", BACKEND_DIR / "uploads")).resolve()
TABLE_SCHEMA_PATH = Path(
    os.environ.get("MIROFISH_TABLE_SCHEMA_PATH", BACKEND_DIR / "table_schema.json")
).resolve()
SUPPORTED_EXTENSIONS = {".csv", ".json", ".jsonl", ".md", ".markdown", ".pdf", ".txt"}
SUPPORTED_COLUMN_TYPES = {"array", "boolean", "integer", "number", "string"}
MAX_FILE_BYTES = int(os.environ.get("MIROFISH_MCP_MAX_FILE_BYTES", str(50 * 1024 * 1024)))


def _load_table_schema() -> dict[str, Any]:
    with TABLE_SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    columns = schema.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("Table schema must define a non-empty columns array")
    keys = [column.get("key") for column in columns]
    if any(not key or not isinstance(key, str) for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("Every table column needs a unique string key")
    invalid_types = {
        column.get("type", "string") for column in columns
    } - SUPPORTED_COLUMN_TYPES
    if invalid_types:
        raise ValueError(f"Unsupported table column types: {sorted(invalid_types)}")
    return schema


def _table_tool_description() -> str:
    try:
        schema = _load_table_schema()
        columns = ", ".join(
            f"{column['key']} ({column.get('type', 'string')})"
            for column in schema["columns"]
        )
        return (
            "Validate rows against the user-defined table schema and return a structured table. "
            f"Required schema columns: {columns}."
        )
    except Exception as exc:
        return f"Create a structured table. Schema currently cannot be loaded: {exc}"


mcp = FastMCP(
    "mirofish-local-tools",
    instructions="Search MiroFish project data and create schema-validated structured tables.",
    log_level="ERROR",
)


def _decode_text(path: Path) -> str:
    raw = path.read_bytes()
    match = from_bytes(raw).best()
    return str(match) if match else raw.decode("utf-8", errors="replace")


def _read_search_units(path: Path) -> list[tuple[str, int]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        with fitz.open(path) as document:
            return [(page.get_text(), page.number + 1) for page in document]
    if suffix == ".csv":
        rows = csv.reader(io.StringIO(_decode_text(path)))
        return [(" | ".join(row), index) for index, row in enumerate(rows, start=1)]
    return [(line, index) for index, line in enumerate(_decode_text(path).splitlines(), start=1)]


def _scope_directory(project_id: str) -> Path:
    if not project_id:
        raise ValueError("project_id is required")
    if not re.fullmatch(r"proj_[a-f0-9]{12}", project_id):
        raise ValueError("Invalid project_id")
    project_dir = (DATA_DIR / "projects" / project_id / "files").resolve()
    if not project_dir.is_relative_to(DATA_DIR):
        raise ValueError("Project path escapes configured data directory")
    if not project_dir.is_dir():
        raise ValueError(f"Project data not found: {project_id}")
    return project_dir


def _source_names(project_id: str) -> dict[str, str]:
    metadata_path = DATA_DIR / "projects" / project_id / "project.json"
    try:
        with metadata_path.open("r", encoding="utf-8") as metadata_file:
            project = json.load(metadata_file)
        return {
            item["stored_filename"]: item.get("filename", item["stored_filename"])
            for item in project.get("files", [])
            if item.get("stored_filename")
        }
    except Exception:
        return {}


@mcp.tool(
    description=(
        "Search uploaded MiroFish data files. Supports PDF, CSV, JSON, JSONL, Markdown, and text. "
        "Returns ranked matching snippets with source paths and page/line locations."
    ),
    structured_output=True,
)
def search_data_files(
    query: str,
    project_id: str,
    file_pattern: str = "*",
    max_results: int = 20,
) -> dict[str, Any]:
    """Search project data for text matching all query terms."""
    query = query.strip()
    if not query:
        raise ValueError("query is required")
    wildcard = query == "*"
    max_results = max(1, min(int(max_results), 100))
    scope = _scope_directory(project_id)
    source_names = _source_names(project_id)
    terms = [
        token.strip(".-")
        for token in re.findall(r"[\w.-]+", query.casefold())
        if token.strip(".-")
    ]
    if not wildcard and not terms:
        raise ValueError("query must contain searchable terms")
    matches: list[tuple[int, int, dict[str, Any]]] = []
    errors: list[dict[str, str]] = []
    source_previews: list[dict[str, Any]] = []
    total_matches = 0
    match_order = 0
    files_scanned = 0

    for path in sorted(scope.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(scope) or not fnmatch.fnmatch(path.name, file_pattern):
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        files_scanned += 1
        try:
            preview_units = []
            for text, location in _read_search_units(path):
                if len(preview_units) < 12 and text.strip():
                    preview_units.append({
                        "location_type": "page" if path.suffix.lower() == ".pdf" else "line",
                        "location": location,
                        "snippet": re.sub(r"\s+", " ", text).strip()[:500],
                    })
                normalized = text.casefold()
                if not normalized.strip() or (not wildcard and not all(term in normalized for term in terms)):
                    continue
                score = 1 if wildcard else sum(normalized.count(term) for term in terms)
                first_match = 0 if wildcard else min(normalized.find(term) for term in terms)
                start = max(0, first_match - 300)
                end = min(len(text), first_match + 700)
                snippet = re.sub(r"\s+", " ", text[start:end]).strip()
                if start > 0:
                    snippet = f"...{snippet}"
                if end < len(text):
                    snippet = f"{snippet}..."
                item = {
                    "source": source_names.get(path.name, path.name),
                    "location_type": "page" if path.suffix.lower() == ".pdf" else "line",
                    "location": location,
                    "snippet": snippet,
                    "score": score,
                }
                total_matches += 1
                match_order += 1
                entry = (score, match_order, item)
                if len(matches) < max_results:
                    heapq.heappush(matches, entry)
                elif score > matches[0][0]:
                    heapq.heapreplace(matches, entry)
            source_previews.append({
                "source": source_names.get(path.name, path.name),
                "units": preview_units,
            })
        except Exception as exc:
            if len(errors) < 10:
                errors.append({
                    "source": source_names.get(path.name, path.name),
                    "error": str(exc),
                })

    ranked_matches = [entry[2] for entry in sorted(matches, reverse=True)]
    return {
        "query": query,
        "project_id": project_id,
        "files_scanned": files_scanned,
        "matches": ranked_matches,
        "match_count": len(ranked_matches),
        "total_match_count": total_matches,
        "source_previews": source_previews,
        "errors": errors,
    }


def _validate_value(value: Any, column: dict[str, Any], row_index: int) -> None:
    key = column["key"]
    expected = column.get("type", "string")
    valid = {
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
    }[expected]
    if not valid:
        raise ValueError(f"Row {row_index}: {key} must be {expected}")
    allowed = column.get("enum")
    if allowed and value not in allowed:
        raise ValueError(f"Row {row_index}: {key} must be one of {allowed}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise ValueError(f"Row {row_index}: {key} must be finite")
        if "minimum" in column and value < column["minimum"]:
            raise ValueError(f"Row {row_index}: {key} must be >= {column['minimum']}")
        if "maximum" in column and value > column["maximum"]:
            raise ValueError(f"Row {row_index}: {key} must be <= {column['maximum']}")


def _markdown_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return str(value).replace("|", "\\|").replace("\n", "<br>")


@mcp.tool(description=_table_tool_description(), structured_output=True)
def create_structured_table(rows: list[dict[str, Any]], title: str | None = None) -> dict[str, Any]:
    """Validate rows against table_schema.json and return JSON plus Markdown."""
    schema = _load_table_schema()
    if not 1 <= len(rows) <= 20:
        raise ValueError("Table must contain between 1 and 20 rows")
    columns = schema["columns"]
    column_keys = {column["key"] for column in columns}
    allow_extra = bool(schema.get("allow_extra_columns", False))
    normalized_rows: list[dict[str, Any]] = []

    for row_index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Row {row_index} must be an object")
        extras = set(row) - column_keys
        if extras and not allow_extra:
            raise ValueError(f"Row {row_index} has undefined columns: {sorted(extras)}")
        normalized: dict[str, Any] = {}
        for column in columns:
            key = column["key"]
            if key not in row:
                if column.get("required", True):
                    raise ValueError(f"Row {row_index} is missing required column: {key}")
                defaults = {
                    "array": [],
                    "boolean": False,
                    "integer": 0,
                    "number": 0,
                    "string": "",
                }
                default = column.get("default", defaults[column.get("type", "string")])
                _validate_value(default, column, row_index)
                normalized[key] = default
                continue
            _validate_value(row[key], column, row_index)
            normalized[key] = row[key]
        normalized_rows.append(normalized)

    labels = [_markdown_cell(column.get("label", column["key"])) for column in columns]
    markdown_lines = [
        f"**{title or schema.get('title', 'Structured Table')}**",
        "",
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join("---" for _ in labels) + " |",
    ]
    for row in normalized_rows:
        markdown_lines.append("| " + " | ".join(_markdown_cell(row[column["key"]]) for column in columns) + " |")

    return {
        "type": "structured_table",
        "title": title or schema.get("title", "Structured Table"),
        "columns": columns,
        "rows": normalized_rows,
        "markdown": "\n".join(markdown_lines),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
