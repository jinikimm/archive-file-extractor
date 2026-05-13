from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)

    full_path = db.Column(db.String(255), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)

    source_archive_name = db.Column(db.String(255), nullable=False)

    nesting_depth = db.Column(db.Integer, nullable=False)

    status = db.Column(db.String(20), nullable=False)

    submitted_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    error_message = db.Column(db.String(255), nullable=True)

    task_count = db.Column(db.Integer, nullable=False, default=0)


class File(db.Model):
    __tablename__ = "files"

    id = db.Column(db.Integer, primary_key=True)

    full_path = db.Column(db.String(255), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    
    source_archive_name = db.Column(db.String(255), nullable=False)

    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    job = db.relationship("Job")

    nesting_depth = db.Column(db.Integer, nullable=False)