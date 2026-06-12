# Architecture: Archive File Extractor

**Version:** 1.0.1
**Last Updated:** 2026-06-12
**Scenario:** C — Reverse Engineering

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Context](#2-system-context)
3. [Container Architecture](#3-container-architecture)
4. [Component Architecture](#4-component-architecture)
5. [Interface Architecture](#5-interface-architecture)
6. [Data Architecture](#6-data-architecture)
7. [Data Flow](#7-data-flow)
8. [Deployment Architecture](#8-deployment-architecture)
9. [Requirements Traceability](#9-requirements-traceability)
10. [Non-Functional Requirements](#10-non-functional-requirements)
11. [Risks and Mitigations](#11-risks-and-mitigations)
12. [Architecture Decisions](#12-architecture-decisions)

---

## 1. Executive Summary

### 1.1 Documentation Scenario

This document was produced via **Scenario C — Reverse Engineering**.
No prior architecture documentation existed; all sections were inferred from codebase analysis.

### 1.2 System Purpose

**Archive File Extractor** is a Flask REST API service that accepts compressed archive files
(ZIP, TAR, TAR.GZ, TGZ) and performs two independent asynchronous operations:

| Operation | Description |
|---|---|
| **Extraction** | Recursively extracts files from nested archives and persists metadata for files matching a caller-supplied glob pattern |
| **Analysis** | Recursively extracts all files and scans binary content for firmware token patterns (`<TknNNNXXXXXTkn>`), aggregating occurrence statistics and exporting results as CSV |

Both operations follow an **async job pattern**: the API returns `job_id` with HTTP 202 immediately;
callers poll the status endpoint until the job completes or fails.

### 1.3 Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Web Framework | Flask |
| ORM / Migrations | Flask-SQLAlchemy, Flask-Migrate |
| Database | PostgreSQL 15 |
| Concurrency — I/O | `threading.Thread`, `ThreadPoolExecutor` |
| Concurrency — CPU | `ProcessPoolExecutor` (spawn context) |
| Containerization | Docker, docker-compose |

### 1.4 Stakeholders

| Stakeholder | Concern |
|---|---|
| API Consumers | Job submission, status polling, result retrieval |
| Platform Engineers | Deployment, resource management, scalability |
| Security Engineers | Input validation, archive safety, access control |

---

## 2. System Context

### 2.1 Description

The system exposes a REST API to external clients.
Job and result metadata is persisted in a relational database.
Local temporary storage is used as a staging area during job processing; it is cleaned up after each job.

### 2.2 System Context Diagram

See: [system-context-archive-file-extractor.puml](diagrams/system-context-archive-file-extractor.puml)

---

## 3. Container Architecture

### 3.1 Containers

| Container | Technology | Purpose |
|---|---|---|
| `app` | Python 3.11, Flask | REST API, job lifecycle management, concurrent processing |
| `db` | PostgreSQL 15 | Persistent storage for jobs and results |
| Temp Filesystem | Host `/tmp` | Staging area for uploaded archives during processing; cleaned after each job |

### 3.2 Container Diagram

See: [container-archive-file-extractor.puml](diagrams/container-archive-file-extractor.puml)

---

## 4. Component Architecture

### 4.1 Layer Overview

| Layer | Package | Responsibility |
|---|---|---|
| API | `app/api/` | Request parsing, input validation delegation, HTTP response serialization |
| Service | `app/service/` | Job lifecycle orchestration, background thread dispatch |
| Worker | `app/worker/` | CPU/I/O-intensive operations: recursive extraction, token scanning |

Supporting cross-cutting components:

| Component | File | Responsibility |
|---|---|---|
| ErrorHandler | `app/error_handler.py` | Custom exception hierarchy; centralised Flask error handlers |
| RequestLogger | `app/logger.py` | Structured JSON request/response logging; `X-Request-ID` correlation |
| Config | `app/config.py` | Environment-variable–driven configuration |
| ORM Models | `app/model.py` | SQLAlchemy model definitions for three database tables |

### 4.2 Component Diagram

See: [component-archive-file-extractor.puml](diagrams/component-archive-file-extractor.puml)

### 4.3 Applied Architecture Patterns

| Pattern | Applied In | Code Evidence |
|---|---|---|
| Async Job / Polling | ExtractionService, AnalysisService | `app/service/extraction_service.py:103-108`, `app/service/analysis_service.py:64-70` |
| Repository / ORM | All services | `app/model.py:9-65` |
| Blueprint Routing | extraction_api, analyze_api | `app/api/extraction_api.py:6`, `app/api/analyze_api.py:6` |
| Centralised Error Handling | ErrorHandler | `app/error_handler.py:40-85` |
| Correlation ID | RequestLogger | `app/logger.py:9-11` |
| Parallel Fan-out (I/O bound) | ArchiveExtractor | `app/worker/archive_extractor.py:68-94` |
| Parallel Fan-out (CPU bound) | FirmwareAnalyzer | `app/worker/firmware_analyzer.py:44-56` |

---

## 5. Interface Architecture

### 5.1 Extraction API — `/extractions`

| Method | Path | Description | Request | Response |
|---|---|---|---|---|
| `POST` | `/extractions/` | Submit extraction job | `multipart/form-data`: `archive` (file), `pattern` (string, default `*.json`) | `202 {"job_id": "..."}` |
| `GET` | `/extractions/{job_id}` | Poll job status | — | `200 {"status": "processing\|completed\|failed"}` |
| `GET` | `/extractions/{job_id}/results` | List extracted files (paginated) | Query: `limit` (default 10), `offset` (default 0) | `200 {"total": N, "files": [...], "limit": N, "offset": N}` |

**Code evidence:** `app/api/extraction_api.py:10-29`

### 5.2 Analysis API — `/analyze`

| Method | Path | Description | Request | Response |
|---|---|---|---|---|
| `POST` | `/analyze/` | Submit analysis job | `multipart/form-data`: `archive` (file) | `202 {"job_id": "...", "status": "queued"}` |
| `GET` | `/analyze/{job_id}` | Poll job status | — | `200 {"status": "processing\|completed\|failed"}` |
| `GET` | `/analyze/{job_id}/results` | List token statistics (paginated) with CSV download URL | Query: `limit` (default 20, max 100), `offset` (default 0) | `200 {"total": N, "statistics": {...}, "csv_download_url": "http://.../analyze/{job_id}/results/download"}` |
| `GET` | `/analyze/{job_id}/results/download` | Download analysis CSV file as attachment | — | `200` (file download) |

**Code evidence:** `app/api/analyze_api.py:10-32`, `app/service/analysis_service.py:109-124`

### 5.3 Health Check

| Method | Path | Description | Response |
|---|---|---|---|
| `GET` | `/health` | Liveness probe with DB connectivity check | `200 {"status": "ok"}` / `500 {"status": "error"}` |

**Code evidence:** `app/__init__.py:38-43`

### 5.4 Uniform Error Response Schema

All error responses conform to the following structure:

```json
{
  "request_id": "<uuid>",
  "error": {
    "code": "<error_code>",
    "message": "<human-readable message>",
    "details": [{ "field": "...", "message": "..." }]
  }
}
```

| HTTP Status | Code | Trigger |
|---|---|---|
| 400 | `validation_error` | Missing file, invalid pattern, malformed JSON |
| 404 | `not_found` | Job ID does not exist |
| 409 | `conflict` | Results requested before job completes, or job failed |
| 500 | `archive_error` | Archive extraction failure |
| 500 | `internal_error` | Unhandled exception |
| 503 | `database_error` | SQLAlchemy error |

**Code evidence:** `app/error_handler.py:7-85`

---

## 6. Data Architecture

### 6.1 Data Models

| Model | Table | Purpose |
|---|---|---|
| `ExtractionJob` | `jobs` | Tracks extraction job lifecycle and input metadata |
| `File` | `files` | Stores metadata for extracted files that matched the pattern |
| `AnalysisJob` | `analysis_jobs` | Tracks analysis job lifecycle, aggregated token statistics, and CSV output path |

**Code evidence:** `app/model.py:9-65`

### 6.2 Entity Relationship Diagram

See: [erd-archive-file-extractor.puml](diagrams/erd-archive-file-extractor.puml)

### 6.3 Job Status State Machine

See: [state-job-archive-file-extractor.puml](diagrams/state-job-archive-file-extractor.puml)

**Code evidence:** `app/service/extraction_service.py:17-25`, `app/service/extraction_service.py:61-78`

---

## 7. Data Flow

### 7.1 Archive Extraction Flow

See: [seq-extraction-archive-file-extractor.puml](diagrams/seq-extraction-archive-file-extractor.puml)

**Code evidence:** `app/service/extraction_service.py:50-134`

### 7.2 Firmware Analysis Flow

See: [seq-analysis-archive-file-extractor.puml](diagrams/seq-analysis-archive-file-extractor.puml)

**Code evidence:** `app/service/analysis_service.py:27-115`

---

## 8. Deployment Architecture

### 8.1 Description

The system is deployed via Docker Compose with two service containers.
Flask-Migrate runs `flask db upgrade` at container startup before the application accepts requests.
There is no reverse proxy or load balancer in the current configuration.

### 8.2 Deployment Diagram

See: [deployment-archive-file-extractor.puml](diagrams/deployment-archive-file-extractor.puml)

### 8.3 Startup Sequence

1. `db` container starts; PostgreSQL begins accepting connections
2. `app` container starts (`depends_on: db`)
3. `flask db upgrade` applies pending schema migrations
4. `python -m app.main` starts Flask on `0.0.0.0:5000` with `threaded=True`

**Code evidence:** `Dockerfile:11`, `docker-compose.yml:14`

---

## 9. Requirements Traceability

> Requirements are inferred from codebase analysis (Scenario C). No formal requirements document exists.

| ID | Requirement | Architecture Section | Code Evidence |
|---|---|---|---|
| REQ-01 | Accept archive file uploads via REST API | §5 Interface Architecture | `app/api/extraction_api.py:10-13`, `app/api/analyze_api.py:10-12` |
| REQ-02 | Extract files from nested archives matching a glob pattern | §4 Component, §7.1 Data Flow | `app/service/extraction_service.py:55-59`, `app/worker/archive_extractor.py:68-94` |
| REQ-03 | Scan extracted files for firmware token patterns | §4 Component, §7.2 Data Flow | `app/worker/firmware_analyzer.py:8`, `app/worker/firmware_analyzer.py:37-60` |
| REQ-04 | Track job lifecycle (processing → completed / failed) | §6.3 State Machine | `app/model.py:18`, `app/service/extraction_service.py:61-78` |
| REQ-05 | Return paginated extraction and analysis results | §5 Interface Architecture | `app/api/extraction_api.py:22-29`, `app/service/extraction_service.py:119-134` |
| REQ-06 | Expose health check endpoint with DB connectivity verification | §5.3 Health Check | `app/__init__.py:38-43` |
| REQ-07 | Support ZIP, TAR, TAR.GZ, TGZ archive formats | §4 Component | `app/worker/archive_extractor.py:10-11`, `app/worker/archive_extractor.py:31-42` |
| REQ-08 | Persist job and file metadata to a relational database | §6 Data Architecture | `app/model.py:9-65` |
| REQ-09 | Export token analysis results as a CSV file | §7.2 Data Flow | `app/worker/firmware_analyzer.py:11-19`, `app/worker/firmware_analyzer.py:58` |
| REQ-10 | Provide CSV download URL in analysis result payload and support explicit download endpoint | §5.2 Interface Architecture | `app/service/analysis_service.py:122-124`, `app/api/analyze_api.py:29-32` |

---

## 10. Non-Functional Requirements

| ID | NFR | Rationale | Architecture Section | Code Evidence |
|---|---|---|---|---|
| NFR-01 | **Asynchronous processing** — API returns HTTP 202 immediately; processing runs in a daemon background thread | Prevents client timeout on large or deeply nested archives | §7 Data Flow | `app/service/extraction_service.py:103-108` |
| NFR-02 | **Parallel I/O** — Archive extraction uses `ThreadPoolExecutor` (default 10 workers) | Reduces wall-clock time for deeply nested archive trees | §4 Component | `app/worker/archive_extractor.py:68-94` |
| NFR-03 | **Parallel CPU** — Token scanning uses `ProcessPoolExecutor` with `spawn` context (default 10 workers) | Bypasses GIL for CPU-bound regex scanning across many files | §4 Component | `app/worker/firmware_analyzer.py:40-56` |
| NFR-04 | **Structured logging** — Every request logged as JSON with `request_id`, method, path, status, and duration | Enables log aggregation and correlation | §4 Component | `app/logger.py:14-29` |
| NFR-05 | **Request correlation** — `X-Request-ID` header accepted and propagated on every response | Supports end-to-end request tracing across services | §4 Component | `app/logger.py:9-11`, `app/logger.py:28` |
| NFR-06 | **Temp file cleanup** — Work directory removed in `finally` block after job completion or failure | Prevents unbounded disk growth | §7 Data Flow | `app/service/extraction_service.py:80-82` |
| NFR-07 | **Extraction depth limit** — Recursive archive extraction capped at depth 10 | Mitigates resource exhaustion from zip-bomb–style archives | §4 Component | `app/worker/archive_extractor.py:68` |

---

## 11. Risks and Mitigations

| ID | Risk | Severity | Likelihood | Mitigation | Status |
|---|---|---|---|---|---|
| RISK-01 | **No authentication** — All API endpoints are publicly accessible without credentials | High | High | Add API key validation or OAuth2 middleware before routing | Open |
| RISK-02 | **Tarfile path traversal** — `tarfile.extractall()` without `filter='data'` may write files outside the target directory on Python < 3.12 | High | Medium | Pass `filter='data'` to `tarfile.extractall()` (`app/worker/archive_extractor.py:42`) | Open |
| RISK-03 | **Unsanitised upload filename** — `save_file()` uses `file.filename` directly; a crafted filename containing `../` sequences could write outside `save_dir` | Medium | Low | Apply `werkzeug.utils.secure_filename()` before constructing the path in `app/service/utils.py:10` | Open |
| RISK-04 | **Daemon thread job loss** — Background threads are `daemon=True`; if the process exits mid-job the job remains in `status=processing` indefinitely | Medium | Medium | Add startup reconciliation to mark stale `processing` jobs as `failed`, or migrate to a persistent task queue (e.g. Celery + Redis) | Open |
| RISK-05 | **No DB connection pool tuning** — SQLAlchemy default pool may exhaust connections under high concurrency from many parallel threads | Medium | Medium | Set `SQLALCHEMY_ENGINE_OPTIONS` with `pool_size` and `max_overflow` in `app/config.py` | Open |
| RISK-06 | **Ephemeral CSV storage** — CSV results are written to `/tmp`; a container restart deletes files while `csv_path` in the database still references them | Low | Medium | Mount a persistent volume for results, or store CSV content directly in the database | Open |

---

## 12. Architecture Decisions

### ADR-01: In-Process Async with `threading.Thread` Instead of a Task Queue

| Field | Value |
|---|---|
| Status | Accepted |
| Context | Jobs must be processed asynchronously without blocking the HTTP response |
| Decision | Use `threading.Thread(daemon=True)` to process jobs in the background within the same process |
| Rationale | Minimises operational complexity; no additional broker or worker infrastructure required at current scale |
| Consequences | Job state is lost on process restart (see RISK-04). Migration to Celery or equivalent is recommended if durability SLAs are required |
| Evidence | `app/service/extraction_service.py:103-108` |

---

### ADR-02: `ProcessPoolExecutor` with `spawn` Context for Token Scanning

| Field | Value |
|---|---|
| Status | Accepted |
| Context | Token scanning (`re.findall` over binary file content) is CPU-bound and contended by the GIL when threaded |
| Decision | Use `ProcessPoolExecutor` with `mp_context=multiprocessing.get_context("spawn")` |
| Rationale | `spawn` avoids forking the Flask application context into child processes, preventing SQLAlchemy session corruption |
| Evidence | `app/worker/firmware_analyzer.py:40-46` |

---

### ADR-03: `ThreadPoolExecutor` with Dynamic Future Scheduling for Recursive Extraction

| Field | Value |
|---|---|
| Status | Accepted |
| Context | Recursive extraction requires dynamically submitting new extraction tasks as nested archives are discovered |
| Decision | Use a `while futures` loop with `wait(FIRST_COMPLETED)` to fan out sub-archive extraction as archives are found |
| Rationale | Threads are sufficient for I/O-bound disk operations and share memory, avoiding spawn overhead |
| Evidence | `app/worker/archive_extractor.py:68-94` |

---

### ADR-04: JSON-in-TEXT Column for Token Statistics

| Field | Value |
|---|---|
| Status | Accepted |
| Context | Token statistics are a variable-length `dict[str, int]` |
| Decision | Serialise and store as a JSON string in the `TEXT` column `analysis_jobs.statistics` |
| Rationale | Avoids a separate normalised table for a flexible key-value structure with no foreign-key query requirements |
| Consequences | Token-level queries require application-side deserialisation; no SQL-level aggregation possible |
| Evidence | `app/model.py:64`, `app/service/analysis_service.py:104` |
