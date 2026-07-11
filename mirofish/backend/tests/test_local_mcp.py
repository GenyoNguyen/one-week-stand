import json

import pytest

from app.config import Config
from app.services.local_mcp_client import LocalMCPClient


PROJECT_ID = "proj_012345abcdef"


@pytest.fixture
def mcp_client(tmp_path, monkeypatch):
    project_dir = tmp_path / "projects" / PROJECT_ID / "files"
    project_dir.mkdir(parents=True)
    (project_dir / "hotel.csv").write_text(
        "date,rooms,revenue\n2026-07-11,42,12345\n",
        encoding="utf-8",
    )
    (project_dir / "channels.txt").write_text(
        "property | channel\nThe Anam 1 | Booking.com\n",
        encoding="utf-8",
    )
    (project_dir.parent / "project.json").write_text(
        json.dumps({
            "files": [
                {"stored_filename": "hotel.csv", "filename": "hotel-source.csv"},
                {"stored_filename": "channels.txt", "filename": "channel-source.txt"},
            ]
        }),
        encoding="utf-8",
    )

    schema_path = tmp_path / "table_schema.json"
    schema = {
        "title": "Evidence Assessment",
        "allow_extra_columns": False,
        "columns": [
            {"key": "claim", "type": "string", "required": True},
            {
                "key": "confidence",
                "type": "number",
                "required": True,
                "minimum": 0,
                "maximum": 1,
            },
        ],
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    monkeypatch.setattr(Config, "MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(Config, "MCP_TABLE_SCHEMA_PATH", str(schema_path))
    return LocalMCPClient()


def test_stdio_server_lists_and_calls_tools(mcp_client):
    assert {tool["name"] for tool in mcp_client.list_tools()} == {
        "search_data_files",
        "create_structured_table",
    }

    search = json.loads(
        mcp_client.call_tool(
            "search_data_files",
            {"query": "rooms revenue", "project_id": PROJECT_ID},
        )
    )
    assert search["files_scanned"] == 2
    assert search["match_count"] == 1
    assert search["matches"][0]["source"] == "hotel-source.csv"

    table = json.loads(
        mcp_client.call_tool(
            "create_structured_table",
            {"rows": [{"claim": "Demand is up", "confidence": 0.9}]},
        )
    )
    assert table["type"] == "structured_table"
    assert table["rows"] == [{"claim": "Demand is up", "confidence": 0.9}]
    assert "| Demand is up | 0.9 |" in table["markdown"]


def test_search_normalizes_punctuation_and_returns_each_source_preview(mcp_client):
    search = json.loads(
        mcp_client.call_tool(
            "search_data_files",
            {"query": "rooms, revenue.", "project_id": PROJECT_ID},
        )
    )

    assert search["match_count"] == 1
    assert search["matches"][0]["source"] == "hotel-source.csv"
    previews = {preview["source"]: preview["units"] for preview in search["source_previews"]}
    assert set(previews) == {"hotel-source.csv", "channel-source.txt"}
    assert previews["hotel-source.csv"][0] == {
        "location_type": "line",
        "location": 1,
        "snippet": "date | rooms | revenue",
    }
    assert previews["channel-source.txt"][1]["snippet"] == "The Anam 1 | Booking.com"


def test_search_rejects_project_path_traversal(mcp_client):
    with pytest.raises(RuntimeError, match="Invalid project_id"):
        mcp_client.call_tool(
            "search_data_files",
            {"query": "rooms", "project_id": "../../outside"},
        )


def test_table_rejects_values_outside_schema_bounds(mcp_client):
    with pytest.raises(RuntimeError, match="confidence must be <= 1"):
        mcp_client.call_tool(
            "create_structured_table",
            {"rows": [{"claim": "Demand is up", "confidence": 1.1}]},
        )
