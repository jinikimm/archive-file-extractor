import io
import pytest


@pytest.fixture
def client():
    from app import create_app
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})

    with app.app_context():
        from app.model import db

        db.create_all()
        yield app.test_client()

        from app import queue
        from app.worker import worker
        for _ in range(4):
            queue.put(None)
        worker.executor.shutdown()

def test_create_analysis_job(client):
    data = {"archive": (io.BytesIO(b"dummydata"), "test.zip")}

    response = client.post("/analyze/", data=data, content_type="multipart/form-data")
    response_data = response.get_json()

    assert response.status_code == 202
    assert "job_id" in response_data
    assert response_data["status"] == "queued"

def test_analyze_post_and_status(client):
    data = {"archive": (io.BytesIO(b"dummydata"), "test.zip")}
    response = client.post("/analyze/", data=data, content_type="multipart/form-data")

    assert response.status_code == 202

    job_id = response.get_json()["job_id"]
    status_response = client.get(f"/analyze/{job_id}")

    assert status_response.status_code == 200
    assert "status" in status_response.get_json()


def test_analyze_results_before_completed(client):
    data = {"archive": (io.BytesIO(b"dummydata"), "test.zip")}
    response = client.post("/analyze/", data=data, content_type="multipart/form-data")

    job_id = response.get_json()["job_id"]
    results_response = client.get(f"/analyze/{job_id}/results")

    assert results_response.status_code in (400, 404)


def test_analyze_missing_file(client):
    response = client.post("/analyze/", data={}, content_type="multipart/form-data")
    assert response.status_code == 400


def test_analyze_results_after_completed(client):
    data = {"archive": (io.BytesIO(b"dummydata"), "test.zip")}
    response = client.post("/analyze/", data=data, content_type="multipart/form-data")

    job_id = response.get_json()["job_id"]

    from app.model import db, AnalysisJob
    job = AnalysisJob.query.get(job_id)
    job.status = "completed"
    job.statistics = '{"token0": 10, "token1": 11, "token2": 12, "token3": 13, "token4": 14}'
    db.session.commit()

    for i in range(2):
        response = client.get(f"/analyze/{job_id}/results?limit=3&offset={i*3}")
        assert response.status_code == 200

        results_data = response.get_json()
        assert results_data["total"] == 5
        assert len(results_data["statistics"]) == 3 if i < 1 else 2

    response = client.get(f"/analyze/{job_id}/results")
    assert response.status_code == 200

    results_data = response.get_json()
    assert results_data["total"] ==5
    assert results_data["statistics"] == {"token0": 10, "token1": 11, "token2": 12, "token3": 13, "token4": 14}