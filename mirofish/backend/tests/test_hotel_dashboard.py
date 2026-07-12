from contextlib import nullcontext
from types import SimpleNamespace

from app.services.forecast_service import (
    ForecastJob,
    ForecastJobStore,
    ForecastService,
    ForecastStatus,
)
from app.services.hotel_dashboard import build_hotel_dashboard


PERFORMANCE_HEADERS = [
    "date", "property", "occupancy_pct", "adr_vnd", "revpar_vnd",
    "room_nights", "revenue_vnd", "booking_pace_pct", "pickup_room_nights",
    "pickup_24h_room_nights", "market_segment", "source", "channel",
    "guest_nationality", "lead_time_days", "cancellations",
    "budget_room_nights", "budget_adr_vnd", "last_year_room_nights",
    "ly_adr_vnd", "on_the_books_room_nights", "stly_otb_room_nights",
]


def markdown_table(headers, rows):
    return "\n".join([
        f"| {' | '.join(headers)} |",
        f"| {' | '.join('---' for _ in headers)} |",
        *(f"| {' | '.join(map(str, row))} |" for row in rows),
    ])


def write_sources(tmp_path):
    performance = tmp_path / "stored-performance.md"
    performance.write_text(markdown_table(PERFORMANCE_HEADERS, [
        [
            "2026-07-13", "ACR", 30, 100, 30, 30, 3000, 80, 5, 1,
            "Direct", "Brand.com", "Brand.com", "Vietnam", 20, 2,
            40, 100, 28, 90, 20, 25,
        ],
        [
            "2026-07-13", "ACR", 20, 80, 16, 20, 1600, 77.8, 4, 1,
            "OTA", "Booking.com", "Booking.com", "South Korea", 15, 3,
            30, 80, 25, 75, 15, 20,
        ],
    ]), encoding="utf-8")

    properties = tmp_path / "stored-properties.md"
    properties.write_text(markdown_table(
        [
            "property", "city", "province", "country", "property_type",
            "room_count", "currency", "timezone",
        ],
        [["ACR", "Cam Ranh", "Khanh Hoa", "Vietnam", "Resort", 100, "VND", "Asia/Ho_Chi_Minh"]],
    ), encoding="utf-8")

    flow = tmp_path / "stored-flow.md"
    flow.write_text(markdown_table(
        [
            "date", "property", "bookings_checking_in", "bookings_staying",
            "bookings_checking_out", "guests_checking_in", "guests_staying",
            "guests_checking_out", "staffing_risk_index", "staffing_status",
        ],
        [["2026-07-13", "ACR", 10, 50, 8, 18, 92, 15, 20, "Right amount"]],
    ), encoding="utf-8")
    return [performance, properties, flow]


def build(tmp_path):
    paths = write_sources(tmp_path)
    return build_hotel_dashboard(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        file_paths=[str(path) for path in paths],
        source_files=[
            {"filename": "performance.csv", "stored_filename": paths[0].name},
            {"filename": "properties.csv", "stored_filename": paths[1].name},
            {"filename": "guest-flow.csv", "stored_filename": paths[2].name},
        ],
        created_at="2026-07-12T06:00:00+07:00",
        completed_at="2026-07-12T06:10:00+07:00",
        output_locale="en",
    )


def test_dashboard_aggregates_only_uploaded_hotel_fields(tmp_path):
    output = build(tmp_path)

    assert output["schema_version"] == "hotel-dashboard.v1"
    assert output["available"] is True
    assert output["run_metadata"]["currency"] == "VND"
    assert output["run_metadata"]["output_locale"] == "en"
    assert output["run_metadata"]["source_files"] == [
        "performance.csv", "properties.csv", "guest-flow.csv",
    ]
    assert output["data_status"]["accepted_rows"] == 4
    assert output["data_status"]["rejected_rows"] == 0

    row = output["daily_forecast"][0]
    assert row["date"] == "2026-07-13"
    assert row["lead_days"] == 1
    assert row["rooms_available"] == 100
    assert row["room_nights"] == 50
    assert row["occupancy_pct"] == 50
    assert row["adr"] == 92
    assert row["revenue"] == 4600
    assert row["on_the_books_rooms"] == 35
    assert row["expected_final_room_nights"] is None
    assert row["budget_room_nights"] == 70
    assert row["budget_revenue"] == 6400
    assert row["last_year_room_nights"] == 53
    assert row["stly_otb_rooms"] == 45
    assert row["pickup_room_nights"] == 9
    assert row["pickup_24h_room_nights"] == 2
    assert row["cancellations"] == 5
    assert row["guests_staying"] == 92
    assert row["revenue_risk_index"] is None

    # Unsupported model outputs must stay unavailable rather than receiving
    # made-up bands, accuracy, or time-window assumptions.
    assert row["forecast_lo80_room_nights"] is None
    assert row["pickup_7d_rooms"] is None
    assert row["cancellations_7d_rooms"] is None
    assert output["model_checks"]["historical_forecast_error_pct"] is None
    assert output["capabilities"]["forecast_intervals"] is False
    assert output["capabilities"]["point_forecast"] is False
    assert output["capabilities"]["pickup_7d"] is False
    assert output["capabilities"]["cancellations_7d"] is False


