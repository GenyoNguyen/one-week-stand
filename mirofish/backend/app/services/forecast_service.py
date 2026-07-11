"""Backend-only orchestration for the complete MiroFish forecast pipeline."""

import json
import os
import re
import signal
import subprocess
import threading
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import Config
from ..models.project import ProjectManager, ProjectStatus
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from .graph_builder import GraphBuilderService
from .ontology_generator import OntologyGenerator
from .report_agent import ReportAgent, ReportManager, ReportStatus
from .simulation_manager import SimulationManager, SimulationStatus
from .simulation_runner import RunnerStatus, SimulationRunner
from .text_processor import TextProcessor
from .zep_graph_memory_updater import ZepGraphMemoryManager


logger = get_logger("mirofish.forecast_service")


class ForecastQueueFullError(ValueError):
    """Raised when the bounded forecast worker queue has no capacity."""


class GraphNotUsableError(RuntimeError):
    """Raised when a completed graph cannot provide simulation entities."""


def _process_start_token(pid: int) -> Optional[str]:
    """Return an OS process birth marker, preventing PID-reuse mistakes."""
    try:
        if os.name == "nt":
            return subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    f'(Get-CimInstance Win32_Process -Filter "ProcessId = {pid}").CreationDate',
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout.strip() or None
        return subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout.strip() or None
    except Exception:
        return None


def _process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


class ForecastStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ForecastJob:
    job_id: str
    project_id: str
    status: ForecastStatus = ForecastStatus.QUEUED
    stage: str = "queued"
    progress: int = 0
    message: str = "Forecast queued"
    graph_id: Optional[str] = None
    graph_chunks: List[str] = field(default_factory=list)
    graph_episode_uuids: List[str] = field(default_factory=list)
    graph_pending_episode_uuids: List[str] = field(default_factory=list)
    graph_wait_completed: bool = False
    simulation_id: Optional[str] = None
    report_id: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    options: Dict[str, Any] = field(default_factory=dict)
    file_paths: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    worker_pid: Optional[int] = None
    worker_instance_id: Optional[str] = None
    worker_start_token: Optional[str] = None
    simulation_pid: Optional[int] = None
    failed_stage: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    def to_public_dict(self) -> Dict[str, Any]:
        data = self.to_dict()
        data["graph_episode_count"] = len(self.graph_episode_uuids)
        data["graph_pending_episode_count"] = len(self.graph_pending_episode_uuids)
        data["graph_chunk_count"] = len(self.graph_chunks)
        graph_resumable = self.can_resume_graph()
        report_resumable = self.can_resume_report()
        data["resumable"] = graph_resumable or report_resumable
        data["resume_stage"] = (
            "graph" if graph_resumable else "report" if report_resumable else None
        )
        data.pop("file_paths", None)
        data.pop("options", None)
        data.pop("graph_episode_uuids", None)
        data.pop("graph_pending_episode_uuids", None)
        data.pop("graph_chunks", None)
        data.pop("worker_pid", None)
        data.pop("worker_instance_id", None)
        data.pop("worker_start_token", None)
        data.pop("simulation_pid", None)
        return data

    def can_resume_graph(self) -> bool:
        graph_checkpoint_ready = bool(
            self.graph_chunks
            and (
                self.graph_pending_episode_uuids
                or self.graph_wait_completed
                or len(self.graph_episode_uuids) < len(self.graph_chunks)
            )
        )
        return bool(
            self.status == ForecastStatus.FAILED
            and self.failed_stage in {"graph", "graph_processing", "graph_validation"}
            and self.graph_id
            and self.graph_episode_uuids
            and graph_checkpoint_ready
            and not self.simulation_id
        )

    def can_resume_report(self) -> bool:
        checkpoint_ids_ready = bool(
            self.status == ForecastStatus.FAILED
            and self.failed_stage == "report"
            and self.graph_id
            and self.simulation_id
            and self.report_id
        )
        if not checkpoint_ids_ready:
            return False
        try:
            report = ReportManager.get_report(self.report_id)
            if not report or not report.outline or not report.outline.sections:
                return False
            saved_sections = {
                item["section_index"]
                for item in ReportManager.get_generated_sections(self.report_id)
                if item.get("content", "").strip()
            }
            return all(
                section.content.strip() or index in saved_sections
                for index, section in enumerate(report.outline.sections, start=1)
            )
        except Exception:
            return False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastJob":
        data = dict(data)
        data["status"] = ForecastStatus(data.get("status", ForecastStatus.QUEUED.value))
        return cls(**data)


