import argparse
import asyncio
import os
import re

from tqdm import tqdm

from . import config
from .fields import build_id_title_index
from .image_pipeline import build_local_image_index, download_images, local_image_index
from .maps import build_map_index, set_map_index
from .processor import process_json_file
from .utils import list_json_files, select_json_files


def parse_args():
    parser = argparse.ArgumentParser(description="Convert World Anvil JSON export to Obsidian markdown.")
    parser.add_argument(
        "file_filter",
        nargs="?",
        default=None,
        help="Optional plain-text file filter (example: Material-Mysticum).",
    )
    parser.add_argument(
        "--file-regex",
        dest="file_regex",
        default=None,
        help="Regex to select a specific JSON file for conversion (matches basename or full path).",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default=None,
        help="Override output directory for markdown files (defaults to destination_directory).",
    )
    parser.add_argument(
        "--output-root",
        dest="output_root",
        action="store_true",
        help="Write markdown files directly in output directory root (no template subfolders). Useful for debugging.",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    output_directory = args.output_dir or config.destination_directory
    os.makedirs(output_directory, exist_ok=True)
    os.makedirs(config.obsidian_resource_folder, exist_ok=True)

    local_image_index.clear()
    local_image_index.update(build_local_image_index(os.path.join(config.source_directory, "images")))
    set_map_index(build_map_index(os.path.join(config.source_directory, "maps"), local_image_index))

    all_json_files = list_json_files(config.source_directory)
    file_pattern = args.file_regex
    if not file_pattern and args.file_filter:
        file_pattern = re.escape(args.file_filter)

    selected_json_files = select_json_files(all_json_files, file_pattern)
    if not selected_json_files:
        return

    id_to_title = build_id_title_index(all_json_files)
    image_jobs = []
    progress_bar = tqdm(total=len(selected_json_files), unit=" articles")

    try:
        for json_file in selected_json_files:
            file_image_jobs = process_json_file(
                json_file,
                id_to_title,
                output_directory=output_directory,
                use_template_folders=not args.output_root,
            )
            if file_image_jobs:
                image_jobs.extend(file_image_jobs)
            progress_bar.update(1)
    except Exception as e:
        print(f"Failed to convert. Error: {e}")
        raise
    finally:
        progress_bar.close()

    await download_images(image_jobs)
    print("WA-Parser is finished; Please validate your results")


def run():
    asyncio.run(main())
