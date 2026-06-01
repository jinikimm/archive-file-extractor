import io
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        from app.model import db

        db.create_all()
        yield app.test_client()

        from app import queue
        from app.worker.worker import executor

        for _ in range(4):
            queue.put(None)
        executor.shutdown(wait=True)


def test_extraction_post_and_status(client):
    data = {
        "archive": (io.BytesIO(b"dummydata"), "test.zip"),
        "pattern": "*.json",
    }
    response = client.post("/extractions/", data=data, content_type="multipart/form-data")

    assert response.status_code == 202

    job_id = response.get_json()["job_id"]
    status_response = client.get(f"/extractions/{job_id}")

    assert status_response.status_code == 200
    assert "status" in status_response.get_json()

    # # polling for actual test data
    # for _ in range(100):
    #     status_response = client.get(f"/extractions/{job_id}")
    #     status = status_response.get_json()["status"]

    #     if status == "completed":
    #         break

    #     time.sleep(0.2)


def test_extraction_results_before_completed(client):
    data = {
        "archive": (io.BytesIO(b"dummydata"), "test.zip"),
        "pattern": "*.json",
    }
    response = client.post("/extractions/", data=data, content_type="multipart/form-data")

    job_id = response.get_json()["job_id"]
    results_response = client.get(f"/extractions/{job_id}/results")

    assert results_response.status_code in (400, 404)


def test_extraction_results_after_completed(client):
    data = {
        "archive": (io.BytesIO(b"dummydata"), "test.zip"),
        "pattern": "*.json",
    }
    response = client.post("/extractions/", data=data, content_type="multipart/form-data")

    job_id = response.get_json()["job_id"]

    from app.model import db, ExtractionJob, File

    job = ExtractionJob.query.get(job_id)
    job.status = "completed"

    files = [
        File(
            full_path=f"extracted/file{i}.json",
            file_name=f"file{i}.json",
            file_size=1000 + i,
            source_archive_name="test.zip",
            nesting_depth=1,
            job_id=job_id,
        )
        for i in range(5)
    ]
    db.session.add_all(files)
    db.session.commit()

    for i in range(2):
        response = client.get(f"/extractions/{job_id}/results?limit=3&offset={i*3}")

        assert response.status_code == 200
        results_data = response.get_json()
        assert results_data["total"] == 5
        assert len(results_data["files"]) == 3 if i < 1 else 2

    response = client.get(f"/extractions/{job_id}/results")
    assert response.status_code == 200
    results_data = response.get_json()
    assert results_data["total"] == 5
    assert len(results_data["files"]) == 5


def test_extraction_missing_fields(client):
    response = client.post("/extractions/", data={}, content_type="multipart/form-data")
    assert response.status_code == 400

    data = {"archive": (io.BytesIO(b"dummydata"), "test.zip")}
    response_missing_pattern = client.post(
        "/extractions/", data=data, content_type="multipart/form-data"
    )
    assert response_missing_pattern.status_code == 400


def test_extraction_delete_not_implemented(client):
    data = {
        "archive": (io.BytesIO(b"dummydata"), "test.zip"),
        "pattern": "*.json",
    }
    response = client.post("/extractions/", data=data, content_type="multipart/form-data")

    job_id = response.get_json()["job_id"]
    delete_response = client.delete(f"/extractions/{job_id}")

    assert delete_response.status_code == 204
