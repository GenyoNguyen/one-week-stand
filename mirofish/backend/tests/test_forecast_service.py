from contextlib import nullcontext
from io import BytesIO
from types import SimpleNamespace

import pytest

from app import create_app
from app.config import Config
from app.services.forecast_service import (
    ForecastJob,
    ForecastJobStore,
    ForecastService,
    ForecastStatus,
)
from app.services.report_agent import (
    Report,
    ReportManager,
    ReportOutline,
    ReportSection,
    ReportStatus,
)
from app.services.simulation_manager import SimulationStatus


@pytest.fixture
def isolated_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(ForecastJobStore, "JOBS_DIR", tmp_path / "forecasts")


def monotonic_sequence(values):
    iterator = iter(values)
    current = [values[-1]]

    def read():
        current[0] = next(iterator, current[0])
        return current[0]

    return read


def test_job_store_persists_status(isolated_jobs):
    job = ForecastJob(job_id="forecast_123456789abc", project_id="proj_123456789abc")
    ForecastJobStore.save(job)

    ForecastJobStore.update(
        job.job_id,
        status=ForecastStatus.RUNNING,
        stage="graph",
        progress=25,
    )

    loaded = ForecastJobStore.get(job.job_id)
    assert loaded.status == ForecastStatus.RUNNING
    assert loaded.stage == "graph"
    assert loaded.progress == 25


def test_graph_documents_are_bounded_and_sample_every_large_source(monkeypatch):
    small = "Source file: properties.md\n" + "property metadata\n" * 10
    large_a = "Source file: performance.md\n" + "A" * 2500 + "A-tail"
    large_b = "Source file: guest-flow.md\n" + "B" * 2500 + "B-tail"
    monkeypatch.setattr(Config, "FORECAST_GRAPH_MAX_SOURCE_CHARS", 1000)

    sampled = ForecastService._prepare_graph_documents([small, large_a, large_b])

    assert sampled[0] == small.strip()
    assert sum(map(len, sampled)) <= 1000
    assert sampled[1].startswith("Source file: performance.md")
    assert sampled[1].endswith("A-tail")
    assert sampled[2].startswith("Source file: guest-flow.md")
    assert sampled[2].endswith("B-tail")
    assert all("representative rows omitted" in text for text in sampled[1:])


def test_episode_polling_retries_transient_errors_and_persists_completion(
    isolated_jobs, monkeypatch
):
    from app.services import forecast_service as module

    job = ForecastJob(job_id="forecast_123456789abc", project_id="proj_123456789abc")
    ForecastJobStore.save(job)
    calls = {"episode_retry": 0, "episode_pending": 0}

    def get_episode(uuid_):
        calls[uuid_] += 1
        if uuid_ == "episode_retry" and calls[uuid_] == 1:
            raise ConnectionError("temporary Zep failure")
        return SimpleNamespace(processed=calls[uuid_] > 1)

    builder = SimpleNamespace(
        client=SimpleNamespace(
            graph=SimpleNamespace(
                episode=SimpleNamespace(get=get_episode),
            )
        )
    )
    monkeypatch.setattr(Config, "FORECAST_GRAPH_TIMEOUT_SECONDS", 60)
    monkeypatch.setattr(module.time, "monotonic", lambda: 0)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)

    ForecastService._wait_for_episodes(
        job.job_id,
        builder,
        ["episode_retry", "episode_pending"],
    )

    persisted = ForecastJobStore.get(job.job_id)
    assert calls == {"episode_retry": 2, "episode_pending": 2}
    assert persisted.stage == "graph_processing"
    assert persisted.progress == 39
    assert persisted.message == "Waiting for graph processing: 2/2"
    assert persisted.graph_pending_episode_uuids == []


def test_episode_polling_timeout_reports_pending_count_and_persists_progress(
    isolated_jobs, monkeypatch
):
    from app.services import forecast_service as module

    job = ForecastJob(job_id="forecast_123456789abc", project_id="proj_123456789abc")
    ForecastJobStore.save(job)
    sleeps = []

    def get_episode(uuid_):
        return SimpleNamespace(processed=uuid_ == "episode_done")

    builder = SimpleNamespace(
        client=SimpleNamespace(
            graph=SimpleNamespace(
                episode=SimpleNamespace(get=get_episode),
            )
        )
    )
    monkeypatch.setattr(Config, "FORECAST_GRAPH_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(
        module.time,
        "monotonic",
        monotonic_sequence([0, 0, 0, 0, 0, 2, 2, 2]),
    )
    monkeypatch.setattr(module.time, "sleep", sleeps.append)

    with pytest.raises(
        TimeoutError,
        match=r"Graph processing stalled for 2 seconds with 2 pending episodes",
    ):
        ForecastService._wait_for_episodes(
            job.job_id,
            builder,
            ["episode_done", "episode_pending_1", "episode_pending_2"],
        )

    persisted = ForecastJobStore.get(job.job_id)
    assert sleeps == [Config.FORECAST_GRAPH_POLL_SECONDS]
    assert persisted.stage == "graph_processing"
    assert persisted.progress == 34
    assert persisted.message == "Waiting for graph processing: 1/3"
    assert persisted.graph_pending_episode_uuids == [
        "episode_pending_1",
        "episode_pending_2",
    ]


