import os
import shutil


def save_file(file, save_dir):
    os.makedirs(save_dir, exist_ok=True)

    filename = file.filename
    if not filename:
        raise ValueError("Invalid file name")
    file_path = os.path.join(save_dir, filename)

    file.save(file_path)
    return file_path


def cleanup(input_path=None):
    if input_path and os.path.isfile(input_path):
        try:
            os.remove(input_path)
        except OSError:
            pass

    if input_path and os.path.isdir(input_path):
        shutil.rmtree(input_path, ignore_errors=True)
