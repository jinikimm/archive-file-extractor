import json
import os
import threading
import uuid
from datetime import datetime

from flask import current_app, request

from ..error_handler import ConflictError, NotFoundError, ValidationError
from ..db.model import AnalysisJob, db
from ..service.utils import cleanup, save_file
from ..worker.archive_extractor import extract_all_archives_parrel
from ..worker.firmware_analyzer import firmware_analyzer, get_analysis_csv_path


class AnalysisService:
    def create_analysis_job(self, job_id, file_path):
        job = AnalysisJob(
            id=job_id,
            source_archive_name=os.path.basename(file_path),
            status="queued",
            submitted_at=datetime.utcnow(),
        )
        db.session.add(job)
        db.session.commit()

        return job_id, job.status

    def update_analysis_job_status(self, job_id, status, **kwargs):
        job = AnalysisJob.query.get(job_id)
        if job: 
            if job.status == "queued" and status == "completed" and "statistics" in kwargs and "csv_path" in kwargs:
                job.completed_at = datetime.utcnow()
                job.statistics = json.dumps(kwargs["statistics"])
                job.csv_path = kwargs["csv_path"]
            if job.status != "completed" and status == "failed" and "error_message" in kwargs:
                job.completed_at = datetime.utcnow()
                job.error_message = kwargs["error_message"]
            job.status = status
            db.session.commit()

    def _process_analysis_job(self, app, job_id, file_path):
        with app.app_context():
            work_dir = os.path.dirname(file_path)
            app.logger.info(json.dumps({"event": "job_started", "job_id": job_id}))
            try:
                self.update_analysis_job_status(job_id, "processing")

                file_list = extract_all_archives_parrel(file_path)

                csv_path = get_analysis_csv_path(job_id)
                statistics = firmware_analyzer(file_list, work_dir, csv_path)

                job = AnalysisJob.query.get(job_id)
                if job and job.status != "failed":
                    self.update_analysis_job_status(job_id, "completed", statistics=statistics, csv_path=csv_path)
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
                self.update_analysis_job_status(job_id, "failed", error_message=str(e))

            finally:
                cleanup(work_dir)
                db.session.remove()

    def submit_analysis_job(self, file):
        if not file:
            raise ValidationError(
                details=[{"field": "file", "message": "archive file is required"}]
            )

        job_id = str(uuid.uuid4())
        work_dir = os.path.join("/tmp", "analysis", job_id)
        try:
            file_path = save_file(file, work_dir)
        except ValueError as e:
            cleanup(work_dir)
            raise ValidationError(details=[{"field": "file", "message": str(e)}])

        _, job_status = self.create_analysis_job(job_id, file_path)

        app = current_app._get_current_object()
        app.logger.info(json.dumps({"event": "job_submitted", "job_id": job_id}))
        t = threading.Thread(
            target=self._process_analysis_job,
            args=(app, job_id, file_path),
            daemon=False,
        )
        t.start()

        return {"job_id": job_id, "status": job_status}

    def get_analysis_job_status(self, job_id):
        job = AnalysisJob.query.get(job_id)
        if not job:
            raise NotFoundError(
                details=[{"field": "job_id", "message": "Job not found"}]
            )

        return {"status": job.status}

    def list_analysis_results(self, job_id, limit=10, offset=0):
        job = AnalysisJob.query.get(job_id)
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

        statistics = json.loads(job.statistics) if job.statistics else {}
        items = sorted(statistics.items(), key=lambda item: item[0])
        paged_items = items[offset : offset + limit]
        paged_statistics = {token: count for token, count in paged_items}

        return {
            "total": len(items),
            "statistics": paged_statistics,
            "csv_download_url": request.host_url.rstrip("/") + f"/analyze/{job_id}/results/download",
        }

    def get_analysis_csv_path(self, job_id):
        job = AnalysisJob.query.get(job_id)
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

        return job.csv_path
