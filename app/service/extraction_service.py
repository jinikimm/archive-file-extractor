import fnmatch
import json
import os
import threading
import uuid
from datetime import datetime

from flask import current_app

from ..error_handler import ConflictError, NotFoundError, ValidationError
from ..db.model import ExtractionJob, File, db
from ..service.utils import cleanup, save_file
from ..worker.archive_extractor import extract_all_archives_parrel


class ExtractionService:
    def create_extraction_job(self, job_id, file_path):
        job = ExtractionJob(
            id=job_id,
            work_path=file_path,
            file_name=os.path.basename(file_path),
            file_size=os.path.getsize(file_path),
            status="queued",
            submitted_at=datetime.utcnow(),
        )
        db.session.add(job)
        db.session.commit()

        return job_id, job.status

    def create_extracted_file(self, f, job_id, work_dir):
        full_path = os.path.relpath(f["full_path"], work_dir)
        paths = full_path.split(os.sep)

        source_archive_name = paths[0]
        depth = len(paths) - 1

        db.session.add(
            File(
                full_path=full_path,
                file_name=f["file_name"],
                file_size=f["file_size"],
                source_archive_name=source_archive_name,
                nesting_depth=depth,
                job_id=job_id,
                extracted_at=datetime.utcnow(),
            )
        )

    def update_extraction_job_status(self, job_id, status, **kwargs):
        job = ExtractionJob.query.get(job_id)
        if job: 
            job.status = status
            if status == "processing":
                job.started_at = datetime.utcnow()
            if status == "completed":
                job.completed_at = datetime.utcnow()
            if status == "failed" and "error_message" in kwargs:
                job.completed_at = datetime.utcnow()
                job.error_message = kwargs["error_message"]
            db.session.commit()

    def _process_extraction_job(self, app, job_id, file_path, pattern):
        with app.app_context():
            work_dir = os.path.dirname(file_path)
            app.logger.info(json.dumps({"event": "job_started", "job_id": job_id}))
            try:
                self.update_extraction_job_status(job_id, "processing")

                file_list = extract_all_archives_parrel(file_path)

                for f in file_list:
                    if fnmatch.fnmatch(f["file_name"], pattern):
                        self.create_extracted_file(f, job_id, work_dir)

                job = ExtractionJob.query.get(job_id)
                if job and job.status != "failed":
                    self.update_extraction_job_status(job_id, "completed")
                    app.logger.info(
                        json.dumps({"event": "job_completed", "job_id": job_id})
                    )

            except Exception as e:
                app.logger.error(
                    json.dumps(
                        {"event": "job_failed", "job_id": job_id, "error": str(e)}
                    )
                )

                db.session.rollback()
                self.update_extraction_job_status(job_id, "failed", error_message=str(e))

            finally:
                cleanup(work_dir)
                db.session.remove()

    def submit_extraction_job(self, file, pattern):
        if not file:
            raise ValidationError(
                details=[{"field": "file", "message": "archive file is required"}]
            )
        if not pattern:
            raise ValidationError(
                details=[{"field": "pattern", "message": "pattern is required"}]
            )

        job_id = str(uuid.uuid4())
        work_dir = os.path.join("/tmp", "extract", job_id)

        try:
            file_path = save_file(file, work_dir)
        except ValueError as e:
            cleanup(work_dir)
            raise ValidationError(details=[{"field": "file", "message": str(e)}])

        _, job_status = self.create_extraction_job(job_id, file_path)

        app = current_app._get_current_object()
        app.logger.info(json.dumps({"event": "job_submitted", "job_id": job_id}))
        t = threading.Thread(
            target=self._process_extraction_job,
            args=(app, job_id, file_path, pattern),
            daemon=False,
        )
        t.start()

        return {"job_id": job_id, "status": job_status}

    def get_extraction_job_status(self, job_id):
        job = ExtractionJob.query.get(job_id)
        if not job:
            raise NotFoundError(
                details=[{"field": "job_id", "message": "Job not found"}]
            )

        return {"status": job.status}  # matched count 도 반환해야함

    def list_extraction_results(self, job_id, limit=10, offset=0):
        job = ExtractionJob.query.get(job_id)
        if not job:
            raise NotFoundError(
                details=[{"field": "job_id", "message": "Job not found"}]
            )
        if job.status == "processing":
            raise ConflictError(
                details=[{"field": "job_id", "message": "Job is not completed yet"}]
            )
        if job.status == "failed":
            raise ConflictError(
                details=[
                    {"field": "job_id", "message": f"Job failed: {job.error_message}"}
                ]
            )

        q = File.query.filter_by(job_id=job_id).order_by(File.nesting_depth.asc())

        items = [
            {
                "full_path": f.full_path,
                "file_name": f.file_name,
                "file_size": f.file_size,
                "source_archive_name": f.source_archive_name,
                "nesting_depth": f.nesting_depth,
            }
            for f in q.offset(offset).limit(limit)
        ]
        return {"total": q.count(), "files": items, "limit": limit, "offset": offset}
