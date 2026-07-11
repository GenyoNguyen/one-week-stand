"""Backend-only API for the complete forecasting pipeline."""

import os
import hmac
from functools import wraps
from typing import Any

from flask import jsonify, request, url_for

from . import forecast_bp
from ..config import Config
from ..models.project import ProjectManager
from ..services.forecast_service import (
    ForecastQueueFullError,
    ForecastService,
    ForecastStatus,
)
from ..utils.logger import get_logger


logger = get_logger("mirofish.api.forecast")

HOTEL_PERFORMANCE_SCHEMAS = (
    {
        "date", "property", "occupancy_pct", "adr_vnd", "revpar_vnd",
        "room_nights", "revenue_vnd", "booking_pace_pct",
        "pickup_room_nights", "pickup_24h_room_nights", "market_segment",
        "source", "channel", "guest_nationality", "lead_time_days",
        "cancellations", "budget_room_nights", "budget_adr_vnd",
        "last_year_room_nights", "ly_adr_vnd",
        "on_the_books_room_nights", "stly_otb_room_nights",
    },
    {
        "date", "property", "rooms_available", "rooms_sold", "room_revenue",
        "adr", "occupancy", "market_segment", "channel",
        "guest_nationality", "lead_time_days", "cancellations",
        "budget_occupancy", "budget_adr", "ly_occupancy", "ly_adr",
        "otb_rooms",
    },
)


def _contains_hotel_performance_data(files) -> bool:
    for file in files:
        position = file.stream.tell()
        try:
            sample = file.stream.read(512 * 1024)
        finally:
            file.stream.seek(position)
        text = sample.decode("utf-8", errors="ignore").lower()
        columns = {
            cell.strip()
            for line in text.splitlines()
            if "|" in line
            for cell in line.strip().strip("|").split("|")
        }
        if any(required <= columns for required in HOTEL_PERFORMANCE_SCHEMAS):
            return True
    return False


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("Boolean values must be one of: true, false, 1, 0, yes, no, on, off")