def test_episode_wait_continues_while_zep_makes_progress(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(job_id="forecast_123456789abc", project_id="proj_123456789abc")
    ForecastJobStore.save(job)
    calls = {"episode_fast": 0, "episode_slow": 0}

    def get_episode(uuid_):
        calls[uuid_] += 1
        return SimpleNamespace(
            processed=uuid_ == "episode_fast" or calls[uuid_] >= 2
        )

    builder = SimpleNamespace(
        client=SimpleNamespace(
            graph=SimpleNamespace(episode=SimpleNamespace(get=get_episode))
        )
    )
    monkeypatch.setattr(Config, "FORECAST_GRAPH_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(Config, "FORECAST_GRAPH_MAX_TIMEOUT_SECONDS", 10)
    monkeypatch.setattr(Config, "FORECAST_GRAPH_POLL_SECONDS", 0.1)
    monkeypatch.setattr(
        module.time,
        "monotonic",
        monotonic_sequence([0, 0, 0, 0.8, 0.8, 1.6]),
    )
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    ForecastService._wait_for_episodes(
        job.job_id,
        builder,
        ["episode_fast", "episode_slow"],
    )

    assert ForecastJobStore.get(job.job_id).graph_pending_episode_uuids == []


def test_episode_wait_hard_cap_bounds_continuous_progress(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(job_id="forecast_123456789abc", project_id="proj_123456789abc")
    ForecastJobStore.save(job)
    calls = {"episode_fast": 0, "episode_medium": 0, "episode_slow": 0}
    thresholds = {"episode_fast": 1, "episode_medium": 2, "episode_slow": 99}

    def get_episode(uuid_):
        calls[uuid_] += 1
        return SimpleNamespace(processed=calls[uuid_] >= thresholds[uuid_])

    builder = SimpleNamespace(
        client=SimpleNamespace(
            graph=SimpleNamespace(episode=SimpleNamespace(get=get_episode))
        )
    )
    monkeypatch.setattr(Config, "FORECAST_GRAPH_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(Config, "FORECAST_GRAPH_MAX_TIMEOUT_SECONDS", 1.5)
    monkeypatch.setattr(Config, "FORECAST_GRAPH_POLL_SECONDS", 0.1)
    monkeypatch.setattr(
        module.time,
        "monotonic",
        monotonic_sequence([0, 0, 0, 0, 0.8, 0.8, 0.8, 1.6]),
    )
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    with pytest.raises(TimeoutError, match="hard wait limit"):
        ForecastService._wait_for_episodes(
            job.job_id,
            builder,
            ["episode_fast", "episode_medium", "episode_slow"],
        )

    persisted = ForecastJobStore.get(job.job_id)
    assert persisted.graph_pending_episode_uuids == ["episode_slow"]


def test_episode_status_outage_is_not_reported_as_processing_stall(
    isolated_jobs, monkeypatch
):
    from app.services import forecast_service as module

    job = ForecastJob(job_id="forecast_123456789abc", project_id="proj_123456789abc")
    ForecastJobStore.save(job)

    def get_episode(uuid_):
        raise ConnectionError("Zep unavailable")

    builder = SimpleNamespace(
        client=SimpleNamespace(
            graph=SimpleNamespace(episode=SimpleNamespace(get=get_episode))
        )
    )
    monkeypatch.setattr(Config, "FORECAST_GRAPH_TIMEOUT_SECONDS", 60)
    monkeypatch.setattr(Config, "FORECAST_GRAPH_MAX_TIMEOUT_SECONDS", 120)
    monkeypatch.setattr(Config, "FORECAST_GRAPH_STATUS_ERROR_SWEEPS", 3)
    monkeypatch.setattr(Config, "FORECAST_GRAPH_POLL_SECONDS", 0.1)
    monkeypatch.setattr(module.time, "monotonic", lambda: 0)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    with pytest.raises(ConnectionError, match="3 consecutive checks: Zep unavailable"):
        ForecastService._wait_for_episodes(
            job.job_id,
            builder,
            ["episode_1", "episode_2"],
        )


def test_public_job_exposes_resume_counts_without_episode_ids():
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.FAILED,
        failed_stage="graph_processing",
        graph_id="graph_123",
        graph_chunks=["chunk_1", "chunk_2"],
        graph_episode_uuids=["episode_1", "episode_2"],
        graph_pending_episode_uuids=["episode_2"],
    )

    public = job.to_public_dict()

    assert public["graph_episode_count"] == 2
    assert public["graph_pending_episode_count"] == 1
    assert public["graph_chunk_count"] == 2
    assert public["resumable"] is True
    assert public["resume_stage"] == "graph"
    assert "graph_episode_uuids" not in public
    assert "graph_pending_episode_uuids" not in public
    assert "graph_chunks" not in public


def test_public_job_exposes_report_resume_checkpoint(monkeypatch):
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

    public = job.to_public_dict()

    assert job.can_resume_report() is True
    assert public["resumable"] is True
    assert public["resume_stage"] == "report"


def test_completed_graph_wait_can_resume_transient_validation_failure():
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.FAILED,
        failed_stage="graph_validation",
        graph_id="graph_123",
        graph_chunks=["chunk_1"],
        graph_episode_uuids=["episode_1"],
        graph_pending_episode_uuids=[],
        graph_wait_completed=True,
    )

    assert job.can_resume_graph() is True

    job.failed_stage = "graph_validation_failed"
    assert job.can_resume_graph() is False


def test_legacy_job_deserialization_defaults_graph_checkpoint_fields():
    job = ForecastJob.from_dict({
        "job_id": "forecast_123456789abc",
        "project_id": "proj_123456789abc",
        "status": "failed",
    })

    assert job.graph_episode_uuids == []
    assert job.graph_pending_episode_uuids == []
    assert job.graph_chunks == []
    assert job.can_resume_graph() is False


def test_resume_queues_same_graph_job_without_rebuilding(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.FAILED,
        stage="failed",
        failed_stage="graph_processing",
        progress=36,
        graph_id="graph_123",
        graph_chunks=["chunk_1", "chunk_2"],
        graph_episode_uuids=["episode_1", "episode_2"],
        graph_pending_episode_uuids=["episode_2"],
    )
    ForecastJobStore.save(job)
    project = SimpleNamespace(status=module.ProjectStatus.FAILED, error="timeout")
    starts = []

    class FakeThread:
        def __init__(self, *, target, args, daemon, name):
            self.target = target
            self.args = args
            self.daemon = daemon
            self.name = name

        def start(self):
            starts.append((self.target, self.args))

    admission = SimpleNamespace(
        acquire=lambda blocking=False: True,
        release=lambda: None,
    )
    monkeypatch.setattr(ForecastService, "_threads", {})
    monkeypatch.setattr(ForecastService, "_admission", admission)
    monkeypatch.setattr(module.threading, "Thread", FakeThread)
    monkeypatch.setattr(module.ProjectManager, "get_project", lambda project_id: project)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda value: None)

    resumed = ForecastService.resume(job.job_id)

    assert resumed.job_id == job.job_id
    assert resumed.status == ForecastStatus.QUEUED
    assert resumed.graph_id == "graph_123"
    assert resumed.error is None
    assert project.status == module.ProjectStatus.GRAPH_BUILDING
    assert starts == [(ForecastService._run_job, (job.job_id, True))]


def test_resume_is_idempotent_for_running_job(isolated_jobs, monkeypatch):
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.RUNNING,
    )
    ForecastJobStore.save(job)
    acquired = []
    monkeypatch.setattr(
        ForecastService,
        "_admission",
        SimpleNamespace(acquire=lambda **kwargs: acquired.append(True)),
    )

    resumed = ForecastService.resume(job.job_id)

    assert resumed.status == ForecastStatus.RUNNING
    assert acquired == []


