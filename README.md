# Archive Extractor Service

## Operating Model

```mermaid
flowchart LR
	C[Client] --> S[Service API]
	S --> Q[(In-memory Queue)]
	Q --> W1[Worker 1]
	Q --> W2[Worker 2]
	Q --> Wn[Worker N]

	S --> DB[(DB: jobs/files)]
	S --> FS[(Filesystem: temp files)]

	W1 --> DB
	W2 --> DB
	Wn --> DB

	W1 --> FS
	W2 --> FS
	Wn --> FS
```

The service receives requests, stores job state in DB, and pushes extraction tasks to an in-memory queue.
Workers consume tasks concurrently, write results to DB, and use temporary files on the filesystem.

## Architecture

```mermaid
flowchart TD
	Client[Client]
	API[Flask API]
	Q[(In-memory Queue)]
	W[ThreadPool Worker]
	ES[ExtractionService]
	AS[AnalysisService]
	TS[Token Scanner - ProcessPool]
	DB[(PostgreSQL)]
	FS[(Temp Filesystem)]

	Client --> API
	API --> DB
	API --> Q

	Q --> W

	W --> ES
	W --> AS

	ES --> DB
	ES --> FS

	AS --> ES
	AS --> TS
	AS --> DB
	AS --> FS

	TS --> FS
```

### Key points

- Queue is used as a trigger for background jobs.
- Extraction job is enqueued once, then fully processed in one worker flow.
- Nested archive traversal logic is centralized in `ExtractionService.extract_all_archives` and reused by analysis.
- Token scan runs in process pool (`spawn`) inside token scanner.

## Extraction Request Flow

```mermaid
sequenceDiagram
	participant C as Client
	participant API as /extractions
	participant DB as jobs/files
	participant Q as Queue
	participant W as Worker
	participant ES as ExtractionService

	C->>API: POST /extractions (archive, pattern)
	API->>ES: save_file()
	API->>DB: create ExtractionJob(status=pending)
	API->>Q: enqueue extraction task (once)
	API-->>C: 202 {job_id}

	Q->>W: consume task
	W->>ES: extract_task(job_id, file_path, pattern)
	ES->>DB: status -> running
	ES->>ES: extract_all_archives()\n(single-thread full traversal)
	ES->>DB: insert matched files
	ES->>DB: status -> completed
```

### Extraction behavior

- No recursive re-enqueue for nested archives.
- Nested archives are processed inside one worker task.
- Job status updates are persisted as `pending -> running -> completed` (or `failed`).

## Analysis Request Flow

```mermaid
sequenceDiagram
	participant C as Client
	participant API as /analyze
	participant DB as analysis_jobs
	participant Q as Queue
	participant W as Worker
	participant AS as AnalysisService
	participant ES as ExtractionService
	participant TS as TokenScanner

	C->>API: POST /analyze (archive)
	API->>AS: save_file()
	API->>DB: create AnalysisJob(status=queued)
	API->>Q: enqueue analyze task
	API-->>C: 202 {job_id, status=queued}

	Q->>W: consume analyze task
	W->>AS: analyze_task(job_id, file_path)
	AS->>DB: status -> running
	AS->>ES: extract_all_archives(file_path, analysis_job_id)
	AS->>TS: scan_tokens(extract_dir, csv_path)
	AS->>DB: save statistics/csv_path\nstatus -> done
```

### Analysis behavior

- Analysis reuses extraction traversal module (`extract_all_archives`) rather than duplicating archive traversal logic.
- Token counting is parallelized in process pool, while API/worker flow remains synchronous per task.
