from concurrent.futures import ThreadPoolExecutor
import logging

from . import queue
from .extraction_service import ExtractionService

extraction_service = ExtractionService()
executor = None

def worker(app, queue):
    with app.app_context():
        while True:
            task = queue.get()
            if task is None:
                queue.task_done()
                break

            job_id = None
            file_path = None
            task_dir = None
            try:
                job_id, file_path, pattern, depth = task
                task_dir = extraction_service.extract_task(job_id, file_path, pattern, depth)
            except Exception:
                logging.exception("Worker task failed")
            finally:
                extraction_service.cleanup(job_id, task_dir, file_path)
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
