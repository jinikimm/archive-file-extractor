from flask import Blueprint, request, jsonify, abort

from .extraction_service import ExtractionService
from .model import db, Job, File


def serialize_file(file):
    return {
        "full_path": file.full_path,
        "file_name": file.file_name,
        "file_size": file.file_size,
        "source_archive_name": file.source_archive_name,
        "nesting_depth": file.nesting_depth,
    }


bp = Blueprint("extractions", __name__, url_prefix="/extractions")
extraction_service = ExtractionService()


@bp.route("/", methods=["POST"])
def create_extraction_job():
    file = request.files.get("archive")
    pattern = request.form.get("pattern")

    if not file:
        abort(400, description="archive file is required")
    if not pattern:
        abort(400, description="pattern is required")

    try:
        file_path = extraction_service.save_file(file)
    except ValueError as e:
        abort(400, description=str(e))
    
    job_id = extraction_service.submit_job(file_path, pattern)

    return jsonify({"job_id": job_id}), 202


@bp.route("/<job_id>", methods=["GET"])
def get_extraction_job_status(job_id):
    job = Job.query.get(job_id)
    if not job:
        abort(404, description="Job not found")

    return jsonify({"status": job.status}), 200

@bp.route("/<job_id>/results", methods=["GET"])
def list_extraction_results(job_id):
    job = Job.query.get(job_id)

    if not job:
        abort(404, description="Job not found")
    if job.status != "completed":
        abort(400, description="Job is not completed yet")

    limit = min(int(request.args.get("limit", 20)), 100)
    offset = int(request.args.get("offset", 0))
        
    total = File.query.filter_by(job_id=job_id).count()
    files = File.query.filter_by(job_id=job_id).offset(offset).limit(limit).all()

    return jsonify({"total": total, "files": [serialize_file(f) for f in files]}), 200


@bp.route("/<job_id>", methods=["DELETE"])
def delete_extraction_job(job_id):

    return jsonify("Not implemented"), 204

