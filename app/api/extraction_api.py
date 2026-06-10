from flask import Blueprint, request, jsonify, abort

from ..service.extraction_service import ExtractionService
from ..model import ExtractionJob, File


bp = Blueprint("extractions", __name__, url_prefix="/extractions")
extraction_service = ExtractionService()


@bp.route("/", methods=["POST"])
def create_extraction_job():
    file = request.files.get("archive")
    pattern = request.form.get("pattern", "*.json")
    job_id = extraction_service.submit_extraction_job(file, pattern)
    return jsonify({"job_id": job_id}), 202


@bp.route("/<job_id>", methods=["GET"])
def get_extraction_job_status(job_id):
    result = extraction_service.get_extraction_job_status(job_id)
    return jsonify(result), 200

@bp.route("/<job_id>/results", methods=["GET"])
def list_extraction_results(job_id):
    limit = int(request.args.get("limit", 10))
    offset = int(request.args.get("offset", 0))
    result = extraction_service.list_extraction_results(job_id, limit, offset)
    return jsonify(result), 200


