from io import BytesIO
from types import SimpleNamespace

import pytest

from app import create_app
from app.config import Config
from app.models.project import ProjectManager
from app.services.forecast_service import (
    ForecastJob,
    ForecastJobStore,
    ForecastQueueFullError,
    ForecastService,
    ForecastStatus,
)
from app.services.report_agent import ReportManager
from app.services.simulation_manager import SimulationManager
from app.services.simulation_runner import SimulationRunner


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "FORECAST_API_KEY", "test-key")
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path / "simulations"))
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path / "simulations"))
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setattr(ForecastJobStore, "JOBS_DIR", tmp_path / "forecasts")
    return create_app().test_client()


def test_all_api_routes_are_registered(client):
    routes = {
        (method, str(rule))
        for rule in client.application.url_map.iter_rules()
        if str(rule).startswith("/api/")
        for method in rule.methods - {"HEAD", "OPTIONS"}
    }
    assert len(routes) == 64
    assert {
        ("POST", "/api/forecast"),
        ("GET", "/api/forecast/<job_id>"),
        ("GET", "/api/forecast/<job_id>/result"),
        ("POST", "/api/forecast/<job_id>/resume"),
        ("POST", "/api/graph/ontology/generate"),
        ("POST", "/api/graph/build"),
        ("POST", "/api/simulation/start"),
        ("POST", "/api/report/generate"),
    } <= routes


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/health", 200),
        ("/api/graph/project/list", 200),
        ("/api/graph/project/proj_missing", 404),
        ("/api/graph/task/task_missing", 404),
        ("/api/simulation/list", 200),
        ("/api/simulation/history", 200),
        ("/api/simulation/sim_missing", 404),
        ("/api/simulation/sim_missing/profiles", 404),
        ("/api/simulation/sim_missing/config", 404),
        ("/api/simulation/sim_missing/config/realtime", 404),
        ("/api/simulation/sim_missing/run-status", 200),
        ("/api/simulation/sim_missing/run-status/detail", 200),
        ("/api/simulation/sim_missing/actions", 200),
        ("/api/simulation/sim_missing/timeline", 200),
        ("/api/simulation/sim_missing/agent-stats", 200),
        ("/api/simulation/sim_missing/posts", 200),
        ("/api/simulation/sim_missing/comments", 200),
        ("/api/report/list", 200),
        ("/api/report/report_missing", 404),
        ("/api/report/report_missing/progress", 404),
        ("/api/report/report_missing/sections", 200),
        ("/api/report/check/sim_missing", 200),
    ],
)
def test_safe_get_services_do_not_return_server_errors(client, path, expected):
    response = client.get(path)
    assert response.status_code == expected


@pytest.mark.parametrize(
    "path",
    [
        "/api/graph/ontology/generate",
        "/api/graph/build",
        "/api/simulation/create",
        "/api/simulation/prepare",
        "/api/simulation/prepare/status",
        "/api/simulation/start",
        "/api/simulation/stop",
        "/api/simulation/interview",
        "/api/simulation/interview/batch",
        "/api/simulation/interview/all",
        "/api/simulation/interview/history",
        "/api/simulation/env-status",
        "/api/simulation/close-env",
        "/api/report/generate",
        "/api/report/generate/status",
        "/api/report/chat",
        "/api/report/tools/search",
        "/api/report/tools/statistics",
    ],
)
def test_post_services_validate_empty_requests(client, path):
    response = client.post(path, json={})
    assert response.status_code == 400


def test_forecast_service_auth_and_validation(client):
    assert client.post("/api/forecast").status_code == 401
    assert client.post(
        "/api/forecast",
        headers={"X-API-Key": "test-key"},
    ).status_code == 400
    assert client.get(
        "/api/forecast/forecast_missing",
        headers={"X-API-Key": "test-key"},
    ).status_code == 404
    assert client.get(
        "/api/forecast/forecast_missing/result",
        headers={"X-API-Key": "test-key"},
    ).status_code == 404
    assert client.post(
        "/api/forecast/forecast_missing/resume",
        headers={"X-API-Key": "test-key"},
    ).status_code == 404


