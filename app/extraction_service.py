
import os
import glob
import shutil
from datetime import datetime
import fnmatch
import uuid

import tarfile, zipfile

from .model import db, ExtractionJob, File
from . import queue


class ExtractionService:

    def save_file(self, file, download_dir="/tmp/uploads"):
        os.makedirs(download_dir, exist_ok=True)

        filename = file.filename
        if not filename:
            raise ValueError("Invalid file name")
        file_path = os.path.join(download_dir, f"{uuid.uuid4().hex}_{filename}")

        file.save(file_path)

        return file_path


    def submit_extraction_job(self, file_path, pattern="json"):
        job = ExtractionJob(
            full_path=file_path,
            file_name=os.path.basename(file_path),
            file_size=os.path.getsize(file_path),
            source_archive_name=os.path.basename(file_path),
            nesting_depth=0,
            status="pending",
            submitted_at=datetime.utcnow(),
        )
        db.session.add(job)
        db.session.commit()

        queue.put({"job_type": "extraction", "job_id": job.id, "file_path": file_path, "pattern": pattern})

        return job.id


    def extract_archive(self, file_path, job_id, extract_dir="/tmp/extracted"):
        job_root = os.path.join(extract_dir, f"job_{job_id}")
        if os.path.abspath(file_path).startswith(os.path.abspath(job_root) + os.sep):
            extract_dir = os.path.join(os.path.dirname(file_path), f"{os.path.basename(file_path)}_extracted")
        else:
            extract_dir = os.path.join(job_root, f"{os.path.basename(file_path)}_extracted")
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


    def cleanup(self, input_path=None):
        if input_path and os.path.isfile(input_path):
            try:
                os.remove(input_path)
            except OSError:
                pass

        if input_path and os.path.isdir(input_path):
            shutil.rmtree(input_path, ignore_errors=True)


    def extract_all_archives(self, file_path, job_id):
        extract_dir = None
        archives_to_process = [(file_path, 0)]
        max_nesting_depth = 0
        extracted_file_entries = []

        while archives_to_process:
            current_archive_path, current_depth = archives_to_process.pop()
            file_list, current_extract_dir = self.extract_archive(current_archive_path, job_id)
            if extract_dir is None:
                extract_dir = current_extract_dir

            max_nesting_depth = max(max_nesting_depth, current_depth)

            for extracted_file in file_list:
                extracted_file_entries.append((extracted_file, current_archive_path, current_depth))
                if extracted_file.lower().endswith((".zip", ".tar", ".tar.gz", ".tgz")):
                    archives_to_process.append((extracted_file, current_depth + 1))

        return extracted_file_entries, extract_dir, max_nesting_depth


    def extract_task(self, job_id, file_path, pattern="json"):
        extract_dir = None
        job = ExtractionJob.query.filter_by(id=job_id).with_for_update().first()
        if not job:
            return None

        try:
            matched_files = []

            if job.status == "pending":
                job.status = "running"
                db.session.commit()

            extracted_file_entries, extract_dir, max_nesting_depth = self.extract_all_archives(file_path, job_id)

            for extracted_file, current_archive_path, current_depth in extracted_file_entries:
                file_name = os.path.basename(extracted_file)
                if fnmatch.fnmatch(file_name, pattern):
                    matched_files.append(
                        File(
                            full_path=extracted_file,
                            file_name=file_name,
                            file_size=os.path.getsize(extracted_file),
                            source_archive_name=os.path.basename(current_archive_path),
                            nesting_depth=current_depth,
                            job_id=job_id,
                        )
                    )

            db.session.add_all(matched_files)

            job.nesting_depth = max(job.nesting_depth, max_nesting_depth)
            job.status = "completed"
            job.completed_at = datetime.utcnow()

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            job = ExtractionJob.query.filter_by(id=job_id).with_for_update().first()
            if job and job.status != "completed":
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.session.commit()
            self.cleanup(input_path=extract_dir)

        return extract_dir
