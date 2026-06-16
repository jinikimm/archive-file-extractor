from flask import Blueprint, jsonify, request

from ..error_handler import ValidationError
from ..service.extraction_service import ExtractionService

bp = Blueprint("extractions", __name__, url_prefix="/extractions")
extraction_service = ExtractionService()


@bp.route("/", methods=["POST"])
def create_extraction_job():
    file = request.files.get("archive")
    pattern = request.form.get("pattern", "*.json")
    result = extraction_service.submit_extraction_job(file, pattern)
    return jsonify(result), 202


@bp.route("/<job_id>", methods=["GET"])
def get_extraction_job_status(job_id):
    result = extraction_service.get_extraction_job_status(job_id)
    return jsonify(result), 200


@bp.route("/<job_id>/results", methods=["GET"])
def list_extraction_results(job_id):
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

    result = extraction_service.list_extraction_results(job_id, limit, offset)
    return jsonify(result), 200
