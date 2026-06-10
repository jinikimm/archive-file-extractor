# archive-file-extractor

Flask app that provides two services in one API:
- **Archive File Extractor** service: recursively extracts nested archives and returns matched files.
- **Firmware Analyzer** service: scans extracted files for token patterns and returns aggregated statistics.

## Service boundary

This repository implements two independent requirement tracks in a single Flask app.

| Track | Purpose | Endpoint prefix | Main output |
|---|---|---|---|
| Archive File Extractor | Extract nested archives and filter files by pattern | /extractions | matched file list |
| Firmware Analyzer | Scan extracted files for token pattern frequency | /analyze | token statistics + csv path |

Shared runtime components:
- same Flask process
- same DB and migration set
- same error/structured logging model

Service-specific behavior:
- Extractor requires pattern input and returns file metadata.
- Analyzer does token scanning and returns aggregated counters.

## 1) Build and run locally

Prerequisites:
- Python 3.11+
- PostgreSQL 15+

Install and run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# optional but recommended for flask cli
export FLASK_APP=app:create_app

# run API
python -m app.main
```

Default API port: 5000

## 2) Run with Docker / docker-compose
docker-compose (db + app):

```bash
docker compose up --build app db
```

compose app startup command runs DB migration first:
- flask db upgrade
- python -m app.main

### Example usage

Archive File Extractor service:

```bash
curl -X POST http://localhost:5000/extractions/ \
-F "archive=@./sample.zip" \
-F "pattern=*.json"

curl http://localhost:5000/extractions/<job_id>

curl "http://localhost:5000/extractions/<job_id>/results?limit=20&offset=0"
```

Firmware Analyzer service:

```bash

curl -X POST http://localhost:5000/analyze/ \
-F "archive=@./sample.zip"

curl http://localhost:5000/analyze/<job_id>

curl "http://localhost:5000/analyze/<job_id>/results?limit=20&offset=0"
```

## 3) Required environment variables and defaults

Variables used by app:
- DB_HOST: localhost
- DB_PORT: 5434
- DB_NAME: testdb
- DB_USER: testuser
- DB_PASSWORD: test
- PORT: 5000

In docker-compose, DB_HOST is set to db and DB_PORT is set to 5432.

## 4) Database setup / migration

This project uses Flask-Migrate (Alembic), and migration files are included in this repo.

Apply schema:

```bash
export FLASK_APP=app:create_app
flask db upgrade
```

If you only need quick local testing, tests use in-memory SQLite and do not require PostgreSQL.

## 5) Run tests

#### Functional tests are in tests/api_test/.

To run functional tests:

```bash
docker compose run --rm test pytest tests/api_test/
```

#### Live integration tests are in tests/integration_test/.

To run live integration tests:

```bash
docker compose run --rm test pytest tests/integration_test/
```

## 6) Job and result matching explanation

### 6-A) Archive File Extractor
- job key: job_id
- result association: job_id + full_path
- result payload: files[] with full_path, file_name, file_size, source_archive_name, nesting_depth

### 6-B) Firmware Analyzer
- job key: job_id
- result association: job_id
- result payload: statistics{} and csv_path

### Common behavior
- unknown job_id: rejected with 404
- results requested while processing: rejected with 409
- results requested for failed job: rejected with 409 and failure reason
- results requested for completed job: returns paged data

## 7) Job lifecycle and asynchronous behavior

### 7-A) Archive File Extractor lifecycle
- submit: POST /extractions/ with archive + pattern
- status: GET /extractions/{job_id}
- results: GET /extractions/{job_id}/results?limit=&offset=
- background execution: recursive archive extraction in worker threads

### 7-B) Firmware Analyzer lifecycle
- submit: POST /analyze/ with archive
- status: GET /analyze/{job_id}
- results: GET /analyze/{job_id}/results?limit=&offset=
- background execution: extraction + token scanning in process pool
- results limit: capped to 100

### Shared lifecycle properties
- asynchronous response on submit (202)
- terminal status is completed or failed
- temporary work directory cleanup after job completion/failure

## 8) Assumptions and shortcuts

- Single service process; asynchronous jobs are handled by in-process threads.
- Supported archive formats are zip, tar, tar.gz, and tgz.
- Extraction records only final non-archive files from recursive traversal.
- Analysis token pattern is fixed to <Tkn###AAAAATkn> byte format.
- Request-level structured logging includes request_id and job lifecycle events.

## 9) Improvements with more time
- OpenAPI / Swagger specification.

## 10) Updates in this iteration

- Added structured error response shape with request_id.
- Added request/response logging with X-Request-ID propagation.
- Added job-level structured logs: job_submitted, job_started, job_completed, job_failed.
- Added archive error handling for corrupt/unsupported archive inputs.
- Added functional API tests for extraction and analyze endpoints.
- Added live integration API tests for running environment.