def test_resume_rejects_incomplete_report_checkpoint(isolated_jobs):
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.FAILED,
        failed_stage="report",
        graph_id="graph_123",
    )
    ForecastJobStore.save(job)

    with pytest.raises(ValueError, match="not resumable"):
        ForecastService.resume(job.job_id)


def test_resume_queues_report_finalization_without_graph_rerun(
    isolated_jobs, monkeypatch
):
    from app.services import forecast_service as module

    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.FAILED,
        stage="failed",
        failed_stage="report",
        progress=96,
        graph_id="graph_123",
        simulation_id="sim_123",
        report_id="report_123",
        error="table finalization failed",
    )
    ForecastJobStore.save(job)
    project = SimpleNamespace(status=module.ProjectStatus.FAILED, error=job.error)
    starts = []

    class FakeThread:
        def __init__(self, *, target, args, daemon, name):
            self.target = target
            self.args = args

        def start(self):
            starts.append((self.target, self.args))

    monkeypatch.setattr(ForecastService, "_threads", {})
    monkeypatch.setattr(
        module.ReportManager,
        "get_report",
        lambda report_id: SimpleNamespace(
            outline=SimpleNamespace(sections=[SimpleNamespace(content="Saved section")])
        ),
    )
    monkeypatch.setattr(
        module.ReportManager,
        "get_generated_sections",
        lambda report_id: [{"section_index": 1, "content": "Saved section"}],
    )
    monkeypatch.setattr(
        ForecastService,
        "_admission",
        SimpleNamespace(acquire=lambda blocking=False: True, release=lambda: None),
    )
    monkeypatch.setattr(module.threading, "Thread", FakeThread)
    monkeypatch.setattr(module.ProjectManager, "get_project", lambda project_id: project)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda value: None)

    resumed = ForecastService.resume(job.job_id)

    assert resumed.status == ForecastStatus.QUEUED
    assert resumed.stage == "report"
    assert resumed.message == "Waiting to finalize saved report"
    assert resumed.error is None
    assert resumed.failed_stage is None
    assert project.status == module.ProjectStatus.GRAPH_COMPLETED
    assert starts == [(ForecastService._run_job, (job.job_id, False, True))]


