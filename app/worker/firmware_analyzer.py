import csv
import multiprocessing
import os
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

TOKEN_PATTERN = re.compile(rb"<Tkn\d{3}[A-Z]{5}Tkn>")


def save_csv(rows, csv_output_path):
    rows.sort(key=lambda item: (item[0], item[2], item[1]))

    os.makedirs(os.path.dirname(csv_output_path), exist_ok=True)
    with open(csv_output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Path", "Token", "Occurrences"])
        writer.writerows(rows)


def get_analysis_csv_path(analysis_job_id):
    return os.path.join("/tmp/analysis/results", f"analysis_{analysis_job_id}.csv")


def scan_token(file_path):
    try:
        with open(file_path, "rb") as f:
            content = f.read()
    except OSError as e:
        raise RuntimeError(f"Failed to analyze file: {file_path} - {str(e)}")

    tokens = TOKEN_PATTERN.findall(content)
    return Counter(tokens)


def firmware_analyzer(file_list, root_dir, csv_output_path, max_workers=10):
    rows = []
    statistics = Counter()
    process_context = multiprocessing.get_context("spawn")

    file_paths = [f["full_path"] for f in file_list]

    with ProcessPoolExecutor(
        max_workers=max_workers, mp_context=process_context
    ) as executor:
        counters = executor.map(scan_token, file_paths)
        for file_path, token_counter in zip(file_paths, counters):
            if not token_counter:
                continue

            rel_path = os.path.relpath(file_path, root_dir)
            for token_bytes, occurrences in token_counter.items():
                token = token_bytes.decode("ascii")
                rows.append((rel_path, token, occurrences))
                statistics[token] += occurrences

    save_csv(rows, csv_output_path)

    return dict(statistics)