def test_hotel_profile_rejects_supporting_files_without_performance_data(client):
    properties = """| property | city | province | country | property_type | room_count | currency | timezone |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ACR | Cam Ranh | Khanh Hoa | Vietnam | Resort | 213 | VND | Asia/Ho_Chi_Minh |
"""

    response = client.post(
        "/api/forecast",
        data={
            "data_profile": "hotel",
            "files": (BytesIO(properties.encode()), "properties.md"),
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 400
    assert "daily reservation/performance" in response.get_json()["error"]


def test_hotel_profile_accepts_performance_schema(client, monkeypatch):
    columns = [
        "date", "property", "rooms_available", "rooms_sold", "room_revenue",
        "adr", "occupancy", "market_segment", "channel", "guest_nationality",
        "lead_time_days", "cancellations", "budget_occupancy", "budget_adr",
        "ly_occupancy", "ly_adr", "otb_rooms",
    ]
    markdown = (
        f"| {' | '.join(columns)} |\n"
        f"| {' | '.join('---' for _ in columns)} |\n"
    )
    monkeypatch.setattr(
        ForecastService,
        "submit",
        lambda project_id, file_paths, options: ForecastJob(
            job_id="forecast_123456789abc",
            project_id=project_id,
            options=options,
            file_paths=file_paths,
        ),
    )

    response = client.post(
        "/api/forecast",
        data={
            "data_profile": "hotel",
            "files": (BytesIO(markdown.encode()), "performance.md"),
        },
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 202


def test_forecast_resume_endpoint_returns_conflict_for_nonresumable_job(client):
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.FAILED,
        failed_stage="report",
    )
    ForecastJobStore.save(job)

    response = client.post(
        f"/api/forecast/{job.job_id}/resume",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 409
    assert "not resumable" in response.get_json()["error"]


def test_forecast_status_exposes_report_resume_stage(client, monkeypatch):
    monkeypatch.setattr(
        ReportManager,
        "get_report",
        lambda report_id: SimpleNamespace(
            outline=SimpleNamespace(sections=[SimpleNamespace(content="Saved section")])
        ),
    )
    monkeypatch.setattr(
        ReportManager,
        "get_generated_sections",
        lambda report_id: [{"section_index": 1, "content": "Saved section"}],
    )
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.FAILED,
        failed_stage="report",
        graph_id="graph_123",
        simulation_id="sim_123",
        report_id="report_123",
    )
    ForecastJobStore.save(job)

    response = client.get(
        f"/api/forecast/{job.job_id}",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["resumable"] is True
    assert payload["resume_stage"] == "report"


def test_latest_forecast_returns_most_recent_completed_job(client):
    older = ForecastJob(
        job_id="forecast_111111111111",
        project_id="proj_111111111111",
        status=ForecastStatus.COMPLETED,
        report_id="report_older",
        created_at="2026-07-11T08:00:00",
    )
    newer = ForecastJob(
        job_id="forecast_222222222222",
        project_id="proj_222222222222",
        status=ForecastStatus.COMPLETED,
        report_id="report_newer",
        created_at="2026-07-12T08:00:00",
    )
    ForecastJobStore.save(older)
    ForecastJobStore.save(newer)

    response = client.get(
        "/api/forecast/latest",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["job_id"] == newer.job_id


def test_forecast_resume_endpoint_returns_existing_job(client, monkeypatch):
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.FAILED,
        failed_stage="graph_processing",
        graph_id="graph_123",
        graph_chunks=["chunk_1"],
        graph_episode_uuids=["episode_1"],
        graph_pending_episode_uuids=["episode_1"],
    )
    ForecastJobStore.save(job)
    queued = ForecastJob.from_dict(job.to_dict())
    queued.status = ForecastStatus.QUEUED
    monkeypatch.setattr(ForecastService, "resume", lambda job_id: queued)

    response = client.post(
        f"/api/forecast/{job.job_id}/resume",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 202
    payload = response.get_json()["data"]
    assert payload["job_id"] == job.job_id
    assert payload["status"] == "queued"


def test_forecast_resume_queue_full_is_retryable(client, monkeypatch):
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.FAILED,
    )
    ForecastJobStore.save(job)
    monkeypatch.setattr(
        ForecastService,
        "resume",
        lambda job_id: (_ for _ in ()).throw(
            ForecastQueueFullError("Forecast queue is full; retry later")
        ),
    )

    response = client.post(
        f"/api/forecast/{job.job_id}/resume",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"


def test_forecast_submit_queue_full_is_retryable(client, monkeypatch):
    monkeypatch.setattr(
        ForecastService,
        "submit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ForecastQueueFullError("Forecast queue is full; retry later")
        ),
    )

    response = client.post(
        "/api/forecast",
        data={"files": (BytesIO(b"# evidence"), "evidence.md")},
        content_type="multipart/form-data",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
