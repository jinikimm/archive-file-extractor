from concurrent.futures import ThreadPoolExecutor
import logging

from .. import queue
from ..service.analysis_service import AnalysisService
from ..service.extraction_service import ExtractionService

extraction_service = ExtractionService()
analysis_service = AnalysisService()
executor = None

def worker(app, queue):
    with app.app_context():
        while True:
            task = queue.get()
            if task is None:
                queue.task_done()
                break

            file_path = None
            task_dir = None
            try:
                job_type = task.get("job_type")
                job_id = task.get("job_id")
                file_path = task.get("file_path")
                pattern = task.get("pattern", "json")

                if job_type == "analyze":
                    task_dir = analysis_service.analyze_task(job_id, file_path)
                else:
                    task_dir = extraction_service.extract_task(job_id, file_path, pattern)
            except Exception:
                extraction_service.cleanup(task_dir)
                logging.exception("Worker task failed")
            finally:
                extraction_service.cleanup(file_path)
                queue.task_done()

    return ""

def set_worker(app, num_workers=4):
    global executor
    if executor is not None:
        return executor

    executor = ThreadPoolExecutor(max_workers=num_workers)

    for _ in range(num_workers):
        executor.submit(worker, app, queue)

    return executor
