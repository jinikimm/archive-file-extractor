from flask import Blueprint, jsonify, request

from ..service.analysis_service import AnalysisService

bp = Blueprint("analyze", __name__, url_prefix="/analyze")
analysis_service = AnalysisService()


@bp.route("/", methods=["POST"])
def create_analysis_job():
    file = request.files.get("archive")
    job_id = analysis_service.submit_analysis_job(file)
    return jsonify({"job_id": job_id, "status": "queued"}), 202


@bp.route("/<job_id>", methods=["GET"])
def get_analysis_job_status(job_id):
    result = analysis_service.get_analysis_job_status(job_id)
    return jsonify(result), 200


@bp.route("/<job_id>/results", methods=["GET"])
def list_analysis_results(job_id):
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = int(request.args.get("offset", 0))
    result = analysis_service.list_analysis_results(job_id, limit, offset)
    return jsonify(result), 200
