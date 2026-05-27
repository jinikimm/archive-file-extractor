import json

from flask import Blueprint, request, jsonify, abort

from .analysis_service import AnalysisService
from .model import AnalysisJob

bp = Blueprint("analyze", __name__, url_prefix="/analyze")
analysis_service = AnalysisService()


@bp.route("/", methods=["POST"])
def create_analysis_job():
    file = request.files.get("archive")

    if not file:
        abort(400, description="archive file is required")

    try:
        file_path = analysis_service.save_file(file)
    except ValueError as e:
        abort(400, description=str(e))

    job_id = analysis_service.submit_analysis_job(file_path)

    return jsonify({"job_id": job_id, "status": "queued"}), 202


@bp.route("/<job_id>", methods=["GET"])
def get_analysis_job_status(job_id):
    job = AnalysisJob.query.get(job_id)
    if not job:
        abort(404, description="Job not found")

    return jsonify({"status": job.status}), 200


@bp.route("/<job_id>/results", methods=["GET"])
def list_analysis_results(job_id):
    job = AnalysisJob.query.get(job_id)
    
    if not job:
        abort(404, description="Job not found")
    if job.status != "done":
        abort(400, description="Job is not completed yet")

    statistics = json.loads(job.statistics) if job.statistics else {}
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = int(request.args.get("offset", 0))

    items = sorted(statistics.items(), key=lambda item: item[0])
    paged_items = items[offset:offset + limit]
    paged_statistics = {token: count for token, count in paged_items}

    return jsonify({"total": len(items), "statistics": paged_statistics, "csv_path": job.csv_path}), 200
