import os
import re


def normalize_image_filename(filename):
    if not filename:
        return ""
    if not filename.lower().endswith((".png", ".jpeg", ".jpg")):
        return f"{filename}.png"
    return filename


def sanitize_note_filename(name):
    if not name:
        return ""
    sanitized = re.sub(r'[\\/:*?"<>|]+', " ", str(name))
    sanitized = re.sub(r"\s+", " ", sanitized).strip().strip(".")
    return sanitized


def build_note_filename(data, source_filename):
    TO_APPEND = ["Map", "Category"]
    title = sanitize_note_filename((data or {}).get("title"))
    if data.get("entityClass") in TO_APPEND:
        return f"{title} {data.get('entityClass')}"

    if title:
        return title

    base = os.path.splitext(os.path.basename(source_filename))[0]
    # Export filenames often look like "Template-Title-uid"; trim wrapper bits.
    base = re.sub(r"^[A-Za-z]+-", "", base)
    base = re.sub(r"-[A-Za-z0-9]{3,}$", "", base)
    fallback = sanitize_note_filename(base)
    return fallback or "untitled"


def create_parent_directory(file_path):
    parent_directory = os.path.dirname(file_path)
    os.makedirs(parent_directory, exist_ok=True)


def list_json_files(directory):
    json_files = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".json"):
                json_files.append(os.path.join(root, filename))
    return json_files


def select_json_files(json_files, file_regex=None):
    if not file_regex:
        return json_files

    pattern = re.compile(file_regex)
    matches = []
    for json_file in json_files:
        basename = os.path.basename(json_file)
        if pattern.search(basename) or pattern.search(json_file):
            matches.append(json_file)

    if not matches:
        print(f"No files matched regex: {file_regex}")
        return []

    matches = sorted(matches)
    if len(matches) > 1:
        print(f"Regex matched {len(matches)} files; converting first match only: {os.path.basename(matches[0])}")

    return [matches[0]]