class ForecastJobStore:
    JOBS_DIR = Path(Config.UPLOAD_FOLDER) / "forecasts"
    _lock = threading.RLock()

    @classmethod
    def _path(cls, job_id: str) -> Path:
        if not job_id.startswith("forecast_") or not job_id[9:].isalnum():
            raise ValueError("Invalid forecast job ID")
        return cls.JOBS_DIR / f"{job_id}.json"

    @classmethod
    def save(cls, job: ForecastJob) -> None:
        with cls._lock:
            cls.JOBS_DIR.mkdir(parents=True, exist_ok=True)
            job.updated_at = datetime.now().isoformat()
            path = cls._path(job.job_id)
            temp_path = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
            with temp_path.open("w", encoding="utf-8") as job_file:
                json.dump(job.to_dict(), job_file, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)

    @classmethod
    def get(cls, job_id: str) -> Optional[ForecastJob]:
        with cls._lock:
            path = cls._path(job_id)
            if not path.exists():
                return None
            with path.open("r", encoding="utf-8") as job_file:
                return ForecastJob.from_dict(json.load(job_file))

    @classmethod
    def update(cls, job_id: str, **changes: Any) -> ForecastJob:
        with cls._lock:
            job = cls.get(job_id)
            if not job:
                raise ValueError(f"Forecast job not found: {job_id}")
            for key, value in changes.items():
                if key == "status" and isinstance(value, str):
                    value = ForecastStatus(value)
                setattr(job, key, value)
            cls.save(job)
            return job

    @classmethod
    def list(cls, limit: int = 50) -> List[ForecastJob]:
        with cls._lock:
            if not cls.JOBS_DIR.exists():
                return []
            jobs = []
            for path in cls.JOBS_DIR.glob("forecast_*.json"):
                try:
                    with path.open("r", encoding="utf-8") as job_file:
                        jobs.append(ForecastJob.from_dict(json.load(job_file)))
                except Exception as exc:
                    logger.warning(f"Skipping unreadable forecast job {path.name}: {exc}")
            jobs.sort(key=lambda job: job.created_at, reverse=True)
            return jobs[:max(1, min(limit, 200))]


