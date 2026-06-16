from flask import Blueprint, jsonify, request, send_file

from ..service.analysis_service import AnalysisService
from ..error_handler import ValidationError

bp = Blueprint("analyze", __name__, url_prefix="/analyze")
analysis_service = AnalysisService()


@bp.route("/", methods=["POST"])
def create_analysis_job():
    file = request.files.get("archive")
    result = analysis_service.submit_analysis_job(file)
    return jsonify(result), 202


@bp.route("/<job_id>", methods=["GET"])
def get_analysis_job_status(job_id):
    result = analysis_service.get_analysis_job_status(job_id)
    return jsonify(result), 200


@bp.route("/<job_id>/results", methods=["GET"])
def list_analysis_results(job_id):
    try:
        limit = min(int(request.args.get("limit", 10)), 100)
        offset = int(request.args.get("offset", 0))
    except ValueError:
        raise ValidationError(
            details=[{"field": "query", "message": "limit and offset must be integers"}]
        )
    if limit < 0 or offset < 0:
        raise ValidationError(
            details=[{"field": "query", "message": "limit and offset must be non-negative"}]
        )

    result = analysis_service.list_analysis_results(job_id, limit, offset)
    return jsonify(result), 200

@bp.route("/<job_id>/results/download", methods=["GET"])
def download_analysis_results(job_id):
    csv_path = analysis_service.get_analysis_csv_path(job_id)
    return send_file(csv_path, as_attachment=True), 200