
import os
import glob
import datetime

import tarfile, zipfile, gzip

from .model import db, Job, File
from . import queue


class ExtractionService:

    def save_file(file, download_dir="/tmp/uploads"):
        os.makedirs(download_dir, exist_ok=True)

        filename = file.filename
        if not filename:
            raise ValueError("Invalid file name")

        file_path = os.path.join(download_dir, filename)

        file.save(file_path)

        return file_path


    def submit_job(file_path, pattern="json"):
        job = Job(
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

        queue.put([job.id, file_path, pattern])

        return job.id
    

    def extract_archive(file_path, extract_dir="/tmp/extracted"):
        extract_dir = os.path.join("/tmp/extracted", file_path)
        os.makedirs(extract_dir, exist_ok=True)

        file_list = []
        
        if file_path.endswith(".zip"):
            with zipfile.ZipFile(file_path, "r") as archive:
                archive.extractall(extract_dir)
                
        elif file_path.endswith(".tar.gz") or file_path.endswith(".tar"):
            with tarfile.open(file_path, "r:*") as archive:
                members = [member for member in archive.getmembers() if member.isfile()]
                archive.extractall(extract_dir, members=members)
                    
        elif file_path.endswith(".gz"):
            output_name = os.path.basename(file_path)[:-3]
            output_path = os.path.join(extract_dir, output_name)
            with gzip.open(file_path, "rb") as src, open(output_path, "wb") as dst:
                dst.write(src.read())

        for f in glob.glob(os.path.join(extract_dir, "**"), recursive=True):
            if os.path.isfile(f):
                file_list.append(f)

        return file_list


    def save_extracted_file(file_path, job_id):
        file = File(
            full_path=file_path,
            file_name=os.path.basename(file_path),
            file_size=os.path.getsize(file_path),
            source_archive_name=os.path.basename(file_path),
            nesting_depth=0,
            job_id=job_id
        )
        db.session.add(file)
        db.session.commit()

        return file.id


    def extract_task(job_id, file_path, pattern="json"):
        
        file_list = self.extract_archive(file_path)

        if file_list != []:
            Job.query.filter_by(id=job_id).update({
                "nesting_depth": Job.nesting_depth + 1,
                "status": "running",
                "task_count": Job.task_count - 1,
                })
            
            additional_tasks = []

            for file in file_list:
                if file.endswith(pattern):
                    self.save_extracted_file(file, job_id)
                else:
                    additional_tasks.append([job_id, file, pattern])
                    queue.put([job_id, file, pattern])
    
            Job.query.filter_by(id=job_id).update({
                "task_count": Job.task_count + len(additional_tasks),
            })
            
        else:
            Job.query.filter_by(id=job_id).update({
                "task_count": Job.task_count - 1,
                })
            task_count = Job.query.filter_by(id=job_id).first().task_count
            if task_count == 0:
                Job.query.filter_by(id=job_id).update({
                    "status": "completed",
                    "completed_at": datetime.utcnow(),
                })

        db.session.commit()

        return ""