def test_dashboard_provides_breakdowns_rules_and_source_freshness(tmp_path):
    output = build(tmp_path)

    assert {item["segment"] for item in output["breakdowns"]["segments"]} == {
        "Direct", "OTA",
    }
    assert {
        item["segment"]: item["room_nights"]
        for item in output["breakdowns"]["segments"]
    } == {"Direct": 20, "OTA": 15}
    assert {item["channel"] for item in output["breakdowns"]["channels"]} == {
        "Brand.com", "Booking.com",
    }
    assert {item["nationality"] for item in output["breakdowns"]["nationalities"]} == {
        "Vietnam", "South Korea",
    }
    assert output["breakdowns"]["pace"][0]["pace_vs_stly_pct"] == -22.22
    assert output["data_status"]["freshness"][0]["status"] == "unknown"
    assert output["data_status"]["freshness"][0]["source_as_of"] is None

    risk = output["risks"][0]
    action = output["actions"][0]
    assert risk["source"] == "deterministic_source_data_rule"
    assert risk["confidence"] is None
    assert risk["type"] == "booking_pace_behind_stly"
    assert risk["evidence"]["pace_vs_stly_pct"] == -22.22
    assert risk["evidence"]["room_gap_to_stly"] == 10
    assert action["risk_id"] == risk["id"]
    assert action["rule_based"] is True
    assert action["impact"] is None
    assert action["owner"] is None
    assert action["deadline"] is None


def test_dashboard_is_explicitly_unavailable_without_performance_table(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("# Narrative only\n\nNo stable hotel table.", encoding="utf-8")

    output = build_hotel_dashboard(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        file_paths=[str(source)],
        source_files=[{"filename": "notes.md", "stored_filename": source.name}],
        created_at="2026-07-12T06:00:00+07:00",
        completed_at="2026-07-12T06:10:00+07:00",
    )

    assert output["available"] is False
    assert output["daily_forecast"] == []
    assert output["data_status"]["missing_feeds"] == ["daily_performance"]
    assert output["capabilities"]["point_forecast"] is False


def test_completed_result_preserves_report_and_adds_dashboard(
    tmp_path, monkeypatch
):
    paths = write_sources(tmp_path)
    monkeypatch.setattr(ForecastJobStore, "JOBS_DIR", tmp_path / "forecasts")
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.COMPLETED,
        report_id="report_123456789abc",
        file_paths=[str(path) for path in paths],
        options={"data_profile": "hotel", "output_locale": "en"},
        completed_at="2026-07-12T06:10:00+07:00",
    )
    ForecastJobStore.save(job)
    monkeypatch.setattr(
        "app.services.forecast_service.ReportManager.get_report",
        lambda report_id: SimpleNamespace(to_dict=lambda: {"report_id": report_id}),
    )
    monkeypatch.setattr(
        "app.services.forecast_service.ProjectManager.get_project",
        lambda project_id: SimpleNamespace(files=[
            {"filename": "performance.csv", "stored_filename": paths[0].name},
            {"filename": "properties.csv", "stored_filename": paths[1].name},
            {"filename": "guest-flow.csv", "stored_filename": paths[2].name},
        ]),
    )

    result = ForecastService.get_result(job.job_id)

    assert result["report"] == {"report_id": job.report_id}
    assert result["job"]["job_id"] == job.job_id
    assert result["dashboard_output"]["schema_version"] == "hotel-dashboard.v1"
    assert result["dashboard_output"]["daily_forecast"][0]["room_nights"] == 50