def test_resume_report_assembles_saved_sections_and_structured_table(
    isolated_jobs, monkeypatch
):
    from app.services import forecast_service as module

    options = {
        "simulation_requirement": "Forecast hotel demand",
        "report_prompt": "Verify decisions against uploaded data",
    }
    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.RUNNING,
        stage="report",
        progress=96,
        graph_id="graph_123",
        simulation_id="sim_123",
        report_id="report_123",
        options=options,
    )
    ForecastJobStore.save(job)
    project = SimpleNamespace(project_id=job.project_id)
    report = Report(
        report_id=job.report_id,
        simulation_id=job.simulation_id,
        graph_id=job.graph_id,
        simulation_requirement=options["simulation_requirement"],
        status=ReportStatus.FAILED,
        outline=ReportOutline(
            title="Hotel Demand Forecast",
            summary="Saved simulation report",
            sections=[
                ReportSection(title="Demand Outlook"),
                ReportSection(title="Commercial Actions"),
            ],
        ),
        error="No report claim could be verified",
    )
    captured = {"saved_sections": [], "saved_reports": [], "progress": []}

    class FakeReportAgent:
        def __init__(self, **kwargs):
            captured["agent_kwargs"] = kwargs
            self.mcp_tools = {
                "search_data_files": {},
                "create_structured_table": {},
            }
            self.source_verification_context = ""

        def _load_source_verification_context(self):
            return '{"source_previews":[{"source":"performance.md"}]}'

        def _generate_structured_table(self, report_content):
            captured["verification_context"] = self.source_verification_context
            captured["report_content"] = report_content
            return {
                "rows": [{
                    "claim": "Demand outlook needs source verification",
                    "evidence": "performance.md line 4",
                    "assessment": "needs_verification",
                    "confidence": 0.4,
                }],
                "markdown": "| Claim | Assessment |\n| --- | --- |\n| Demand | Needs verification |",
            }

    def save_section(report_id, section_index, section):
        captured["saved_sections"].append(
            (report_id, section_index, section.title, section.content)
        )

    def assemble_full_report(report_id, outline):
        captured["assembled_outline"] = outline
        return "# Hotel Demand Forecast\n\n## Demand Outlook\n\nSaved demand section"

    def update_progress(report_id, stage, progress, message, **kwargs):
        captured["progress"].append(
            (report_id, stage, progress, message, kwargs)
        )

    monkeypatch.setattr(module, "ReportAgent", FakeReportAgent)
    monkeypatch.setattr(module.ReportManager, "get_report", lambda report_id: report)
    monkeypatch.setattr(
        module.ReportManager,
        "get_generated_sections",
        lambda report_id: [
            {
                "section_index": 1,
                "content": "## Demand Outlook\n\nSaved demand section\n",
            },
            {
                "section_index": 2,
                "content": "## Commercial Actions\n\nSaved action section\n",
            },
        ],
    )
    monkeypatch.setattr(module.ReportManager, "save_section", save_section)
    monkeypatch.setattr(
        module.ReportManager,
        "assemble_full_report",
        assemble_full_report,
    )
    monkeypatch.setattr(
        module.ReportManager,
        "save_report",
        lambda value: captured["saved_reports"].append(value),
    )
    monkeypatch.setattr(module.ReportManager, "update_progress", update_progress)
    monkeypatch.setattr(
        ForecastService,
        "_resume_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("report resume must not rerun graph processing")
        ),
    )

    result = ForecastService._resume_report(job.job_id, project)

    assert result == {
        "project_id": job.project_id,
        "graph_id": job.graph_id,
        "simulation_id": job.simulation_id,
        "report_id": job.report_id,
        "structured_row_count": 1,
    }
    assert captured["agent_kwargs"] == {
        "graph_id": job.graph_id,
        "simulation_id": job.simulation_id,
        "simulation_requirement": options["simulation_requirement"],
        "project_id": job.project_id,
        "structured_table_required": True,
        "report_instructions": options["report_prompt"],
    }
    assert "Saved demand section" in captured["report_content"]
    assert "Saved action section" in captured["report_content"]
    assert "source_previews" in captured["verification_context"]
    assert captured["saved_sections"] == [
        (
            job.report_id,
            2,
            "Commercial Actions",
            "Saved action section\n\n| Claim | Assessment |\n"
            "| --- | --- |\n| Demand | Needs verification |",
        )
    ]
    assert report.status == ReportStatus.COMPLETED
    assert report.error is None
    assert report.structured_output["rows"][0]["assessment"] == "needs_verification"
    assert report.markdown_content.startswith("# Hotel Demand Forecast")
    assert captured["saved_reports"] == [report]
    assert captured["progress"][0][1:4] == (
        "completed",
        100,
        "Report completed from saved sections",
    )
    assert ForecastJobStore.get(job.job_id).progress == 95


def test_submit_thread_start_failure_does_not_leave_queued_job(
    isolated_jobs, monkeypatch
):
    from app.services import forecast_service as module

    project = SimpleNamespace(status=module.ProjectStatus.CREATED, error=None)
    releases = []

    class BrokenThread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            raise RuntimeError("thread unavailable")

    monkeypatch.setattr(ForecastService, "_threads", {})
    monkeypatch.setattr(
        ForecastService,
        "_admission",
        SimpleNamespace(
            acquire=lambda blocking=False: True,
            release=lambda: releases.append(True),
        ),
    )
    monkeypatch.setattr(module.threading, "Thread", BrokenThread)
    monkeypatch.setattr(module.ProjectManager, "get_project", lambda project_id: project)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda value: None)

    with pytest.raises(RuntimeError, match="thread unavailable"):
        ForecastService.submit("proj_123456789abc", ["/tmp/data.md"], {})

    jobs = ForecastJobStore.list()
    assert len(jobs) == 1
    assert jobs[0].status == ForecastStatus.FAILED
    assert jobs[0].error == "thread unavailable"
    assert ForecastService._threads == {}
    assert project.status == module.ProjectStatus.FAILED
    assert releases == [True]


