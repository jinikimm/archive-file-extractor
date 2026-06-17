import json
import os
import time
from io import BytesIO
from urllib import error, request
from uuid import uuid4

import pytest


def _http_multipart(base_url, path, fields, headers=None):
    boundary = uuid4().hex
    body_parts = []

    for name, value in fields.items():
        if isinstance(value, tuple):
            filename, data = value
            body_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n"
            )
            body_parts.append(data if isinstance(data, bytes) else data.encode())
            body_parts.append(b"\r\n")
        else:
            body_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            )

    body_parts.append(f"--{boundary}--\r\n")
    body = b"".join(p if isinstance(p, bytes) else p.encode() for p in body_parts)

    req_headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if headers:
        req_headers.update(headers)

    req = request.Request(
        url=f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=req_headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            body_resp = resp.read().decode("utf-8")
            return resp.status, json.loads(body_resp) if body_resp else {}
    except error.HTTPError as e:
        body_resp = e.read().decode("utf-8")
        return e.code, json.loads(body_resp) if body_resp else {}


def _http_json(method, base_url, path, headers=None):
    req_headers = {}
    if headers:
        req_headers.update(headers)

    req = request.Request(
        url=f"{base_url.rstrip('/')}{path}",
        headers=req_headers,
        method=method,
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, json.loads(body) if body else {}


def _make_zip_bytes():
    import zipfile

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.json", '{"key": "value"}')
        zf.writestr("readme.txt", "hello")
    buf.seek(0)
    return buf.read()


def _submit_analysis(base_url, filename, payload, headers=None):
    return _http_multipart(
        base_url,
        "/analysis/",
        {"archive": (filename, payload)},
        headers=headers,
    )


def _poll_status(base_url, job_id, timeout=10.0, interval=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, body = _http_json("GET", base_url, f"/analysis/{job_id}")
        assert status == 200
        if body.get("status") in ("completed", "failed"):
            return body.get("status"), body
        time.sleep(interval)
    return None, {}


@pytest.fixture
def base_url():
    url = os.getenv("INTEGRATION_BASE_URL", "http://localhost:5000")
    try:
        status, _ = _http_json("GET", url, "/health")
    except Exception:
        pytest.skip(f"Live app is not reachable at {url}")

    if status != 200:
        pytest.skip(f"Live app health check failed at {url}")

    return url


def test_live_health_check(base_url):
    status, body = _http_json("GET", base_url, "/health")
    assert status == 200
    assert body["status"] == "ok"


def test_live_analysis_submit_returns_202_and_job_id(base_url):
    status, body = _submit_analysis(base_url, "sample.zip", _make_zip_bytes())

    assert status == 202
    assert "job_id" in body
    assert body.get("status") == "queued"


def test_live_analysis_submit_and_poll_status(base_url):
    status, body = _submit_analysis(base_url, "sample.zip", _make_zip_bytes())
    assert status == 202
    job_id = body["job_id"]

    final_status, _ = _poll_status(base_url, job_id)

    assert final_status in ("completed", "failed")


def test_live_analysis_results_after_completed(base_url):
    status, body = _submit_analysis(base_url, "sample.zip", _make_zip_bytes())
    assert status == 202
    job_id = body["job_id"]

    final_status, _ = _poll_status(base_url, job_id)

    rs, rb = _http_json("GET", base_url, f"/analysis/{job_id}/results")
    if final_status == "completed":
        assert rs == 200
        assert "statistics" in rb
        assert "total" in rb
        assert "csv_download_url" in rb
    else:
        assert rs == 409
        assert rb["error"]["code"] == "conflict"
        assert "Job failed:" in rb["error"]["details"][0]["message"]


def test_live_analysis_results_pagination(base_url):
    status, body = _submit_analysis(base_url, "sample.zip", _make_zip_bytes())
    assert status == 202
    job_id = body["job_id"]

    final_status, _ = _poll_status(base_url, job_id)
    assert final_status == "completed", f"Expected completed, got {final_status}"

    rs, rb = _http_json("GET", base_url, f"/analysis/{job_id}/results?limit=1&offset=0")

    assert rs == 200
    assert len(rb["statistics"]) <= 1


def test_live_analysis_results_limit_capped_to_100(base_url):
    status, body = _submit_analysis(base_url, "sample.zip", _make_zip_bytes())
    assert status == 202
    job_id = body["job_id"]

    final_status, _ = _poll_status(base_url, job_id)
    assert final_status == "completed", f"Expected completed, got {final_status}"

    rs, rb = _http_json(
        "GET", base_url, f"/analysis/{job_id}/results?limit=9999&offset=0"
    )

    assert rs == 200
    assert len(rb["statistics"]) <= 100


def test_live_analysis_results_while_processing_returns_conflict(base_url):
    status, body = _submit_analysis(base_url, "sample.zip", _make_zip_bytes())
    assert status == 202
    job_id = body["job_id"]

    # 제출 직후 즉시 조회 — processing 상태일 가능성 높음
    rs, rb = _http_json("GET", base_url, f"/analysis/{job_id}/results")

    assert rs in (200, 409)
    if rs == 409:
        assert rb["error"]["code"] == "conflict"


def test_live_analysis_missing_file_returns_validation_error(base_url):
    boundary = uuid4().hex
    body = f"--{boundary}--\r\n".encode()

    req = request.Request(
        url=f"{base_url.rstrip('/')}/analysis/",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            status = resp.status
            rb = json.loads(resp.read().decode())
    except error.HTTPError as e:
        status = e.code
        rb = json.loads(e.read().decode())

    assert status == 400
    assert rb["error"]["code"] == "validation_error"


def test_live_analysis_job_not_found(base_url):
    status, body = _http_json("GET", base_url, "/analysis/non-existent-job-id")

    assert status == 404
    assert body["error"]["code"] == "not_found"


def test_live_analysis_results_not_found(base_url):
    status, body = _http_json("GET", base_url, "/analysis/non-existent-job-id/results")

    assert status == 404
    assert body["error"]["code"] == "not_found"


def test_live_analysis_request_id_propagation(base_url):
    req_id = f"live-req-{uuid4().hex[:8]}"
    boundary = uuid4().hex
    body = f"--{boundary}--\r\n".encode()

    req = request.Request(
        url=f"{base_url.rstrip('/')}/analysis/",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Request-ID": req_id,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            status = resp.status
            rb = json.loads(resp.read().decode())
            resp_req_id = resp.headers.get("X-Request-ID")
    except error.HTTPError as e:
        status = e.code
        rb = json.loads(e.read().decode())
        resp_req_id = e.headers.get("X-Request-ID")

    assert status == 400
    assert resp_req_id == req_id
    assert rb["request_id"] == req_id