def test_pms_schema_keeps_repeated_capacity_from_being_summed(tmp_path):
    headers = [
        "date", "property", "rooms_available", "rooms_sold", "room_revenue",
        "adr", "occupancy", "market_segment", "channel", "guest_nationality",
        "lead_time_days", "cancellations", "budget_occupancy", "budget_adr",
        "ly_occupancy", "ly_adr", "otb_rooms",
    ]
    source = tmp_path / "pms.md"
    source.write_text(markdown_table(headers, [
        ["2026-07-13", "ACR", 100, 30, 3000, 100, 30, "Direct", "Web", "VN", 1, 1, 40, 100, 35, 90, 20],
        ["2026-07-13", "ACR", 100, 20, 1600, 80, 20, "OTA", "OTA", "KR", 1, 2, 30, 80, 25, 75, 15],
    ]), encoding="utf-8")

    output = build_hotel_dashboard(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        file_paths=[str(source)],
        source_files=[{"filename": "pms.csv", "stored_filename": source.name}],
        created_at="2026-07-12T06:00:00+07:00",
        completed_at="2026-07-12T06:10:00+07:00",
    )

    row = output["daily_forecast"][0]
    assert row["rooms_available"] == 100
    assert row["room_nights"] == 50
    assert row["budget_room_nights"] == 70
    assert row["last_year_room_nights"] == 60
    assert row["pickup_7d_rooms"] is None
    assert output["capabilities"]["pace_vs_stly"] is False
    assert output["capabilities"]["pickup_7d"] is False
    assert output["capabilities"]["cancellations_7d"] is False


def test_pms_rows_missing_required_numeric_measures_are_rejected(tmp_path):
    headers = [
        "date", "property", "rooms_available", "rooms_sold", "room_revenue",
        "adr", "occupancy", "market_segment", "channel", "guest_nationality",
        "lead_time_days", "cancellations", "budget_occupancy", "budget_adr",
        "ly_occupancy", "ly_adr", "otb_rooms",
    ]
    source = tmp_path / "blank-pms.md"
    source.write_text(markdown_table(headers, [[
        "2026-07-13", "ACR", "", "", "", "", "", "Direct", "Web", "VN",
        "", "", "", "", "", "", "",
    ]]), encoding="utf-8")

    output = build_hotel_dashboard(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        file_paths=[str(source)],
        source_files=[{"filename": "blank-pms.csv", "stored_filename": source.name}],
        created_at="2026-07-12T06:00:00+07:00",
        completed_at="2026-07-12T06:10:00+07:00",
    )

    assert output["available"] is False
    assert output["daily_forecast"] == []
    assert output["data_status"]["accepted_rows"] == 0
    assert output["data_status"]["rejected_rows"] == 1


def test_canonical_restatements_replace_by_documented_key_and_keep_net_pickup(tmp_path):
    source = tmp_path / "performance.md"
    first = [
        "2026-07-13", "ACR", 20, 100, 20, 20, 2000, 80, 3, 1,
        "Direct", "Source A", "Brand.com", "Vietnam", 10, 1,
        25, 100, 18, 90, 15, 14,
    ]
    replacement = [
        "2026-07-13", "ACR", 25, 100, 25, 25, 2500, 82, -2, -1,
        "Direct", "Source B", "Brand.com", "Vietnam", 10, 1,
        25, 100, 18, 90, 20, 14,
    ]
    source.write_text(
        markdown_table(PERFORMANCE_HEADERS, [first, replacement]),
        encoding="utf-8",
    )

    output = build_hotel_dashboard(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        file_paths=[str(source)],
        source_files=[{"filename": "performance.csv", "stored_filename": source.name}],
        created_at="2026-07-12T06:00:00+07:00",
        completed_at="2026-07-12T06:10:00+07:00",
    )

    assert len(output["daily_forecast"]) == 1
    assert output["daily_forecast"][0]["room_nights"] == 25
    assert output["daily_forecast"][0]["pickup_room_nights"] == -2
    assert any("duplicate performance rows" in warning for warning in output["data_status"]["warnings"])


def test_background_forecast_worker_applies_persisted_output_locale(
    tmp_path, monkeypatch
):
    from app.services import forecast_service as module

    monkeypatch.setattr(ForecastJobStore, "JOBS_DIR", tmp_path / "forecasts")
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        options={"data_profile": "hotel", "output_locale": "en"},
    )
    ForecastJobStore.save(job)
    locales = []
    monkeypatch.setattr(module, "set_locale", locales.append)
    monkeypatch.setattr(ForecastService, "_semaphore", nullcontext())
    monkeypatch.setattr(
        ForecastService,
        "_admission",
        SimpleNamespace(release=lambda: None),
    )
    monkeypatch.setattr(ForecastService, "_execute_pipeline", lambda job_id: {})

    ForecastService._run_job(job.job_id)

    assert locales == ["en"]
    assert ForecastJobStore.get(job.job_id).status == ForecastStatus.COMPLETED