def test_restart_recovery_preserves_resumable_graph_checkpoint(
    isolated_jobs, monkeypatch
):
    from app.services import forecast_service as module

    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.QUEUED,
        stage="graph_processing",
        graph_id="graph_123",
        graph_chunks=["chunk_1", "chunk_2"],
        graph_episode_uuids=["episode_1", "episode_2"],
        graph_pending_episode_uuids=["episode_2"],
    )
    ForecastJobStore.save(job)
    project = SimpleNamespace(status=module.ProjectStatus.GRAPH_BUILDING, error=None)
    monkeypatch.setattr(ForecastService, "_terminate_orphan_process", lambda value: True)
    monkeypatch.setattr(module.ProjectManager, "get_project", lambda project_id: project)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda value: None)

    ForecastService.recover_interrupted_jobs()

    recovered = ForecastJobStore.get(job.job_id)
    assert recovered.status == ForecastStatus.FAILED
    assert recovered.failed_stage == "graph_processing"
    assert recovered.can_resume_graph() is True
    assert project.status == module.ProjectStatus.FAILED


def test_recovery_marks_dead_worker_failed_when_birth_lookup_is_empty(
    isolated_jobs, monkeypatch
):
    from app.services import forecast_service as module

    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.RUNNING,
        stage="ontology",
        worker_pid=99999,
        worker_start_token="old-token",
    )
    ForecastJobStore.save(job)
    project = SimpleNamespace(status=module.ProjectStatus.ONTOLOGY_GENERATED, error=None)
    monkeypatch.setattr(module, "_process_start_token", lambda pid: None)
    monkeypatch.setattr(module, "_process_is_alive", lambda pid: False)
    monkeypatch.setattr(ForecastService, "_terminate_orphan_process", lambda value: True)
    monkeypatch.setattr(module.ProjectManager, "get_project", lambda project_id: project)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda value: None)

    ForecastService.recover_interrupted_jobs()

    recovered = ForecastJobStore.get(job.job_id)
    assert recovered.status == ForecastStatus.FAILED
    assert recovered.failed_stage == "ontology"
    assert project.status == module.ProjectStatus.FAILED


def test_resume_graph_reuses_checkpointed_graph(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.RUNNING,
        graph_id="graph_existing",
        graph_chunks=["chunk_1", "chunk_2"],
        graph_episode_uuids=["episode_1", "episode_2"],
        graph_pending_episode_uuids=["episode_2"],
    )
    ForecastJobStore.save(job)
    project = SimpleNamespace(status=module.ProjectStatus.GRAPH_BUILDING, error="timeout")
    waited = []

    class ExistingGraphBuilder:
        def __init__(self, api_key):
            self.api_key = api_key

        def create_graph(self, name):
            raise AssertionError("resume must not create a graph")

        def add_text_batches(self, *args, **kwargs):
            raise AssertionError("resume must not add episodes")

        def _get_graph_info(self, graph_id):
            assert graph_id == "graph_existing"
            return SimpleNamespace(
                node_count=3,
                edge_count=2,
                entity_types=["HotelProperty"],
            )

    monkeypatch.setattr(module, "GraphBuilderService", ExistingGraphBuilder)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda value: None)
    monkeypatch.setattr(
        ForecastService,
        "_wait_for_episodes",
        lambda *args, **kwargs: waited.append((args, kwargs)),
    )
    monkeypatch.setattr(Config, "ZEP_API_KEY", "test-zep-key")

    graph_id = ForecastService._resume_graph(job.job_id, project)

    assert graph_id == "graph_existing"
    assert waited[0][0][2] == ["episode_2"]
    assert waited[0][1]["total_episode_count"] == 2
    assert project.status == module.ProjectStatus.GRAPH_COMPLETED
    assert ForecastJobStore.get(job.job_id).progress == 40


def test_graph_upload_persists_partial_episode_checkpoint(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(job_id="forecast_123456789abc", project_id="proj_123456789abc")
    ForecastJobStore.save(job)
    project = SimpleNamespace(
        project_id=job.project_id,
        name="Hotel data",
        status=module.ProjectStatus.ONTOLOGY_GENERATED,
        ontology={"entity_types": [{"name": "HotelProperty"}]},
        chunk_size=2000,
        chunk_overlap=100,
    )
    chunks = ["chunk_1", "chunk_2", "chunk_3", "chunk_4"]

    class InterruptedGraphBuilder:
        def __init__(self, api_key):
            pass

        def create_graph(self, name):
            return "graph_partial"

        def set_ontology(self, graph_id, ontology):
            pass

        def add_text_batches(self, *args, **kwargs):
            kwargs["checkpoint_callback"](["episode_1", "episode_2", "episode_3"])
            raise ConnectionError("second batch failed")

    monkeypatch.setattr(module, "GraphBuilderService", InterruptedGraphBuilder)
    monkeypatch.setattr(module.TextProcessor, "split_text", lambda *args: chunks)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda value: None)
    monkeypatch.setattr(Config, "ZEP_API_KEY", "test-zep-key")

    with pytest.raises(ConnectionError, match="second batch failed"):
        ForecastService._build_graph(
            job.job_id,
            project,
            "hotel data",
            {"chunk_size": 2000, "chunk_overlap": 100, "graph_name": "Graph"},
        )

    persisted = ForecastJobStore.get(job.job_id)
    assert persisted.graph_id == "graph_partial"
    assert persisted.graph_chunks == chunks
    assert persisted.graph_episode_uuids == ["episode_1", "episode_2", "episode_3"]
    assert persisted.graph_pending_episode_uuids == persisted.graph_episode_uuids


