from multiprocessing import Pool, Process, TimeoutError
import multiprocessing
from flask import abort

from . import queue
from .extraction_service import ExtractionService

extraction_service = ExtractionService()

def worker(queue):
    while True:
        task = queue.get()
        if task is None:
            break

        job_id, file_path, pattern = task
        extraction_service.extract_task(job_id, file_path, pattern)

    return ""

def set_worker(num_processes=4):
    processes = []

    for _ in range(num_processes):
        p = Process(target=worker, args=(queue,))
        p.start()
        processes.append(p)

    return processes
