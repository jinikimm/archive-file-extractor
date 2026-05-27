import csv
import multiprocessing
import os
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

TOKEN_PATTERN = re.compile(rb"<Tkn\d{3}[A-Z]{5}Tkn>")
ANALYSIS_WORKERS = 4


def _scan_file(file_path):
    try:
        with open(file_path, "rb") as f:
            content = f.read()
    except OSError:
        return Counter()

    tokens = TOKEN_PATTERN.findall(content)
    return Counter(tokens)


def scan_tokens(directory_path, csv_output_path):
    file_paths = []
    
    for root, _, files in os.walk(directory_path):
        for file_name in files:
            file_paths.append(os.path.join(root, file_name))

    rows = []
    statistics = Counter()
    process_context = multiprocessing.get_context("spawn")

    with ProcessPoolExecutor(max_workers=ANALYSIS_WORKERS, mp_context=process_context) as executor:
        counters = executor.map(_scan_file, file_paths)
        for file_path, token_counter in zip(file_paths, counters):
            if not token_counter:
                continue

            rel_path = os.path.relpath(file_path, directory_path)
            for token_bytes, occurrences in token_counter.items():
                token = token_bytes.decode("ascii")
                rows.append((rel_path, token, occurrences))
                statistics[token] += occurrences

    rows.sort(key=lambda item: (item[0], item[2], item[1]))

    os.makedirs(os.path.dirname(csv_output_path), exist_ok=True)
    with open(csv_output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Path", "Token", "Occurrences"])
        writer.writerows(rows)

    return dict(statistics)