class ForecastService:
    """Run all MiroFish stages in one backend worker thread."""

    _semaphore = threading.BoundedSemaphore(max(1, Config.FORECAST_MAX_CONCURRENT_JOBS))
    _admission = threading.BoundedSemaphore(
        max(1, Config.FORECAST_MAX_CONCURRENT_JOBS + Config.FORECAST_MAX_QUEUED_JOBS)
    )
    _threads: Dict[str, threading.Thread] = {}
    _threads_lock = threading.Lock()
    _process_instance_id = uuid.uuid4().hex
    _process_start_token = _process_start_token(os.getpid())

    @classmethod
    def submit(
        cls,
        project_id: str,
        file_paths: List[str],
        options: Dict[str, Any],
    ) -> ForecastJob:
        capacity = max(1, Config.FORECAST_MAX_CONCURRENT_JOBS + Config.FORECAST_MAX_QUEUED_JOBS)
        with cls._threads_lock:
            persisted_inflight = sum(
                job.status in (ForecastStatus.QUEUED, ForecastStatus.RUNNING)
                for job in ForecastJobStore.list(limit=200)
            )
            if persisted_inflight >= capacity or not cls._admission.acquire(blocking=False):
                raise ForecastQueueFullError("Forecast queue is full; retry later")
        job = ForecastJob(
            job_id=f"forecast_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            options=options,
            file_paths=file_paths,
            worker_pid=os.getpid(),
            worker_instance_id=cls._process_instance_id,
            worker_start_token=cls._process_start_token,
        )
        try:
            ForecastJobStore.save(job)
            thread = threading.Thread(
                target=cls._run_job,
                args=(job.job_id,),
                daemon=True,
                name=f"Forecast-{job.job_id[-6:]}",
            )
            with cls._threads_lock:
                cls._threads[job.job_id] = thread
            thread.start()
            return job
        except Exception as exc:
            with cls._threads_lock:
                cls._threads.pop(job.job_id, None)
            persisted = ForecastJobStore.get(job.job_id)
            if persisted:
                ForecastJobStore.update(
                    job.job_id,
                    status=ForecastStatus.FAILED,
                    stage="failed",
                    failed_stage=persisted.stage,
                    message="Forecast worker could not start",
                    error=str(exc),
                    completed_at=datetime.now().isoformat(),
                )
                project = ProjectManager.get_project(job.project_id)
                if project:
                    project.status = ProjectStatus.FAILED
                    project.error = str(exc)
                    ProjectManager.save_project(project)
            cls._admission.release()
            raise

    @classmethod
    def resume(cls, job_id: str) -> ForecastJob:
        """Resume a checkpointed graph wait or finalize already-generated report sections."""
        with cls._threads_lock:
            job = ForecastJobStore.get(job_id)
            if not job:
                raise ValueError(f"Forecast job not found: {job_id}")
            if job.status in (ForecastStatus.QUEUED, ForecastStatus.RUNNING):
                return job
            resume_graph = job.can_resume_graph()
            resume_report = job.can_resume_report()
            if not resume_graph and not resume_report:
                raise ValueError(
                    "Forecast job is not resumable. A persisted graph checkpoint or "
                    "completed report sections are required."
                )

            capacity = max(
                1,
                Config.FORECAST_MAX_CONCURRENT_JOBS + Config.FORECAST_MAX_QUEUED_JOBS,
            )
            persisted_inflight = sum(
                candidate.status in (ForecastStatus.QUEUED, ForecastStatus.RUNNING)
                for candidate in ForecastJobStore.list(limit=200)
            )
            if persisted_inflight >= capacity or not cls._admission.acquire(blocking=False):
                raise ForecastQueueFullError("Forecast queue is full; retry later")

            try:
                project = ProjectManager.get_project(job.project_id)
                if not project:
                    raise ValueError(f"Project not found: {job.project_id}")
                project.status = (
                    ProjectStatus.GRAPH_BUILDING
                    if resume_graph
                    else ProjectStatus.GRAPH_COMPLETED
                )
                project.error = None
                ProjectManager.save_project(project)
                job = ForecastJobStore.update(
                    job_id,
                    status=ForecastStatus.QUEUED,
                    stage="graph_processing" if resume_graph else "report",
                    message=(
                        "Waiting to resume graph processing"
                        if resume_graph
                        else "Waiting to finalize saved report"
                    ),
                    error=None,
                    completed_at=None,
                    failed_stage=None,
                    worker_pid=os.getpid(),
                    worker_instance_id=cls._process_instance_id,
                    worker_start_token=cls._process_start_token,
                )
                thread = threading.Thread(
                    target=cls._run_job,
                    args=(job_id, True) if resume_graph else (job_id, False, True),
                    daemon=True,
                    name=f"Forecast-{job_id[-6:]}-resume",
                )
                cls._threads[job_id] = thread
                thread.start()
                return job
            except Exception as exc:
                cls._threads.pop(job_id, None)
                ForecastJobStore.update(
                    job_id,
                    status=ForecastStatus.FAILED,
                    stage="failed",
                    failed_stage="graph_processing" if resume_graph else "report",
                    message="Forecast resume could not start",
                    error=str(exc),
                    completed_at=datetime.now().isoformat(),
                )
                project = ProjectManager.get_project(job.project_id)
                if project:
                    project.status = ProjectStatus.FAILED
                    project.error = str(exc)
                    ProjectManager.save_project(project)
                cls._admission.release()
                raise

    @classmethod
    def recover_interrupted_jobs(cls) -> None:
        for job in ForecastJobStore.list(limit=200):
            if job.status not in (ForecastStatus.QUEUED, ForecastStatus.RUNNING):
                continue
            if (
                job.worker_instance_id == cls._process_instance_id
                and job.worker_pid == os.getpid()
            ):
                continue
            observed_start_token = (
                _process_start_token(job.worker_pid)
                if job.worker_pid and job.worker_start_token
                else None
            )
            if job.worker_pid and job.worker_start_token and observed_start_token is None:
                if _process_is_alive(job.worker_pid):
                    ForecastJobStore.update(
                        job.job_id,
                        message="Worker identity check unavailable; recovery will retry",
                    )
                    continue
            worker_alive = bool(
                observed_start_token
                and observed_start_token == job.worker_start_token
            )
            if worker_alive:
                continue
            if not cls._terminate_orphan_process(job):
                ForecastJobStore.update(
                    job.job_id,
                    message="Worker stopped; waiting to terminate orphan simulation process",
                )
                continue
            ForecastJobStore.update(
                job.job_id,
                status=ForecastStatus.FAILED,
                stage="failed",
                failed_stage=job.stage,
                message="Forecast interrupted by backend restart",
                error="Backend process stopped before forecast completion",
                completed_at=datetime.now().isoformat(),
            )
            project = ProjectManager.get_project(job.project_id)
            if project:
                project.status = ProjectStatus.FAILED
                project.error = "Backend process stopped before forecast completion"
                ProjectManager.save_project(project)

    @classmethod
    def get_job(cls, job_id: str) -> Optional[ForecastJob]:
        return ForecastJobStore.get(job_id)

    @classmethod
    def get_latest_completed_job(cls) -> Optional[ForecastJob]:
        return next(
            (
                job
                for job in ForecastJobStore.list(limit=200)
                if job.status == ForecastStatus.COMPLETED and job.report_id
            ),
            None,
        )

    @classmethod
    def get_result(cls, job_id: str) -> Optional[Dict[str, Any]]:
        job = ForecastJobStore.get(job_id)
        if not job or job.status != ForecastStatus.COMPLETED or not job.report_id:
            return None
        report = ReportManager.get_report(job.report_id)
        if not report:
            raise RuntimeError(f"Completed forecast report is missing: {job.report_id}")
        return {
            "job": job.to_public_dict(),
            "report": report.to_dict(),
        }

    @classmethod
    def _set_stage(
        cls,
        job_id: str,
        stage: str,
        progress: int,
        message: str,
        **changes: Any,
    ) -> ForecastJob:
        return ForecastJobStore.update(
            job_id,
            stage=stage,
            progress=max(0, min(int(progress), 100)),
            message=message,
            **changes,
        )

    @classmethod
    def _run_job(
        cls,
        job_id: str,
        resume_graph: bool = False,
        resume_report: bool = False,
    ) -> None:
        try:
            job = ForecastJobStore.get(job_id)
            queued_progress = job.progress if (resume_graph or resume_report) and job else 0
            queued_message = (
                "Waiting to resume graph processing" if resume_graph else
                "Waiting to finalize saved report" if resume_report else
                "Waiting for forecast worker"
            )
            queued_stage = (
                "graph_processing" if resume_graph else "report" if resume_report else "queued"
            )
            cls._set_stage(job_id, queued_stage, queued_progress, queued_message)
            with cls._semaphore:
                ForecastJobStore.update(job_id, status=ForecastStatus.RUNNING)
                if resume_report:
                    result = cls._execute_pipeline(job_id, resume_report=True)
                elif resume_graph:
                    result = cls._execute_pipeline(job_id, resume_graph=True)
                else:
                    result = cls._execute_pipeline(job_id)
                ForecastJobStore.update(
                    job_id,
                    status=ForecastStatus.COMPLETED,
                    stage="completed",
                    progress=100,
                    message="Forecast completed",
                    result=result,
                    failed_stage=None,
                    completed_at=datetime.now().isoformat(),
                )
        except Exception as exc:
            logger.error(f"Forecast {job_id} failed: {exc}\n{traceback.format_exc()}")
            try:
                current_job = ForecastJobStore.get(job_id)
                failed_stage = (
                    current_job.stage
                    if current_job and current_job.stage != "failed"
                    else current_job.failed_stage if current_job else None
                )
                if isinstance(exc, GraphNotUsableError):
                    failed_stage = "graph_validation_failed"
                ForecastJobStore.update(
                    job_id,
                    status=ForecastStatus.FAILED,
                    stage="failed",
                    failed_stage=failed_stage,
                    message="Forecast failed",
                    error=str(exc),
                    completed_at=datetime.now().isoformat(),
                )
                job = ForecastJobStore.get(job_id)
                if job:
                    project = ProjectManager.get_project(job.project_id)
                    if project:
                        project.status = ProjectStatus.FAILED
                        project.error = str(exc)
                        ProjectManager.save_project(project)
            except Exception:
                logger.error(f"Could not persist forecast failure for {job_id}")
        finally:
            with cls._threads_lock:
                cls._threads.pop(job_id, None)
            cls._admission.release()

    @classmethod
    def _execute_pipeline(
        cls,
        job_id: str,
        resume_graph: bool = False,
        resume_report: bool = False,
    ) -> Dict[str, Any]:
        job = ForecastJobStore.get(job_id)
        if not job:
            raise ValueError(f"Forecast job not found: {job_id}")
        options = job.options
        project = ProjectManager.get_project(job.project_id)
        if not project:
            raise ValueError(f"Project not found: {job.project_id}")

        if resume_report:
            return cls._resume_report(job_id, project)

        simulation_manager: Optional[SimulationManager] = None
        simulation_id: Optional[str] = None
        simulation_completed = False
        pipeline_succeeded = False
        try:
            all_text = ProjectManager.get_extracted_text(project.project_id) or ""
            if resume_graph:
                if not all_text:
                    raise RuntimeError("Extracted project text is missing; graph cannot resume")
                graph_id = cls._resume_graph(job_id, project)
            else:
                graph_documents = cls._ingest_and_generate_ontology(
                    job_id,
                    project,
                    job.file_paths,
                    options,
                )
                all_text = ProjectManager.get_extracted_text(project.project_id) or ""
                project = ProjectManager.get_project(project.project_id)
                if not project or not project.ontology:
                    raise RuntimeError("Ontology was not persisted")
                graph_text = "\n\n---\n\n".join(graph_documents) if graph_documents else all_text
                graph_id = cls._build_graph(job_id, project, graph_text, options)
            project = ProjectManager.get_project(project.project_id)
            if not project:
                raise RuntimeError("Project disappeared after graph build")

            cls._set_stage(job_id, "simulation_create", 40, "Creating simulation")
            simulation_manager = SimulationManager()
            simulation_state = simulation_manager.create_simulation(
                project_id=project.project_id,
                graph_id=graph_id,
                enable_twitter=options["enable_twitter"],
                enable_reddit=options["enable_reddit"],
            )
            simulation_id = simulation_state.simulation_id
            ForecastJobStore.update(job_id, simulation_id=simulation_id)

            stage_ranges = {
                "reading": (40, 44),
                "generating_profiles": (44, 55),
                "generating_config": (55, 60),
            }

            def prepare_progress(stage: str, progress: int, message: str, **_: Any) -> None:
                start, end = stage_ranges.get(stage, (40, 60))
                mapped = start + int((end - start) * max(0, min(progress, 100)) / 100)
                cls._set_stage(job_id, f"simulation_{stage}", mapped, message)

            prepared = simulation_manager.prepare_simulation(
                simulation_id=simulation_id,
                simulation_requirement=options["simulation_requirement"],
                document_text=all_text,
                use_llm_for_profiles=options["use_llm_for_profiles"],
                parallel_profile_count=options["parallel_profile_count"],
                progress_callback=prepare_progress,
            )
            if (
                prepared.status != SimulationStatus.READY
                or not prepared.config_generated
                or prepared.profiles_count <= 0
            ):
                raise RuntimeError(prepared.error or "Simulation preparation did not reach ready state")

            cls._set_stage(job_id, "simulation_running", 60, "Running social simulation")
            platform = cls._platform(options["enable_twitter"], options["enable_reddit"])
            run_state = SimulationRunner.start_simulation(
                simulation_id=simulation_id,
                platform=platform,
                max_rounds=options["max_rounds"],
                max_active_agents=options["max_active_agents"],
                enable_graph_memory_update=options["enable_graph_memory_update"],
                graph_id=graph_id,
            )
            ForecastJobStore.update(job_id, simulation_pid=run_state.process_pid)
            prepared.status = SimulationStatus.RUNNING
            simulation_manager._save_simulation_state(prepared)
            cls._wait_for_simulation(job_id, simulation_id, run_state.total_rounds, options)
            simulation_completed = True

            if options["enable_graph_memory_update"]:
                ZepGraphMemoryManager.stop_updater(simulation_id)
                SimulationRunner._graph_memory_enabled.pop(simulation_id, None)
                if Config.FORECAST_MEMORY_SETTLE_SECONDS > 0:
                    time.sleep(Config.FORECAST_MEMORY_SETTLE_SECONDS)

            cls._set_stage(job_id, "report", 85, "Generating final forecast report")
            report_agent = ReportAgent(
                graph_id=graph_id,
                simulation_id=simulation_id,
                simulation_requirement=options["simulation_requirement"],
                project_id=project.project_id,
                structured_table_required=True,
                report_instructions=options["report_prompt"],
            )
            required_mcp_tools = {"search_data_files", "create_structured_table"}
            missing_tools = required_mcp_tools - set(report_agent.mcp_tools)
            if missing_tools:
                raise RuntimeError(f"Required local MCP tools unavailable: {sorted(missing_tools)}")

            def report_progress(_: str, progress: int, message: str) -> None:
                cls._set_stage(job_id, "report", 85 + int(max(0, min(progress, 100)) * 0.14), message)

            report_id = f"report_{uuid.uuid4().hex[:12]}"
            ForecastJobStore.update(job_id, report_id=report_id)
            report = report_agent.generate_report(
                progress_callback=report_progress,
                report_id=report_id,
            )
            if report.status != ReportStatus.COMPLETED:
                raise RuntimeError(report.error or "Report generation failed")
            if not report.structured_output or not report.structured_output.get("rows"):
                raise RuntimeError("Final report did not contain the required structured table")

            pipeline_succeeded = True
            return {
                "project_id": project.project_id,
                "graph_id": graph_id,
                "simulation_id": simulation_id,
                "report_id": report.report_id,
                "structured_row_count": len(report.structured_output["rows"]),
            }
        finally:
            if simulation_id:
                cls._close_simulation(simulation_id)
                if simulation_manager:
                    state = simulation_manager.get_simulation(simulation_id)
                    if state:
                        state.status = (
                            SimulationStatus.COMPLETED
                            if simulation_completed
                            else SimulationStatus.FAILED
                        )
                        if not simulation_completed and not state.error:
                            state.error = "Forecast pipeline failed"
                        simulation_manager._save_simulation_state(state)

    @classmethod
    def _resume_report(cls, job_id: str, project) -> Dict[str, Any]:
        """Finalize a failed report from its persisted outline and section files."""
        job = ForecastJobStore.get(job_id)
        if not job or not job.graph_id or not job.simulation_id or not job.report_id:
            raise RuntimeError("Report checkpoint is incomplete")

        report = ReportManager.get_report(job.report_id)
        if not report or not report.outline or not report.outline.sections:
            raise RuntimeError("Saved report outline or sections are missing")

        saved_sections = {
            item["section_index"]: item["content"]
            for item in ReportManager.get_generated_sections(job.report_id)
        }
        for index, section in enumerate(report.outline.sections, start=1):
            if section.content.strip():
                continue
            saved = saved_sections.get(index, "").strip()
            if saved:
                section.content = re.sub(
                    rf"^##\s+{re.escape(section.title)}\s*",
                    "",
                    saved,
                    count=1,
                ).strip()
        if any(not section.content.strip() for section in report.outline.sections):
            raise RuntimeError("One or more saved report sections are empty")

        cls._set_stage(job_id, "report", 95, "Finalizing saved forecast report")
        report_agent = ReportAgent(
            graph_id=job.graph_id,
            simulation_id=job.simulation_id,
            simulation_requirement=job.options["simulation_requirement"],
            project_id=project.project_id,
            structured_table_required=True,
            report_instructions=job.options["report_prompt"],
        )
        required_mcp_tools = {"search_data_files", "create_structured_table"}
        missing_tools = required_mcp_tools - set(report_agent.mcp_tools)
        if missing_tools:
            raise RuntimeError(f"Required local MCP tools unavailable: {sorted(missing_tools)}")

        report_agent.source_verification_context = (
            report_agent._load_source_verification_context()
        )
        report_content = "\n\n".join(
            f"## {section.title}\n\n{section.content}"
            for section in report.outline.sections
        )
        table_output = report.structured_output
        if not table_output or not table_output.get("rows") or not table_output.get("markdown"):
            table_output = report_agent._generate_structured_table(report_content)
        if not table_output or not table_output.get("rows"):
            raise RuntimeError("Saved report could not produce the required structured table")

        report.structured_output = table_output
        table_markdown = table_output.get("markdown", "")
        last_section = report.outline.sections[-1]
        if table_markdown and table_markdown not in last_section.content:
            last_section.content = f"{last_section.content}\n\n{table_markdown}".strip()
            ReportManager.save_section(
                report.report_id,
                len(report.outline.sections),
                last_section,
            )

        report.markdown_content = ReportManager.assemble_full_report(
            report.report_id,
            report.outline,
        )
        report.status = ReportStatus.COMPLETED
        report.error = None
        report.completed_at = datetime.now().isoformat()
        ReportManager.save_report(report)
        ReportManager.update_progress(
            report.report_id,
            "completed",
            100,
            "Report completed from saved sections",
            completed_sections=[section.title for section in report.outline.sections],
        )
        return {
            "project_id": project.project_id,
            "graph_id": job.graph_id,
            "simulation_id": job.simulation_id,
            "report_id": report.report_id,
            "structured_row_count": len(table_output["rows"]),
        }

    @classmethod
    def _ingest_and_generate_ontology(
        cls,
        job_id: str,
        project,
        file_paths: List[str],
        options: Dict[str, Any],
    ) -> List[str]:
        cls._set_stage(job_id, "ingestion", 2, "Extracting source documents")
        document_texts = []
        merged_parts = []
        for index, file_path in enumerate(file_paths):
            path = Path(file_path)
            text = TextProcessor.preprocess_text(FileParser.extract_text(str(path)))
            if not text.strip():
                continue
            original_name = project.files[index]["filename"] if index < len(project.files) else path.name
            document_texts.append(f"Source file: {original_name}\n{text}")
            merged_parts.append(f"=== {original_name} ===\n{text}")
        if not document_texts:
            raise ValueError("No uploaded document produced searchable text")

        all_text = "\n\n".join(merged_parts)
        project.total_text_length = len(all_text)
        project.simulation_requirement = options["simulation_requirement"]
        ProjectManager.save_extracted_text(project.project_id, all_text)
        ProjectManager.save_project(project)

        graph_documents = cls._prepare_graph_documents(document_texts)
        cls._set_stage(job_id, "ontology", 10, "Generating knowledge-graph ontology")
        ontology = OntologyGenerator().generate(
            document_texts=graph_documents,
            simulation_requirement=options["simulation_requirement"],
            additional_context=options.get("additional_context") or None,
        )
        project.ontology = {
            "entity_types": ontology.get("entity_types", []),
            "edge_types": ontology.get("edge_types", []),
        }
        project.analysis_summary = ontology.get("analysis_summary", "")
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)
        cls._set_stage(job_id, "ontology", 20, "Ontology generated")
        return graph_documents

    @classmethod
    def _prepare_graph_documents(cls, document_texts: List[str]) -> List[str]:
        """Create a representative graph seed while retaining full source files."""
        documents = [text.strip() for text in document_texts if text and text.strip()]
        if not documents:
            return []

        max_chars = max(1000, Config.FORECAST_GRAPH_MAX_SOURCE_CHARS)
        separator_chars = len("\n\n---\n\n") * (len(documents) - 1)
        document_budget = max(1, max_chars - separator_chars)
        if sum(map(len, documents)) <= document_budget:
            return documents

        allocations = [0] * len(documents)
        remaining_indexes = set(range(len(documents)))
        remaining_chars = document_budget
        while remaining_indexes:
            share = max(1, remaining_chars // len(remaining_indexes))
            fitting = [
                index
                for index in remaining_indexes
                if len(documents[index]) <= share
            ]
            if not fitting:
                ordered = sorted(remaining_indexes)
                for offset, index in enumerate(ordered):
                    allocations[index] = share + (1 if offset < remaining_chars % len(ordered) else 0)
                break
            for index in fitting:
                allocations[index] = len(documents[index])
                remaining_chars -= allocations[index]
                remaining_indexes.remove(index)

        return [
            cls._sample_graph_document(document, allocations[index])
            for index, document in enumerate(documents)
            if allocations[index] > 0
        ]

    @staticmethod
    def _sample_graph_document(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        marker = "\n\n[... representative rows omitted ...]\n\n"
        usable = max(1, max_chars - 2 * len(marker))
        head_size = usable // 3
        middle_size = usable // 3
        tail_size = usable - head_size - middle_size
        middle_start = max(0, (len(text) - middle_size) // 2)
        sampled = (
            text[:head_size].rstrip()
            + marker
            + text[middle_start:middle_start + middle_size].strip()
            + marker
            + text[-tail_size:].lstrip()
        )
        return sampled[:max_chars]

    @classmethod
    def _build_graph(cls, job_id: str, project, text: str, options: Dict[str, Any]) -> str:
        cls._set_stage(job_id, "graph", 20, "Building Zep knowledge graph")
        project.status = ProjectStatus.GRAPH_BUILDING
        project.chunk_size = options["chunk_size"]
        project.chunk_overlap = options["chunk_overlap"]
        ProjectManager.save_project(project)

        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        chunks = TextProcessor.split_text(text, project.chunk_size, project.chunk_overlap)
        if not chunks:
            raise ValueError("Document text did not produce graph chunks")
        graph_id = builder.create_graph(options["graph_name"] or project.name)
        project.graph_id = graph_id
        ProjectManager.save_project(project)
        ForecastJobStore.update(
            job_id,
            graph_id=graph_id,
            graph_chunks=chunks,
            graph_episode_uuids=[],
            graph_pending_episode_uuids=[],
            graph_wait_completed=False,
        )
        builder.set_ontology(graph_id, project.ontology)

        def checkpoint_episodes(episode_ids: List[str]) -> None:
            ForecastJobStore.update(
                job_id,
                graph_episode_uuids=episode_ids,
                graph_pending_episode_uuids=episode_ids,
                graph_wait_completed=False,
            )

        episode_uuids = builder.add_text_batches(
            graph_id,
            chunks,
            batch_size=3,
            progress_callback=lambda message, ratio: cls._set_stage(
                job_id, "graph", 24 + int(max(0, min(ratio, 1)) * 8), message
            ),
            checkpoint_callback=checkpoint_episodes,
        )
        if len(episode_uuids) != len(chunks):
            raise RuntimeError(
                f"Zep accepted {len(episode_uuids)} of {len(chunks)} graph episodes"
            )
        ForecastJobStore.update(
            job_id,
            graph_episode_uuids=episode_uuids,
            graph_pending_episode_uuids=episode_uuids,
            graph_wait_completed=False,
        )
        cls._wait_for_episodes(
            job_id,
            builder,
            episode_uuids,
            total_episode_count=len(episode_uuids),
        )
        cls._set_stage(
            job_id,
            "graph_validation",
            39,
            "Validating graph entities",
            graph_wait_completed=True,
        )
        graph_info = builder._get_graph_info(graph_id)
        cls._validate_graph_for_simulation(graph_info)
        project.status = ProjectStatus.GRAPH_COMPLETED
        ProjectManager.save_project(project)
        cls._set_stage(job_id, "graph", 40, "Knowledge graph completed")
        return graph_id

    @classmethod
    def _resume_graph(cls, job_id: str, project) -> str:
        job = ForecastJobStore.get(job_id)
        if (
            not job
            or not job.graph_id
            or not job.graph_chunks
            or not (
                job.graph_pending_episode_uuids
                or job.graph_wait_completed
                or len(job.graph_episode_uuids) < len(job.graph_chunks)
            )
            or job.simulation_id
        ):
            raise RuntimeError("Graph checkpoint is incomplete; forecast cannot resume")

        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        if len(job.graph_episode_uuids) > len(job.graph_chunks):
            raise RuntimeError("Graph checkpoint contains more episodes than source chunks")

        if len(job.graph_episode_uuids) < len(job.graph_chunks):
            existing_episode_ids = list(job.graph_episode_uuids)
            remaining_chunks = job.graph_chunks[len(existing_episode_ids):]

            def checkpoint_resumed_episodes(new_episode_ids: List[str]) -> None:
                combined = existing_episode_ids + new_episode_ids
                ForecastJobStore.update(
                    job_id,
                    graph_episode_uuids=combined,
                    graph_pending_episode_uuids=combined,
                    graph_wait_completed=False,
                )

            new_episode_ids = builder.add_text_batches(
                job.graph_id,
                remaining_chunks,
                batch_size=3,
                progress_callback=lambda message, ratio: cls._set_stage(
                    job_id,
                    "graph",
                    24 + int(max(0, min(ratio, 1)) * 8),
                    f"Resuming graph upload: {message}",
                ),
                checkpoint_callback=checkpoint_resumed_episodes,
            )
            if len(new_episode_ids) != len(remaining_chunks):
                raise RuntimeError(
                    f"Zep accepted {len(new_episode_ids)} of "
                    f"{len(remaining_chunks)} remaining graph episodes"
                )
            combined_episode_ids = existing_episode_ids + new_episode_ids
            ForecastJobStore.update(
                job_id,
                graph_episode_uuids=combined_episode_ids,
                graph_pending_episode_uuids=combined_episode_ids,
                graph_wait_completed=False,
            )
            job = ForecastJobStore.get(job_id)
            if not job:
                raise RuntimeError("Graph checkpoint disappeared during resume")

        total = len(job.graph_chunks)
        if job.graph_pending_episode_uuids:
            completed = total - len(job.graph_pending_episode_uuids)
            cls._set_stage(
                job_id,
                "graph_processing",
                32 + int((completed / max(total, 1)) * 7),
                f"Resuming graph processing: {completed}/{total}",
            )
            cls._wait_for_episodes(
                job_id,
                builder,
                job.graph_pending_episode_uuids,
                total_episode_count=total,
            )
        cls._set_stage(
            job_id,
            "graph_validation",
            39,
            "Validating graph entities",
            graph_wait_completed=True,
        )
        graph_info = builder._get_graph_info(job.graph_id)
        cls._validate_graph_for_simulation(graph_info)
        project.status = ProjectStatus.GRAPH_COMPLETED
        project.error = None
        ProjectManager.save_project(project)
        cls._set_stage(job_id, "graph", 40, "Knowledge graph completed")
        return job.graph_id

    @staticmethod
    def _validate_graph_for_simulation(graph_info) -> None:
        """Reject graphs that cannot provide typed simulation agents."""
        if graph_info.node_count <= 0:
            raise GraphNotUsableError(
                "Zep graph processing completed but extracted no entities. "
                "Verify that the uploaded source contains readable named entities "
                "and relationships."
            )
        if not graph_info.entity_types:
            raise GraphNotUsableError(
                f"Zep extracted {graph_info.node_count} entities and "
                f"{graph_info.edge_count} relationships, but classified 0 entities "
                "with the generated ontology. The graph cannot seed simulation agents. "
                "Upload richer forecast evidence (for this hotel workflow, include daily "
                "reservation/performance data with supporting files) or simplify the "
                "ontology and retry."
            )

    @classmethod
    def _wait_for_episodes(
        cls,
        job_id: str,
        builder: GraphBuilderService,
        episode_uuids: List[str],
        total_episode_count: Optional[int] = None,
    ) -> None:
        pending_order = list(dict.fromkeys(episode_uuids))
        pending = set(pending_order)
        total = max(total_episode_count or len(pending), len(pending))
        if not pending:
            ForecastJobStore.update(
                job_id,
                graph_pending_episode_uuids=[],
                graph_wait_completed=True,
            )
            return

        started_at = time.monotonic()
        last_progress_at = started_at
        stalled_after = max(1, Config.FORECAST_GRAPH_TIMEOUT_SECONDS)
        hard_limit = max(stalled_after, Config.FORECAST_GRAPH_MAX_TIMEOUT_SECONDS)
        max_failed_status_sweeps = max(1, Config.FORECAST_GRAPH_STATUS_ERROR_SWEEPS)
        poll_seconds = max(0.1, Config.FORECAST_GRAPH_POLL_SECONDS)
        failed_status_sweeps = 0

        while pending:
            pending_before = len(pending)
            successful_status_queries = 0
            last_status_error: Optional[Exception] = None
            hard_limit_reached = False
            for episode_uuid in list(pending):
                if time.monotonic() - started_at >= hard_limit:
                    hard_limit_reached = True
                    break
                try:
                    episode = builder.client.graph.episode.get(uuid_=episode_uuid)
                    successful_status_queries += 1
                    if getattr(episode, "processed", False):
                        pending.remove(episode_uuid)
                except Exception as exc:
                    last_status_error = exc
                    logger.debug(f"Episode status retry {episode_uuid}: {exc}")

            now = time.monotonic()
            if len(pending) < pending_before:
                last_progress_at = now
            completed = total - len(pending)
            pending_checkpoint = [
                episode_uuid for episode_uuid in pending_order if episode_uuid in pending
            ]
            cls._set_stage(
                job_id,
                "graph_processing",
                32 + int((completed / max(total, 1)) * 7),
                f"Waiting for graph processing: {completed}/{total}",
                graph_pending_episode_uuids=pending_checkpoint,
                graph_wait_completed=not pending,
            )
            if not pending:
                return

            if successful_status_queries == 0:
                failed_status_sweeps += 1
                if failed_status_sweeps >= max_failed_status_sweeps:
                    detail = f": {last_status_error}" if last_status_error else ""
                    raise ConnectionError(
                        "Zep episode status could not be read for "
                        f"{failed_status_sweeps} consecutive checks{detail}"
                    )
            else:
                failed_status_sweeps = 0

            elapsed = now - started_at
            stalled_for = now - last_progress_at
            if hard_limit_reached or elapsed >= hard_limit:
                raise TimeoutError(
                    "Graph processing reached the hard wait limit with "
                    f"{len(pending)} pending episodes ({completed}/{total} completed)"
                )
            if stalled_for >= stalled_after:
                raise TimeoutError(
                    f"Graph processing stalled for {int(stalled_for)} seconds with "
                    f"{len(pending)} pending episodes ({completed}/{total} completed)"
                )
            time.sleep(poll_seconds)

    @classmethod
    def _wait_for_simulation(
        cls,
        job_id: str,
        simulation_id: str,
        total_rounds: int,
        options: Dict[str, Any],
    ) -> None:
        deadline = time.monotonic() + options["simulation_timeout_seconds"]
        while time.monotonic() < deadline:
            state = SimulationRunner.get_run_state(simulation_id)
            if state:
                if state.runner_status == RunnerStatus.COMPLETED:
                    if options["enable_twitter"] and (
                        not state.twitter_completed or state.twitter_current_round < total_rounds
                    ):
                        raise RuntimeError("Twitter simulation did not complete all expected rounds")
                    if options["enable_reddit"] and (
                        not state.reddit_completed or state.reddit_current_round < total_rounds
                    ):
                        raise RuntimeError("Reddit simulation did not complete all expected rounds")
                    return
                if state.runner_status in (RunnerStatus.FAILED, RunnerStatus.STOPPED):
                    raise RuntimeError(state.error or f"Simulation ended as {state.runner_status.value}")
                current_round = max(
                    state.current_round,
                    state.twitter_current_round,
                    state.reddit_current_round,
                )
                ratio = current_round / max(total_rounds, 1)
                cls._set_stage(
                    job_id,
                    "simulation_running",
                    60 + int(min(ratio, 1) * 24),
                    f"Simulation round {current_round}/{total_rounds}",
                )
            time.sleep(2)
        SimulationRunner.stop_simulation(simulation_id)
        raise TimeoutError("Simulation exceeded configured wall-clock timeout")

    @staticmethod
    def _platform(enable_twitter: bool, enable_reddit: bool) -> str:
        if enable_twitter and enable_reddit:
            return "parallel"
        if enable_twitter:
            return "twitter"
        if enable_reddit:
            return "reddit"
        raise ValueError("At least one simulation platform must be enabled")

    @staticmethod
    def _close_simulation(simulation_id: str) -> None:
        try:
            ZepGraphMemoryManager.stop_updater(simulation_id)
            SimulationRunner._graph_memory_enabled.pop(simulation_id, None)
            if SimulationRunner.check_env_alive(simulation_id):
                SimulationRunner.close_simulation_env(simulation_id, timeout=15)
                deadline = time.monotonic() + 15
                while SimulationRunner.check_env_alive(simulation_id) and time.monotonic() < deadline:
                    time.sleep(1)
            if SimulationRunner.check_env_alive(simulation_id):
                process = SimulationRunner._processes.get(simulation_id)
                if process and process.poll() is None:
                    SimulationRunner._terminate_process(process, simulation_id, timeout=10)
        except Exception as exc:
            logger.warning(f"Simulation cleanup failed for {simulation_id}: {exc}")

    @staticmethod
    def _terminate_orphan_process(job: ForecastJob) -> bool:
        pid = ForecastService._resolve_simulation_pid(job)
        if not pid:
            return True
        try:
            os.kill(pid, 0)
        except OSError:
            return True

        try:
            if os.name == "nt":
                command = subprocess.run(
                    [
                        "powershell", "-NoProfile", "-Command",
                        f'(Get-CimInstance Win32_Process -Filter "ProcessId = {pid}").CommandLine',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                ).stdout
                if (
                    not job.simulation_id
                    or job.simulation_id not in command
                    or "simulation_config.json" not in command
                    or "run_" not in command
                    or "simulation.py" not in command
                ):
                    logger.warning(f"Refusing to terminate PID {pid}; command does not match {job.simulation_id}")
                    return False
                result = subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                return result.returncode == 0

            command = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout
            if (
                not job.simulation_id
                or job.simulation_id not in command
                or "simulation_config.json" not in command
                or "run_" not in command
                or "simulation.py" not in command
            ):
                logger.warning(f"Refusing to terminate PID {pid}; command does not match {job.simulation_id}")
                return False
            process_group = os.getpgid(pid)
            if process_group != pid:
                logger.warning(f"Refusing to terminate PID {pid}; it is not a simulation process-group leader")
                return False
            os.killpg(process_group, signal.SIGTERM)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.5)
                except OSError:
                    return True
            os.killpg(process_group, signal.SIGKILL)
            return True
        except Exception as exc:
            logger.warning(f"Failed to terminate orphan simulation PID {pid}: {exc}")
            return False

    @staticmethod
    def _resolve_simulation_pid(job: ForecastJob) -> Optional[int]:
        if job.simulation_pid:
            return job.simulation_pid
        if not job.simulation_id:
            return None
        run_state_path = (
            Path(SimulationRunner.RUN_STATE_DIR)
            / job.simulation_id
            / "run_state.json"
        )
        try:
            with run_state_path.open("r", encoding="utf-8") as run_state_file:
                pid = json.load(run_state_file).get("process_pid")
            return int(pid) if pid else None
        except Exception:
            return None
