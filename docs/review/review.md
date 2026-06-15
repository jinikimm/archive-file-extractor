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
- .


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
- .

---

### 4. API Routing

**Q. Why use Flask Blueprint? What are alternatives?**

**Answer**
- .

**Action**
- Document design choice and trade-offs vs PSA

**Updates**
- .

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
- N.A

**Updates**
- N.A

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
- .

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
- .

---

### 8. Exception Handling

**Q. Where should exceptions be handled?**

**Answer**
- Service: raise domain exceptions  
- API/ErrorHandler: catch and convert to HTTP response  

**Action**
- Ensure try/catch exists at API boundary

**Updates**
- .
