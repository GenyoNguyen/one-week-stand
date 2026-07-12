import json

import pytest

from app.config import Config
from app.services.report_agent import ReportAgent


class SequenceLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat_json(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("Unexpected LLM call")
        return self.responses.pop(0)


class FakeMCPClient:
    def __init__(self, search_response=None):
        self.search_response = search_response or {"matches": []}
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "search_data_files":
            return json.dumps(self.search_response)
        if name == "create_structured_table":
            rows = arguments["rows"]
            return json.dumps({
                "type": "structured_table",
                "title": arguments.get("title"),
                "columns": ["claim", "evidence", "assessment", "confidence"],
                "rows": rows,
                "markdown": "| Claim | Evidence | Assessment | Confidence |\n| --- | --- | --- | --- |",
            })
        raise AssertionError(f"Unexpected MCP tool: {name}")


@pytest.fixture
def table_schema(tmp_path, monkeypatch):
    schema = {
        "title": "Evidence Assessment",
        "allow_extra_columns": False,
        "columns": [
            {"key": "claim", "type": "string", "required": True},
            {"key": "evidence", "type": "string", "required": True},
            {
                "key": "assessment",
                "type": "string",
                "required": True,
                "enum": ["consistent", "inconsistent", "needs_verification"],
            },
            {
                "key": "confidence",
                "type": "number",
                "required": True,
                "minimum": 0,
                "maximum": 1,
            },
        ],
    }
    schema_path = tmp_path / "table_schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr(Config, "MCP_TABLE_SCHEMA_PATH", str(schema_path))
    return schema


def make_agent(llm, mcp_client, *, search_enabled=False):
    agent = object.__new__(ReportAgent)
    agent.llm = llm
    agent.mcp_client = mcp_client
    agent.mcp_tools = {"create_structured_table": {}}
    if search_enabled:
        agent.mcp_tools["search_data_files"] = {}
    agent.project_id = "proj_012345abcdef" if search_enabled else None
    agent.source_verification_context = json.dumps({
        "source_previews": [{
            "source": "hotel-source.csv",
            "units": [{
                "location_type": "line",
                "location": 1,
                "snippet": "date | market_segment | channel | nationality",
            }],
        }],
    })
    agent.report_instructions = ""
    agent.generated_tables = []
    return agent


def table_rows_call(mcp_client):
    calls = [arguments for name, arguments in mcp_client.calls if name == "create_structured_table"]
    assert calls
    return calls[-1]["rows"]


def test_long_narrative_query_is_rejected_and_unmatched_claim_needs_verification(table_schema):
    llm = SequenceLLM([
        {
            "queries": [
                "The Anam Hotel has guests from Germany whose cancellations need attention"
            ]
        },
        {
            "rows": [{
                "claim": "German guest cancellations are rising.",
                "evidence": "The simulation indicates a cancellation shift.",
                "assessment": "consistent",
                "confidence": 0.91,
            }]
        },
    ])
    mcp_client = FakeMCPClient()
    agent = make_agent(llm, mcp_client, search_enabled=True)

    table = agent._generate_structured_table("## Forecast\nGerman cancellations may be rising.")

    assert table["type"] == "structured_table"
    assert not [call for call in mcp_client.calls if call[0] == "search_data_files"]
    row = table_rows_call(mcp_client)[0]
    assert row["assessment"] == "needs_verification"
    assert row["confidence"] == 0.5
    assert row["evidence"].startswith("No direct uploaded-source match")


def test_translated_assessment_is_normalized_to_schema_enum(table_schema):
    llm = SequenceLLM([{
        "rows": [{
            "claim": "Demand is stable.",
            "evidence": "Simulation summary only.",
            "assessment": "已验证",
            "confidence": 0.8,
        }]
    }])
    mcp_client = FakeMCPClient()
    agent = make_agent(llm, mcp_client)

    table = agent._generate_structured_table("## Forecast\nDemand is stable.")

    assert table["type"] == "structured_table"
    row = table_rows_call(mcp_client)[0]
    assert row["assessment"] == "needs_verification"
    assert row["confidence"] == 0.5


def test_schema_invalid_llm_rows_return_verification_fallback_table(table_schema):
    llm = SequenceLLM([{"rows": []}, {"rows": "not-a-list"}])
    mcp_client = FakeMCPClient()
    agent = make_agent(llm, mcp_client)

    table = agent._generate_structured_table("## Forecast\nNo structured claims were produced.")

    assert table["type"] == "structured_table"
    assert len(llm.calls) == 2
    assert len([call for call in mcp_client.calls if call[0] == "create_structured_table"]) == 1
    assert table["rows"] == [{
        "claim": "Automatic verification of simulation-derived report claims is incomplete.",
        "evidence": "No schema-valid direct source citation was produced during report finalization.",
        "assessment": "needs_verification",
        "confidence": 0.0,
    }]


def test_direct_citation_must_semantically_overlap_the_claim():
    direct_matches = [{
        "citation_id": "S1",
        "source": "hotel-source.csv",
        "location": 22,
        "snippet": "2025-07-11 | OTA | Booking.com | Germany | 49 room nights | 2 cancellations",
    }]
    rows = ReportAgent._sanitize_structured_rows(
        [{
            "claim": "Booking.com is the main source of volume and low-price room risk.",
            "evidence": "S1, hotel-source.csv line 22",
            "assessment": "consistent",
            "confidence": 0.95,
        }],
        direct_matches,
        claim_match_count=1,
    )

    assert rows[0]["assessment"] == "needs_verification"
    assert rows[0]["confidence"] == 0.5


def test_direct_citation_with_matching_row_remains_provisional():
    direct_matches = [{
        "citation_id": "S1",
        "source": "hotel-source.csv",
        "location": 22,
        "snippet": "2025-07-11 | ACR | OTA | Booking.com | Germany | 49 room nights | 2 cancellations",
    }]
    rows = ReportAgent._sanitize_structured_rows(
        [{
            "claim": "ACR recorded 49 room nights and 2 cancellations for OTA Booking.com Germany on 2025-07-11.",
            "evidence": "S1, hotel-source.csv line 22",
            "assessment": "consistent",
            "confidence": 0.95,
        }],
        direct_matches,
        claim_match_count=1,
    )

    assert rows[0]["assessment"] == "needs_verification"
    assert rows[0]["confidence"] == 0.5
    assert not rows[0]["evidence"].startswith("No direct uploaded-source match")


def test_direct_citation_rejects_numeric_values_missing_from_source():
    direct_matches = [{
        "citation_id": "S1",
        "source": "hotel-source.csv",
        "location": 22,
        "snippet": "2025-07-11 | ACR | OTA | Booking.com | Germany | 49 room nights | 2 cancellations",
    }]
    rows = ReportAgent._sanitize_structured_rows(
        [{
            "claim": "ACR recorded 999 room nights and 777 cancellations for OTA Booking.com Germany on 2025-07-11.",
            "evidence": "S1, hotel-source.csv line 22",
            "assessment": "consistent",
            "confidence": 0.95,
        }],
        direct_matches,
        claim_match_count=1,
    )

    assert rows[0]["assessment"] == "needs_verification"


def test_citation_id_and_location_must_match_exactly():
    direct_matches = [{
        "citation_id": "S1",
        "source": "hotel-source.csv",
        "location": 22,
        "snippet": "2025-07-11 | ACR | OTA | Booking.com | Germany | 49 room nights | 2 cancellations",
    }]
    rows = ReportAgent._sanitize_structured_rows(
        [{
            "claim": "ACR recorded 49 room nights and 2 cancellations for OTA Booking.com Germany on 2025-07-11.",
            "evidence": "S10, hotel-source.csv line 122",
            "assessment": "consistent",
            "confidence": 0.95,
        }],
        direct_matches,
        claim_match_count=1,
    )

    assert rows[0]["assessment"] == "needs_verification"