def test_resume_graph_uploads_only_missing_chunks(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(
        job_id="forecast_123456789abc",
        project_id="proj_123456789abc",
        status=ForecastStatus.RUNNING,
        graph_id="graph_existing",
        graph_chunks=["chunk_1", "chunk_2", "chunk_3"],
        graph_episode_uuids=["episode_1"],
        graph_pending_episode_uuids=["episode_1"],
    )
    ForecastJobStore.save(job)
    project = SimpleNamespace(status=module.ProjectStatus.GRAPH_BUILDING, error=None)
    uploaded = []
    waited = []

    class PartialGraphBuilder:
        def __init__(self, api_key):
            pass

        def add_text_batches(self, graph_id, chunks, **kwargs):
            uploaded.extend(chunks)
            kwargs["checkpoint_callback"](["episode_2", "episode_3"])
            return ["episode_2", "episode_3"]

        def _get_graph_info(self, graph_id):
            return SimpleNamespace(
                node_count=3,
                edge_count=2,
                entity_types=["HotelProperty"],
            )

    monkeypatch.setattr(module, "GraphBuilderService", PartialGraphBuilder)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda value: None)
    monkeypatch.setattr(
        ForecastService,
        "_wait_for_episodes",
        lambda *args, **kwargs: waited.append((args, kwargs)),
    )
    monkeypatch.setattr(Config, "ZEP_API_KEY", "test-zep-key")

    graph_id = ForecastService._resume_graph(job.job_id, project)

    assert graph_id == "graph_existing"
    assert uploaded == ["chunk_2", "chunk_3"]
    assert waited[0][0][2] == ["episode_1", "episode_2", "episode_3"]
    persisted = ForecastJobStore.get(job.job_id)
    assert persisted.graph_episode_uuids == ["episode_1", "episode_2", "episode_3"]