def _require_api_key(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        if not Config.FORECAST_API_KEY:
            return jsonify({
                "success": False,
                "error": "Forecast service is disabled until FORECAST_API_KEY is configured",
            }), 503
        authorization = request.headers.get("Authorization", "")
        bearer = authorization[7:] if authorization.lower().startswith("bearer ") else ""
        provided = request.headers.get("X-API-Key") or bearer
        if not provided or not hmac.compare_digest(provided, Config.FORECAST_API_KEY):
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return handler(*args, **kwargs)
    return wrapped


def _as_int(
    value: Any,
    default: int,
    field: str,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if parsed < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{field} must be <= {maximum}")
    return parsed


def _public_response(job) -> dict[str, Any]:
    data = job.to_public_dict()
    data["status_url"] = url_for("forecast.get_forecast", job_id=job.job_id)
    data["result_url"] = url_for("forecast.get_forecast_result", job_id=job.job_id)
    return data


@forecast_bp.route("", methods=["POST"])
@_require_api_key
def create_forecast():
    """Upload source files and start the complete asynchronous forecast pipeline."""
    project = None
    try:
        ForecastService.recover_interrupted_jobs()
        files = request.files.getlist("files")
        files = [file for file in files if file and file.filename]
        if not files:
            return jsonify({"success": False, "error": "At least one source file is required"}), 400
        if len(files) > Config.FORECAST_MAX_FILES:
            return jsonify({
                "success": False,
                "error": f"At most {Config.FORECAST_MAX_FILES} source files are allowed",
            }), 400

        invalid_files = []
        for file in files:
            extension = os.path.splitext(file.filename)[1].lower().lstrip(".")
            if extension not in Config.ALLOWED_EXTENSIONS:
                invalid_files.append(file.filename)
        if invalid_files:
            return jsonify({
                "success": False,
                "error": f"Unsupported source files: {invalid_files}",
                "allowed_extensions": sorted(Config.ALLOWED_EXTENSIONS),
            }), 400

        data_profile = request.form.get("data_profile", "generic").strip().lower()
        if data_profile not in {"generic", "hotel"}:
            return jsonify({
                "success": False,
                "error": "data_profile must be either generic or hotel",
            }), 400
        if data_profile == "hotel" and not _contains_hotel_performance_data(files):
            return jsonify({
                "success": False,
                "error": (
                    "Hotel forecasts require at least one daily reservation/performance "
                    "dataset; property, room, and guest-flow files are supporting inputs."
                ),
            }), 400

        simulation_requirement = (
            request.form.get("simulation_requirement", "").strip()
            or Config.FORECAST_DEFAULT_REQUIREMENT
        )
        project_name = request.form.get("project_name", "Forecast Service Project").strip()
        report_prompt = (
            request.form.get("report_prompt", "").strip()
            or Config.FORECAST_DEFAULT_REPORT_PROMPT
        )

        enable_twitter = _as_bool(request.form.get("enable_twitter"), True)
        enable_reddit = _as_bool(request.form.get("enable_reddit"), True)
        if not enable_twitter and not enable_reddit:
            return jsonify({"success": False, "error": "At least one platform must be enabled"}), 400

        chunk_size = _as_int(
            request.form.get("chunk_size"),
            Config.FORECAST_DEFAULT_CHUNK_SIZE,
            "chunk_size",
            100,
            5000,
        )
        chunk_overlap = _as_int(
            request.form.get("chunk_overlap"),
            Config.FORECAST_DEFAULT_CHUNK_OVERLAP,
            "chunk_overlap",
            0,
        )
        if chunk_overlap >= chunk_size:
            return jsonify({"success": False, "error": "chunk_overlap must be smaller than chunk_size"}), 400

        options = {
            "data_profile": data_profile,
            "simulation_requirement": simulation_requirement,
            "report_prompt": report_prompt,
            "additional_context": request.form.get("additional_context", "").strip(),
            "graph_name": request.form.get("graph_name", "").strip() or project_name,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "enable_twitter": enable_twitter,
            "enable_reddit": enable_reddit,
            "use_llm_for_profiles": _as_bool(request.form.get("use_llm_for_profiles"), True),
            "parallel_profile_count": _as_int(
                request.form.get("parallel_profile_count"), 5, "parallel_profile_count", 1, 20
            ),
            "max_rounds": _as_int(
                request.form.get("max_rounds"), Config.FORECAST_DEFAULT_MAX_ROUNDS,
                "max_rounds", 1, Config.FORECAST_MAX_ROUNDS
            ),
            "max_active_agents": _as_int(
                request.form.get("max_active_agents"),
                Config.FORECAST_DEFAULT_MAX_ACTIVE_AGENTS,
                "max_active_agents",
                1,
                Config.FORECAST_MAX_ACTIVE_AGENTS,
            ),
            "enable_graph_memory_update": _as_bool(
                request.form.get("enable_graph_memory_update"), True
            ),
            "simulation_timeout_seconds": _as_int(
                request.form.get("simulation_timeout_seconds"),
                Config.FORECAST_SIMULATION_TIMEOUT_SECONDS,
                "simulation_timeout_seconds",
                60,
                86400,
            ),
        }

        project = ProjectManager.create_project(name=project_name)
        project.simulation_requirement = simulation_requirement
        file_paths = []
        for file in files:
            file_info = ProjectManager.save_file_to_project(
                project.project_id, file, file.filename
            )
            project.files.append({
                "filename": file_info["original_filename"],
                "stored_filename": file_info["saved_filename"],
                "size": file_info["size"],
            })
            file_paths.append(file_info["path"])
        ProjectManager.save_project(project)

        job = ForecastService.submit(project.project_id, file_paths, options)
        return jsonify({"success": True, "data": _public_response(job)}), 202
    except ForecastQueueFullError as exc:
        if project:
            ProjectManager.delete_project(project.project_id)
        response = jsonify({"success": False, "error": str(exc)})
        response.headers["Retry-After"] = "30"
        return response, 429
    except ValueError as exc:
        if project:
            ProjectManager.delete_project(project.project_id)
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception(f"Failed to submit forecast: {exc}")
        if project:
            ProjectManager.delete_project(project.project_id)
        return jsonify({"success": False, "error": str(exc)}), 500


@forecast_bp.route("/latest", methods=["GET"])
@_require_api_key
def get_latest_forecast():
    """Return the most recent completed forecast so its report survives a page reload."""
    job = ForecastService.get_latest_completed_job()
    if not job:
        return jsonify({"success": False, "error": "No completed forecast found"}), 404
    return jsonify({"success": True, "data": _public_response(job)})


@forecast_bp.route("/<job_id>", methods=["GET"])
@_require_api_key
def get_forecast(job_id: str):
    ForecastService.recover_interrupted_jobs()
    try:
        job = ForecastService.get_job(job_id)
    except ValueError:
        job = None
    if not job:
        return jsonify({"success": False, "error": "Forecast job not found"}), 404
    return jsonify({"success": True, "data": _public_response(job)})


@forecast_bp.route("/<job_id>/resume", methods=["POST"])
@_require_api_key
def resume_forecast(job_id: str):
    """Resume a checkpointed graph wait without creating a duplicate graph."""
    ForecastService.recover_interrupted_jobs()
    try:
        job = ForecastService.get_job(job_id)
    except ValueError:
        job = None
    if not job:
        return jsonify({"success": False, "error": "Forecast job not found"}), 404
    try:
        resumed = ForecastService.resume(job_id)
        return jsonify({"success": True, "data": _public_response(resumed)}), 202
    except ForecastQueueFullError as exc:
        response = jsonify({"success": False, "error": str(exc)})
        response.headers["Retry-After"] = "30"
        return response, 429
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409
    except Exception as exc:
        logger.exception(f"Failed to resume forecast {job_id}: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500


@forecast_bp.route("/<job_id>/result", methods=["GET"])
@_require_api_key
def get_forecast_result(job_id: str):
    ForecastService.recover_interrupted_jobs()
    try:
        job = ForecastService.get_job(job_id)
    except ValueError:
        job = None
    if not job:
        return jsonify({"success": False, "error": "Forecast job not found"}), 404
    if job.status == ForecastStatus.FAILED:
        return jsonify({"success": False, "error": job.error, "data": job.to_public_dict()}), 422
    if job.status != ForecastStatus.COMPLETED:
        return jsonify({"success": True, "data": job.to_public_dict()}), 202
    try:
        result = ForecastService.get_result(job_id)
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
