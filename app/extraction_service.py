
import os
import glob
import shutil
from datetime import datetime
import fnmatch
import uuid

import tarfile, zipfile

from .model import db, Job, File
from . import queue


class ExtractionService:

    def save_file(self, file, download_dir="/tmp/uploads"):
        os.makedirs(download_dir, exist_ok=True)

        filename = file.filename
        if not filename:
            raise ValueError("Invalid file name")

        file_path = os.path.join(download_dir, filename)

        file.save(file_path)

        return file_path


    def submit_job(self, file_path, pattern="json"):
        job = Job(
            full_path=file_path,
            file_name=os.path.basename(file_path),
            file_size=os.path.getsize(file_path),
            source_archive_name=os.path.basename(file_path),
            nesting_depth=0,
            status="pending",
            submitted_at=datetime.utcnow(),
            task_count=1,
        )
        db.session.add(job)
        db.session.commit()

        queue.put([job.id, file_path, pattern, 0])

        return job.id
    

    def extract_archive(self, file_path, job_id, extract_dir="/tmp/extracted"):
        extract_dir = os.path.join(extract_dir, f"job_{job_id}", uuid.uuid4().hex)
        os.makedirs(extract_dir, exist_ok=True)

        file_list = []
        
        if file_path.endswith(".zip"):
            with zipfile.ZipFile(file_path, "r") as archive:
                archive.extractall(extract_dir)
                
        elif file_path.endswith(".tar.gz") or file_path.endswith(".tar") or file_path.endswith(".tgz"):
            with tarfile.open(file_path, "r:*") as archive:
                members = [member for member in archive.getmembers() if member.isfile()]
                archive.extractall(extract_dir, members=members)

        for f in glob.glob(os.path.join(extract_dir, "**"), recursive=True):
            if os.path.isfile(f):
                file_list.append(f)

        return file_list, extract_dir


    def cleanup(self, job_id=None, task_dir=None, input_path=None, extract_dir="/tmp/extracted"):
        if task_dir and os.path.isdir(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)

        if job_id is None:
            return

        job = Job.query.filter_by(id=job_id).first()
        if not job or job.status not in ("completed", "failed"):
            return

        shutil.rmtree(os.path.join(extract_dir, f"job_{job_id}"), ignore_errors=True)

        if input_path and os.path.isfile(input_path):
            try:
                os.remove(input_path)
            except OSError:
                pass


    def extract_task(self, job_id, file_path, pattern="json", depth=0):
        extract_dir = None
        try:
            file_list, extract_dir = self.extract_archive(file_path, job_id)
            additional_task_count = 0
            matched_files = []

            job = Job.query.filter_by(id=job_id).first()
            if job.status == "pending":
                job.status = "running"

            for file in file_list:
                file_name = os.path.basename(file)
                if fnmatch.fnmatch(file_name, pattern):
                    matched_files.append(
                        File(
                            full_path=file,
                            file_name=file_name,
                            file_size=os.path.getsize(file),
                            source_archive_name=os.path.basename(file_path),
                            nesting_depth=depth,
                            job_id=job_id,
                        )
                    )

                if file.lower().endswith((".zip", ".tar", ".tar.gz", ".tgz")):
                    additional_task_count += 1
                    queue.put([job_id, file, pattern, depth + 1])

            if matched_files:
                db.session.add_all(matched_files)

            job.nesting_depth = max(job.nesting_depth, depth)
            job.task_count = max(0, job.task_count - 1 + additional_task_count)

            if job.task_count == 0 and job.status != "failed":
                job.status = "completed"
                job.completed_at = datetime.utcnow()

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            job = Job.query.filter_by(id=job_id).first()
            if job and job.status != "completed":
                job.status = "failed"
                job.error_message = str(e)
                job.task_count = max(0, job.task_count - 1)
                job.completed_at = datetime.utcnow()
                db.session.commit()

        return extract_dir
