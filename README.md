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
