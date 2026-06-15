import io
from datetime import datetime

import pytest

from app import create_app
from app.api import extraction_api
from app.db.model import ExtractionJob, File, db


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app.test_client()


def submit_extraction(
    client, archive_name="sample.zip", pattern="*.json", payload=b"PK"
):
    data = {
        "archive": (io.BytesIO(payload), archive_name),
        "pattern": pattern,
    }
    return client.post("/extractions/", data=data, content_type="multipart/form-data")


def create_extraction_job(status="processing", error_message=None):
    job = ExtractionJob(
        id="job-ext-1",
        work_path="/tmp/extract/job-ext-1/sample.zip",
        file_name="sample.zip",
        file_size=100,
        status=status,
        submitted_at=datetime.utcnow(),
        error_message=error_message,
    )
    db.session.add(job)
    db.session.commit()
    return job


def test_create_extraction_job_returns_202_and_job_id(client, monkeypatch):
    monkeypatch.setattr(
        extraction_api.extraction_service,
        "submit_extraction_job",
        lambda file, pattern: {"job_id": "job-submit-1", "status": "queued"},
    )

    response = submit_extraction(client)
    body = response.get_json()

    assert response.status_code == 202
    assert body["job_id"] == "job-submit-1"
    assert body["status"] == "queued"


def test_create_extraction_job_missing_file_returns_validation_error(client):
    response = client.post("/extractions/", data={}, content_type="multipart/form-data")
    body = response.get_json()

    assert response.status_code == 400
    assert body["error"]["code"] == "validation_error"


def test_get_extraction_status_not_found(client):
    response = client.get("/extractions/not-found")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_get_extraction_status_processing(client):
    create_extraction_job(status="processing")

    response = client.get("/extractions/job-ext-1")

    assert response.status_code == 200
    assert response.get_json()["status"] == "processing"


def test_get_extraction_results_processing_returns_conflict(client):
    create_extraction_job(status="processing")

    response = client.get("/extractions/job-ext-1/results")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "conflict"


def test_get_extraction_results_failed_returns_reason(client):
    create_extraction_job(status="failed", error_message="Archive extraction failed")

    response = client.get("/extractions/job-ext-1/results")
    body = response.get_json()

    assert response.status_code == 409
    assert body["error"]["code"] == "conflict"
    assert "Job failed:" in body["error"]["details"][0]["message"]


def test_get_extraction_results_completed_with_pagination(client):
    create_extraction_job(status="completed")

    files = [
        File(
            full_path=f"root/file{i}.json",
            file_name=f"file{i}.json",
            file_size=100 + i,
            source_archive_name="sample.zip",
            nesting_depth=1,
            job_id="job-ext-1",
            extracted_at=datetime.utcnow(),
        )
        for i in range(5)
    ]
    db.session.add_all(files)
    db.session.commit()

    response = client.get("/extractions/job-ext-1/results?limit=2&offset=1")
    body = response.get_json()

    assert response.status_code == 200
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["files"]) == 2


def test_request_id_header_is_propagated_on_error(client):
    req_id = "req-ext-1"
    response = client.post(
        "/extractions/",
        data={},
        content_type="multipart/form-data",
        headers={"X-Request-ID": req_id},
    )
    body = response.get_json()

    assert response.status_code == 400
    assert response.headers.get("X-Request-ID") == req_id
    assert body["request_id"] == req_id
