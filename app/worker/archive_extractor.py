import os
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import zipfile
import tarfile
import glob

from ..error_handler import ArchiveError, ValidationError


def is_archive(file_name):
    return file_name.lower().endswith((".zip", ".tar", ".tar.gz", ".tgz"))

def extract_archive(file_path):
    if not is_archive(file_path):
        raise ValidationError(
            message="Unsupported archive format",
            details=[{"field": "archive", "message": f"Unsupported format: {file_path}"}],
        )

    try:
        extract_dir = os.path.join(os.path.dirname(file_path), f"{os.path.basename(file_path)}_extracted")
        os.makedirs(extract_dir, exist_ok=True)

        file_list = []

        if file_path.endswith(".zip"):
            with zipfile.ZipFile(file_path, "r") as archive:
                archive.extractall(extract_dir)
                
        elif file_path.endswith(".tar.gz") or file_path.endswith(".tar") or file_path.endswith(".tgz"):
            with tarfile.open(file_path, "r:*") as archive:
                members = [member for member in archive.getmembers() if member.isfile()]
                archive.extractall(extract_dir, members=members)

        for fp in glob.glob(os.path.join(extract_dir, "**"), recursive=True):
            if os.path.isfile(fp):
                file_list.append({
                    "full_path": fp,
                    "file_name": os.path.basename(fp),
                    "file_size": os.path.getsize(fp),
                })

    except Exception as e:
        raise ArchiveError(
            message="Archive extraction failed",
            details=[{"field": "archive", "message": f"Failed to extract: {file_path} - {str(e)}"}],
        )

    return file_list     

def extract_all_archives_parrel(file_path, max_depth=10, max_worker=10):
    file_list = []

    with ThreadPoolExecutor(max_workers=max_worker) as pool:
        futures = {pool.submit(extract_archive, file_path): {"file_path": file_path, "depth": 0}}

        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)

            for future in done:
                archive_path, archive_depth = futures.pop(future).values()
                extracted_files = future.result()

                for f in extracted_files:
                    if is_archive(f["file_name"]) and archive_depth < max_depth:
                        futures[pool.submit(extract_archive, f["full_path"])] = {"file_path": f["full_path"], "depth": archive_depth + 1}
                    else:
                        file_list.append(f)
    return file_list
