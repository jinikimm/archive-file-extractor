## Review Summary

| Summary of review feedback with clear actions and update tracking.


----

### 260612-Update

---

### 1. Docker Usage

**Q. When should Dockerfile vs docker-compose.yml be used?**

**Answer**
- `Dockerfile`: Build a single service image and esure reproducible runtime (local/CI)
- `docker-compose.yml`: Run multi-component environments (API, DB, worker) locally

**Action**
- Add usage explanation to README

**Updates**
- Added the usage of docker/docker-compose to README.md
    (https://github.com/jinikimm/archive-file-extractor#2-run-with-docker--docker-compose)


---

### 2. App Directory Layout

**Q. Why was this /app structure chosen? Why no subdirectories for model/config/error/logger?**

**Q. How does this project relate to PSA architecture?**

**Answer**
- Each currently exists as a single file → avoided premature directory splitting
- Plan to refactor into directories when file count increases

**Action**
- Update /app structure by refering to the PSA structure
- Document mapping between current structure and PSA Level 1

    (PSA)
    Each domain follows a standard microservice pattern:
    - `<Domain>Microservice/` — Flask HTTP service extending Foundation/Microservice base
    - `<Domain>MicroserviceClient/` — Python client library for inter-service calls
    - `<Domain>MicroserviceAPIDefinitions/` — Shared endpoint constant definitions
    - `<Domain>MicroserviceEvents/` — RabbitMQ event definitions
    - `<Domain>Worker/` — Background job worker (Kubernetes Job)
    - `<Domain>Db/` — Domain-specific database schema
    - `<Domain>MicroserviceUnitTests/` — Unit tests (separate Poetry environment)

**Updates**
- https://github.com/jinikimm/archive-file-extractor/commit/346eb96a7542031b736342e242ea20de06b45ce3

  (updated layout)
  - `service/` — Business logic implementation
  - `api/` — HTTP request/response handling
  - `worker/` — Background async processing
  - `db/` — Domain data models
  - `__init__.py`
  - `config.py` — Global configuration
  - `error_handler.py` — Exception handling
  - `logger.py` — Logging initialization
  - `main.py`

---

### 4. API Routing

**Q. Why use Flask Blueprint? What are alternatives?**

**Answer**
- Blueprint is used to modularize and group routes, and here it is combined with API classes to centralize routing logic.

**Action**
- Refactor API routing by adopting PSA's class-based API pattern with centralized route registration.

**Updates**
- [app/api/](https://github.com/jinikimm/archive-file-extractor/tree/main/app/api) ([7aef121
](https://github.com/jinikimm/archive-file-extractor/commit/7aef1210e114172f92fda786c34f8b3b4bcdcb86) ) : Refactored API routing to class-based structure with centralized add_url_rules() registration.

---

### 5. Input Validation

**Q. How are client inputs validated?**

**Answer**
- Controller: basic validation
- Service: domain validation
  - archive existence
  - file type
  - job_id validation
- ErrorHandler: converts exceptions → HTTP response

**Action**
- Add input validation for pagination value

**Updates**
- [app/api/extraction_api.py](app/api/extraction_api.py), [app/api/analyze_api.py](app/api/analyze_api.py):  Add input validation for pagination
- [docs/api/swagger.yaml](docs/api/swagger.yaml): Add detailed error scenario and reponse examples to all endpoints

---

### 6. Job Response Design

**Q. Should API always return status=queued?**

**Answer**
- No
- Response should reflect actual job submission result
- Return structured job/result object instead

**Action**
- Modify `submit_*_job` to return status-aware response

**Updates**
- [4c71a3710e3a5f756de676f95e037fb3d3aa4972](https://github.com/jinikimm/archive-file-extractor/commit/4c71a3710e3a5f756de676f95e037fb3d3aa4972)

---

### 7. Scenario Flow

**Q. What is the full request-processing flow?**

**Answer (Simplified)**

1. Client sends archive + pattern  
2. Validate input  
3. Store file  
4. Extract or dispatch to worker  
5. Return `202 Accepted` with `{job_id, status=pending}`  
6. Client polls or subscribes  
7. State transition: `pending → running → completed/failed`  
8. Result request validates job_id and state  

**Abnormal Cases**
- Missing archive  
- Unsupported format  
- Storage failure  
- Extraction failure  
- Worker failure  
- Invalid job_id  

**Action**
- Expand into detailed scenario documentation
- Update additional detailed exception handling

**Updates**
- [docs/api/swagger.yaml](docs/api/swagger.yaml): Add detailed error scenario and reponse examples to all endpoints

---

### 8. Exception Handling

**Q. Where should exceptions be handled?**

**Answer**
- Service: raise domain exceptions  
- API/ErrorHandler: catch and convert to HTTP response  

**Action**
- Ensure try/catch exists at API boundary

**Updates**
- [app/api/extraction_api.py](app/api/extraction_api.py), [app/api/analyze_api.py](app/api/analyze_api.py): Add try/catch for exception handling at API boundary
- [app/service/extraction_service.py](app/service/extraction_service.py), [app/service/analysis_service.py](app/service/analysis_service.py): Add exception handling for database commits
- [docs/api/swagger.yaml](docs/api/swagger.yaml): Define error response schemas (400, 404, 500, 503) for each endpoint



---

### 260615-Update

---


### 9. File Storage & Cleanup Policy

**Q.** Where are uploaded files and extracted files stored? Are they managed permanently or cleaned up under specific conditions? How should this be managed?

**Answer**
- All temporary files are cleaned up after job completion (success or failure)
- Storage location: `/tmp/{service}/{job_id}/` (service = "extract" or "analysis")
- Job metadata persists in database (status, statistics JSON, CSV path reference)
- No permanent file storage; cleanup() called in finally block guarantees cleanup even on exceptions

**Action**
- N.A

**Updates**
- N.A

---

### 10. API Response Design by Job Status

**Q.** What should GET {extractions/analyses}/{job_id} response look like across different statuses and success/failure cases?

**Answer**

Job status: `queued` → `processing` → `completed` / `failed`

Response by status:
- **queued**:  `{status}`
- **processing**:  `{status}`
- **completed (HTTP 200)**: `{status}`
- **failed (HTTP varies by exception)**: `{status}`
- **not found (HTTP 404)**: `{error: {code, message, job_id}}`

HTTP status codes:
- 200: queued, processing, completed, failed (actual status in response)
- 400: Invalid input (missing file/pattern)
- 404: Job not found
- 500: Processing error (extraction/analysis/shutdown interrupted)

**Action**
- Update API documentation with complete response schemas
- Add HTTP status code reference table

**Updates**
- [app/service/extraction_service.py](app/service/extraction_service.py), [app/service/analysis_service.py](app/service/analysis_service.py): Updated to return responses based on actual job status
- [app/api/extraction_api.py](app/api/extraction_api.py), [app/api/analyze_api.py](app/api/analyze_api.py): Applied actual status codes based on job state
- [docs/api/swagger.yaml](docs/api/swagger.yaml): Added complete response schemas and examples

---

### 11. API Endpoint Naming Convention

**Q.** What naming rule should be followed? extractions(plural) vs analyze(verbs)?

**Answer**
- **Chosen pattern**: RESTful noun-based naming
  -  POST /extractions → Submit extraction job
  -  GET /extractions/{job_id} → Retrieve extraction job status
  -  POST /analysis → Submit analysis job
  -  GET /analysis/{job_id} → Retrieve analysis job status

- **Avoid**: Verb-based naming
  -  POST /extract
  -  POST /analyze
  -  GET /get_job_status

Current Status: Naming not yet unified (extraction_api uses /extractions ✓, analyze_api uses /analyze ✗)

**Action**
- Standardize all API endpoints to noun-based plural form
- Update analyze_api.py to use /analyses instead of /analyze
- Update all client code references

**Updates**
- [app/api/__init__.py](https://github.com/jinikimm/archive-file-extractor/blob/main/app/api/__init__.py) ([9be668d](https://github.com/jinikimm/archive-file-extractor/commit/9be668dff9917829a060cb00b70f2055d834b99e) ) : change api prefix from analyze to analysis for consistency

---
