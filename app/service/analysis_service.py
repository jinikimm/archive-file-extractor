import json
import os
from datetime import datetime

from ..worker.token_scanner import scan_tokens
from ..model import db, AnalysisJob
from .. import queue
from .extraction_service import ExtractionService


class AnalysisService:

    def __init__(self):
        self.extraction_service = ExtractionService()

    def save_file(self, file, download_dir="/tmp/uploads"):
        return self.extraction_service.save_file(file, download_dir)

    def get_analysis_csv_path(self, analysis_job_id):
        return os.path.join("/tmp/analysis", f"analysis_{analysis_job_id}.csv")

    def submit_analysis_job(self, file_path):
        job = AnalysisJob(
            status="queued",
            submitted_at=datetime.utcnow(),
            source_archive_name=os.path.basename(file_path),
        )
        db.session.add(job)
        db.session.commit()

        queue.put({"job_type": "analyze", "job_id": job.id, "file_path": file_path})

        return job.id

    def analyze_task(self, analysis_job_id, file_path):
        extract_dir = None
        try:
            job = AnalysisJob.query.filter_by(id=analysis_job_id).with_for_update().first()
            if not job:
                return None

            if job.status == "queued":
                job.status = "running"
                job.started_at = datetime.utcnow()
                db.session.commit()

            _, extract_dir, _ = self.extraction_service.extract_all_archives(file_path, f"analysis_{analysis_job_id}")

            csv_path = self.get_analysis_csv_path(analysis_job_id)
            statistics = scan_tokens(extract_dir, csv_path)

            job.statistics = json.dumps(statistics)
            job.csv_path = csv_path
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            job = AnalysisJob.query.filter_by(id=analysis_job_id).with_for_update().first()
            if job and job.status != "completed":
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.session.commit()
        finally:
            self.extraction_service.cleanup(extract_dir)

        return extract_dir