def test_forecast_api_submits_complete_pipeline(monkeypatch):
    project = SimpleNamespace(
        project_id="proj_123456789abc",
        files=[],
        simulation_requirement=None,
    )
    submitted = {}

    monkeypatch.setattr(
        "app.api.forecast.ProjectManager.create_project",
        lambda name: project,
    )
    monkeypatch.setattr(
        "app.api.forecast.ProjectManager.save_file_to_project",
        lambda project_id, file, filename: {
            "original_filename": filename,
            "saved_filename": "stored.md",
            "size": 12,
            "path": f"/tmp/{filename}",
        },
    )
    monkeypatch.setattr("app.api.forecast.ProjectManager.save_project", lambda value: None)

    def fake_submit(project_id, file_paths, options):
        submitted.update({
            "project_id": project_id,
            "file_paths": file_paths,
            "options": options,
        })
        return ForecastJob(
            job_id="forecast_abcdef123456",
            project_id=project_id,
        )

    monkeypatch.setattr("app.api.forecast.ForecastService.submit", fake_submit)
    client = create_app().test_client()
    response = client.post(
        "/api/forecast",
        data={"files": (BytesIO(b"forecast evidence"), "evidence.md")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 202
    payload = response.get_json()["data"]
    assert payload["job_id"] == "forecast_abcdef123456"
    assert submitted["project_id"] == project.project_id
    assert submitted["options"]["report_prompt"] == Config.FORECAST_DEFAULT_REPORT_PROMPT
    assert submitted["options"]["max_rounds"] == Config.FORECAST_DEFAULT_MAX_ROUNDS
    assert submitted["options"]["chunk_size"] == Config.FORECAST_DEFAULT_CHUNK_SIZE
    assert submitted["options"]["chunk_overlap"] == Config.FORECAST_DEFAULT_CHUNK_OVERLAP
    assert submitted["options"]["output_locale"] == "zh"


def test_nonempty_graph_without_typed_entities_is_rejected(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(job_id="forecast_123456789abc", project_id="proj_123456789abc")
    ForecastJobStore.save(job)
    project = SimpleNamespace(
        project_id=job.project_id,
        name="Property metadata only",
        status=module.ProjectStatus.ONTOLOGY_GENERATED,
        ontology={"entity_types": [{"name": "HotelProperty"}]},
        chunk_size=500,
        chunk_overlap=50,
    )

    class UntypedGraphBuilder:
        def __init__(self, api_key):
            self.api_key = api_key

        def create_graph(self, name):
            return "graph_untyped"

        def set_ontology(self, graph_id, ontology):
            return None

        def add_text_batches(
            self,
            graph_id,
            chunks,
            batch_size,
            progress_callback,
            checkpoint_callback=None,
        ):
            if checkpoint_callback:
                checkpoint_callback(["episode_1"])
            return ["episode_1"]

        def _get_graph_info(self, graph_id):
            return SimpleNamespace(node_count=15, edge_count=16, entity_types=[])

    monkeypatch.setattr(module, "GraphBuilderService", UntypedGraphBuilder)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda project: None)
    monkeypatch.setattr(module.TextProcessor, "split_text", lambda *args: ["chunk"])
    monkeypatch.setattr(
        ForecastService,
        "_wait_for_episodes",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(Config, "ZEP_API_KEY", "test-zep-key")

    with pytest.raises(RuntimeError) as exc_info:
        ForecastService._build_graph(
            job.job_id,
            project,
            "property metadata",
            {"chunk_size": 500, "chunk_overlap": 50, "graph_name": "Graph"},
        )

    persisted = ForecastJobStore.get(job.job_id)
    assert "Zep extracted 15 entities and 16 relationships" in str(exc_info.value)
    assert "classified 0 entities" in str(exc_info.value)
    assert "include daily reservation/performance data" in str(exc_info.value)
    assert persisted.graph_id == "graph_untyped"
    assert project.status == module.ProjectStatus.GRAPH_BUILDING


def test_typed_graph_completes_and_persists_graph_stage(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(job_id="forecast_123456789abc", project_id="proj_123456789abc")
    ForecastJobStore.save(job)
    project = SimpleNamespace(
        project_id=job.project_id,
        name="Combined hotel evidence",
        status=module.ProjectStatus.ONTOLOGY_GENERATED,
        ontology={"entity_types": [{"name": "HotelProperty"}]},
        chunk_size=500,
        chunk_overlap=50,
    )

    class TypedGraphBuilder:
        def __init__(self, api_key):
            self.api_key = api_key

        def create_graph(self, name):
            return "graph_typed"

        def set_ontology(self, graph_id, ontology):
            return None

        def add_text_batches(
            self,
            graph_id,
            chunks,
            batch_size,
            progress_callback,
            checkpoint_callback=None,
        ):
            if checkpoint_callback:
                checkpoint_callback(["episode_1"])
            return ["episode_1"]

        def _get_graph_info(self, graph_id):
            return SimpleNamespace(
                node_count=3,
                edge_count=2,
                entity_types=["HotelProperty"],
            )

    monkeypatch.setattr(module, "GraphBuilderService", TypedGraphBuilder)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda project: None)
    monkeypatch.setattr(module.TextProcessor, "split_text", lambda *args: ["chunk"])
    monkeypatch.setattr(
        ForecastService,
        "_wait_for_episodes",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(Config, "ZEP_API_KEY", "test-zep-key")

    graph_id = ForecastService._build_graph(
        job.job_id,
        project,
        "combined hotel evidence",
        {"chunk_size": 500, "chunk_overlap": 50, "graph_name": "Graph"},
    )

    persisted = ForecastJobStore.get(job.job_id)
    assert graph_id == "graph_typed"
    assert project.status == module.ProjectStatus.GRAPH_COMPLETED
    assert persisted.graph_id == graph_id
    assert persisted.stage == "graph"
    assert persisted.progress == 40
    assert persisted.message == "Knowledge graph completed"


def test_worker_persists_typed_entity_failure(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(job_id="forecast_123456789abc", project_id="proj_123456789abc")
    ForecastJobStore.save(job)
    project = SimpleNamespace(status=module.ProjectStatus.GRAPH_BUILDING, error=None)
    released = []
    failure = (
        "Zep extracted 15 entities and 16 relationships, but classified 0 entities "
        "with the generated ontology."
    )

    monkeypatch.setattr(ForecastService, "_semaphore", nullcontext())
    monkeypatch.setattr(
        ForecastService,
        "_admission",
        SimpleNamespace(release=lambda: released.append(True)),
    )
    monkeypatch.setattr(
        ForecastService,
        "_execute_pipeline",
        lambda job_id: (_ for _ in ()).throw(RuntimeError(failure)),
    )
    monkeypatch.setattr(module.ProjectManager, "get_project", lambda project_id: project)
    monkeypatch.setattr(module.ProjectManager, "save_project", lambda project: None)

    ForecastService._run_job(job.job_id)

    persisted = ForecastJobStore.get(job.job_id)
    assert persisted.status == ForecastStatus.FAILED
    assert persisted.stage == "failed"
    assert persisted.error == failure
    assert persisted.completed_at is not None
    assert project.status == module.ProjectStatus.FAILED
    assert project.error == persisted.error
    assert released == [True]


def test_pipeline_wires_simulation_mcp_and_report(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    options = {
        "simulation_requirement": "Forecast this event",
        "report_prompt": "Use both local MCP tools",
        "additional_context": "",
        "graph_name": "Graph",
        "chunk_size": 500,
        "chunk_overlap": 50,
        "enable_twitter": True,
        "enable_reddit": True,
        "use_llm_for_profiles": True,
        "parallel_profile_count": 2,
        "max_rounds": 3,
        "max_active_agents": 2,
        "enable_graph_memory_update": False,
        "simulation_timeout_seconds": 60,
    }
    job = ForecastJob(
        job_id="forecast_feedface1234",
        project_id="proj_123456789abc",
        options=options,
        file_paths=["/tmp/evidence.md"],
    )
    ForecastJobStore.save(job)

    project = SimpleNamespace(
        project_id=job.project_id,
        name="Project",
        ontology={"entity_types": [{"name": "Person"}]},
    )
    simulation_state = SimpleNamespace(
        simulation_id="sim_123456789abc",
        status=SimulationStatus.READY,
        config_generated=True,
        profiles_count=2,
        error=None,
    )
    simulation_manager = SimpleNamespace(
        create_simulation=lambda **kwargs: simulation_state,
        prepare_simulation=lambda **kwargs: simulation_state,
        _save_simulation_state=lambda state: None,
        get_simulation=lambda simulation_id: simulation_state,
    )
    captured = {}

    class FakeReportAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.mcp_tools = {
                "search_data_files": {},
                "create_structured_table": {},
            }

        def generate_report(self, progress_callback, report_id):
            return SimpleNamespace(
                report_id=report_id,
                status=ReportStatus.COMPLETED,
                structured_output={"rows": [{"claim": "x"}]},
                error=None,
            )

    monkeypatch.setattr(module.ProjectManager, "get_project", lambda project_id: project)
    monkeypatch.setattr(module.ProjectManager, "get_extracted_text", lambda project_id: "text")
    monkeypatch.setattr(ForecastService, "_ingest_and_generate_ontology", lambda *args: None)
    monkeypatch.setattr(ForecastService, "_build_graph", lambda *args: "graph_123")
    monkeypatch.setattr(module, "SimulationManager", lambda: simulation_manager)
    monkeypatch.setattr(
        module.SimulationRunner,
        "start_simulation",
        lambda **kwargs: SimpleNamespace(total_rounds=3, process_pid=12345),
    )
    monkeypatch.setattr(ForecastService, "_wait_for_simulation", lambda *args: None)
    monkeypatch.setattr(ForecastService, "_close_simulation", lambda *args: None)
    monkeypatch.setattr(module, "ReportAgent", FakeReportAgent)

    result = ForecastService._execute_pipeline(job.job_id)

    assert result["report_id"].startswith("report_")
    assert result["structured_row_count"] == 1
    assert captured["project_id"] == project.project_id
    assert captured["structured_table_required"] is True
    assert captured["report_instructions"] == options["report_prompt"]


def test_simulation_requires_every_enabled_platform(monkeypatch):
    from app.services import forecast_service as module

    state = SimpleNamespace(
        runner_status=module.RunnerStatus.COMPLETED,
        twitter_completed=True,
        twitter_current_round=3,
        reddit_completed=False,
        reddit_current_round=2,
        current_round=3,
        error=None,
    )
    monkeypatch.setattr(module.SimulationRunner, "get_run_state", lambda simulation_id: state)

    with pytest.raises(RuntimeError, match="Reddit"):
        ForecastService._wait_for_simulation(
            "forecast_missing",
            "sim_123",
            3,
            {
                "enable_twitter": True,
                "enable_reddit": True,
                "simulation_timeout_seconds": 60,
            },
        )


def test_completed_simulation_cleanup_force_terminates(monkeypatch):
    from app.services import forecast_service as module

    process = SimpleNamespace(poll=lambda: None)
    monotonic_values = iter([0, 16])
    terminated = []
    monkeypatch.setattr(module.SimulationRunner, "check_env_alive", lambda simulation_id: True)
    monkeypatch.setattr(module.SimulationRunner, "close_simulation_env", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.SimulationRunner, "_processes", {"sim_123": process})
    monkeypatch.setattr(
        module.SimulationRunner,
        "_terminate_process",
        lambda process, simulation_id, timeout: terminated.append(simulation_id),
    )
    monkeypatch.setattr(module.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(module.ZepGraphMemoryManager, "stop_updater", lambda simulation_id: None)

    ForecastService._close_simulation("sim_123")

    assert terminated == ["sim_123"]


def test_orphan_cleanup_refuses_reused_pid(monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(
        job_id="forecast_deadbeef1234",
        project_id="proj_123456789abc",
        simulation_id="sim_expected",
        simulation_pid=4242,
    )
    monkeypatch.setattr(module.os, "kill", lambda pid, signal: None)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="python unrelated.py", returncode=0),
    )

    assert ForecastService._terminate_orphan_process(job) is False


def test_recovery_retries_when_orphan_cannot_be_stopped(isolated_jobs, monkeypatch):
    job = ForecastJob(
        job_id="forecast_cafebabe1234",
        project_id="proj_123456789abc",
        status=ForecastStatus.RUNNING,
        simulation_id="sim_expected",
        simulation_pid=4242,
    )
    ForecastJobStore.save(job)
    monkeypatch.setattr(ForecastService, "_terminate_orphan_process", lambda job: False)

    ForecastService.recover_interrupted_jobs()

    recovered = ForecastJobStore.get(job.job_id)
    assert recovered.status == ForecastStatus.RUNNING
    assert "orphan" in recovered.message


def test_orphan_pid_recovers_from_run_state(tmp_path, monkeypatch):
    from app.services import forecast_service as module

    simulation_dir = tmp_path / "sim_expected"
    simulation_dir.mkdir()
    (simulation_dir / "run_state.json").write_text(
        '{"process_pid": 4242}',
        encoding="utf-8",
    )
    monkeypatch.setattr(module.SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    job = ForecastJob(
        job_id="forecast_112233445566",
        project_id="proj_123456789abc",
        simulation_id="sim_expected",
    )

    assert ForecastService._resolve_simulation_pid(job) == 4242


def test_recovery_never_kills_current_process_when_birth_lookup_fails(isolated_jobs, monkeypatch):
    from app.services import forecast_service as module

    job = ForecastJob(
        job_id="forecast_778899aabbcc",
        project_id="proj_123456789abc",
        status=ForecastStatus.RUNNING,
        worker_pid=module.os.getpid(),
        worker_instance_id=ForecastService._process_instance_id,
        worker_start_token="token",
    )
    ForecastJobStore.save(job)
    terminated = []
    monkeypatch.setattr(module, "_process_start_token", lambda pid: None)
    monkeypatch.setattr(
        ForecastService,
        "_terminate_orphan_process",
        lambda job: terminated.append(job.job_id) or True,
    )

    ForecastService.recover_interrupted_jobs()

    assert terminated == []
    assert ForecastJobStore.get(job.job_id).status == ForecastStatus.RUNNING
