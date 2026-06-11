import uuid
from uuid import uuid4

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class ExtractionJob(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))

    work_path = db.Column(db.Text, nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)

    status = db.Column(db.String(20), nullable=False)

    submitted_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    error_message = db.Column(db.Text, nullable=True)


class File(db.Model):
    __tablename__ = "files"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))

    full_path = db.Column(db.Text, nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)

    job_id = db.Column(
        db.String(36), db.ForeignKey("jobs.id"), nullable=False, index=True
    )

    nesting_depth = db.Column(db.Integer, nullable=False)
    source_archive_name = db.Column(db.String(255), nullable=False)

    extracted_at = db.Column(db.DateTime, nullable=False)

    def to_dict(self):
        return {
            "full_path": self.full_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "source_archive_name": self.source_archive_name,
            "nesting_depth": self.nesting_depth,
        }


class AnalysisJob(db.Model):
    __tablename__ = "analysis_jobs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))

    status = db.Column(db.String(20), nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    source_archive_name = db.Column(db.String(255), nullable=False)
    error_message = db.Column(db.Text, nullable=True)

    statistics = db.Column(db.Text, nullable=True)
    csv_path = db.Column(db.Text, nullable=True)
