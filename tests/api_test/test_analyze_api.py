import io
import json
from datetime import datetime

import pytest

from app import create_app
from app.api import analyze_api
from app.db.model import AnalysisJob, db


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app.test_client()


def submit_analysis(client, archive_name="sample.zip", payload=b"PK"):
    data = {"archive": (io.BytesIO(payload), archive_name)}
    return client.post("/analyze/", data=data, content_type="multipart/form-data")


def create_analysis_job(status="processing", statistics=None, error_message=None):
    job = AnalysisJob(
        id="job-an-1",
        source_archive_name="sample.zip",
        status=status,
        submitted_at=datetime.utcnow(),
        statistics=json.dumps(statistics) if statistics is not None else None,
        error_message=error_message,
        csv_path="/tmp/analysis/analysis_job-an-1.csv",
    )
    db.session.add(job)
    db.session.commit()
    return job


def test_create_analysis_job_returns_202_and_job_id(client, monkeypatch):
    monkeypatch.setattr(
        analyze_api.analysis_service,
        "submit_analysis_job",
        lambda file: "job-submit-1",
    )

    response = submit_analysis(client)
    body = response.get_json()

    assert response.status_code == 202
    assert body["job_id"] == "job-submit-1"
    assert body["status"] == "queued"


def test_create_analysis_job_missing_file_returns_validation_error(client):
    response = client.post("/analyze/", data={}, content_type="multipart/form-data")
    body = response.get_json()

    assert response.status_code == 400
    assert body["error"]["code"] == "validation_error"


def test_get_analysis_status_not_found(client):
    response = client.get("/analyze/not-found")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_get_analysis_status_processing(client):
    create_analysis_job(status="processing")

    response = client.get("/analyze/job-an-1")

    assert response.status_code == 200
    assert response.get_json()["status"] == "processing"


def test_get_analysis_results_processing_returns_conflict(client):
    create_analysis_job(status="processing")

    response = client.get("/analyze/job-an-1/results")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "conflict"


def test_get_analysis_results_failed_returns_reason(client):
    create_analysis_job(status="failed", error_message="scan failed")

    response = client.get("/analyze/job-an-1/results")
    body = response.get_json()

    assert response.status_code == 409
    assert body["error"]["code"] == "conflict"
    assert "Job failed:" in body["error"]["details"][0]["message"]


def test_get_analysis_results_completed_with_pagination(client):
    stats = {f"token{i}": i for i in range(1, 6)}
    create_analysis_job(status="completed", statistics=stats)

    response = client.get("/analyze/job-an-1/results?limit=2&offset=1")
    body = response.get_json()

    assert response.status_code == 200
    assert body["total"] == 5
    assert len(body["statistics"]) == 2
    assert body["csv_download_url"].endswith("/results/download")


def test_analyze_results_limit_is_capped_to_100(client):
    stats = {f"token{i:03d}": i for i in range(120)}
    create_analysis_job(status="completed", statistics=stats)

    response = client.get("/analyze/job-an-1/results?limit=1000&offset=0")
    body = response.get_json()

    assert response.status_code == 200
    assert len(body["statistics"]) == 100


def test_request_id_header_is_propagated_on_error(client):
    req_id = "req-an-1"
    response = client.post(
        "/analyze/",
        data={},
        content_type="multipart/form-data",
        headers={"X-Request-ID": req_id},
    )
    body = response.get_json()

    assert response.status_code == 400
    assert response.headers.get("X-Request-ID") == req_id
    assert body["request_id"] == req_id
