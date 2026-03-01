import asyncio
import json
import os

import httpx

from . import config
from .utils import normalize_image_filename


local_image_index = {}
api_image_cache = {}
active_image_jobs = None


def begin_image_job_collection():
    global active_image_jobs
    active_image_jobs = []


def end_image_job_collection():
    global active_image_jobs
    jobs = active_image_jobs or []
    active_image_jobs = None
    return jobs


def register_image_job(url, filename):
    if active_image_jobs is None or not url or not filename:
        return
    normalized_filename = normalize_image_filename(filename)
    if normalized_filename:
        active_image_jobs.append((url, normalized_filename))


def build_image_metadata(image_record):
    if not isinstance(image_record, dict):
        return None

    image_id = image_record.get("id")
    image_url = image_record.get("url")
    if not image_id or not image_url:
        return None

    preferred_name = image_record.get("title") or image_record.get("filename") or f"image-{image_id}"
    extension = image_record.get("extension")
    if extension and not str(preferred_name).lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        preferred_name = f"{preferred_name}.{extension}"

    return {
        "id": str(image_id),
        "title": image_record.get("title") or "",
        "url": image_url,
        "filename": normalize_image_filename(preferred_name),
    }


def build_local_image_index(images_directory):
    index = {}
    if not os.path.isdir(images_directory):
        return index

    for root, _, files in os.walk(images_directory):
        for filename in files:
            if not filename.endswith(".json"):
                continue
            file_path = os.path.join(root, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as image_file:
                    image_data = json.load(image_file)
            except Exception as exc:
                if config.DEBUG:
                    print(f"Unable to read image metadata {file_path}: {exc}")
                continue

            image_metadata = build_image_metadata(image_data)
            if image_metadata:
                index[image_metadata["id"]] = image_metadata
    return index


def parse_api_image_payload(payload, expected_image_id):
    candidates = []
    if isinstance(payload, dict):
        candidates.append(payload)
        for key in ("data", "image", "result"):
            value = payload.get(key)
            if isinstance(value, dict):
                candidates.append(value)
            elif isinstance(value, list):
                candidates.extend(item for item in value if isinstance(item, dict))
    elif isinstance(payload, list):
        candidates.extend(item for item in payload if isinstance(item, dict))

    expected_id = str(expected_image_id)
    for candidate in candidates:
        metadata = build_image_metadata(candidate)
        if metadata and metadata["id"] == expected_id:
            return metadata
    return None


def resolve_image_via_api(image_id):
    if not config.inline_image_api_fallback_enabled:
        return None
    if not config.worldanvil_image_api_url_template:
        return None
    if not config.worldanvil_api_key:
        return None

    image_id = str(image_id)
    if image_id in api_image_cache:
        return api_image_cache[image_id]

    request_url = config.worldanvil_image_api_url_template.format(image_id=image_id)
    headers = {config.worldanvil_api_auth_header: config.worldanvil_api_key}
    params = {}
    if config.worldanvil_world_id:
        params["world"] = config.worldanvil_world_id

    metadata = None
    for _ in range(max(1, config.worldanvil_api_retries)):
        try:
            response = httpx.get(
                request_url,
                headers=headers,
                params=params,
                timeout=config.worldanvil_api_timeout_seconds,
            )
            if response.status_code == 404:
                break
            response.raise_for_status()
            metadata = parse_api_image_payload(response.json(), image_id)
            if metadata:
                break
        except Exception as exc:
            if config.DEBUG:
                print(f"Failed API image lookup for {image_id}: {exc}")

    api_image_cache[image_id] = metadata
    return metadata


def resolve_inline_image_metadata(image_id):
    image_id = str(image_id)
    if image_id in config.force_missing_inline_image_ids:
        return None

    if image_id in local_image_index:
        return local_image_index[image_id]

    metadata = resolve_image_via_api(image_id)
    if metadata:
        local_image_index[image_id] = metadata
    return metadata


def render_inline_image_embed(filename, raw_params=None):
    params = []
    if raw_params:
        params = [token.strip() for token in str(raw_params).split("|") if token.strip()]

    width = None
    for token in params:
        if token.isdigit() and width is None:
            width = int(token)

    if config.its_theme_support:
        attributes = []
        if width and width > 0:
            if width <= 70:
                attributes.append("wmicro")
            elif width <= 100:
                attributes.append("wtiny")
            elif width <= 200:
                attributes.append("wsmall")
            elif width <= 300:
                attributes.append("ws-med")
            elif width <= 400:
                attributes.append("wm-sm")
            elif width <= 500:
                attributes.append("wmed")
            elif width <= 600:
                attributes.append("wm-tl")
            elif width <= 700:
                attributes.append("wtall")
            else:
                attributes.append("wfull")
        if attributes:
            return f"\n![[{filename}|{'|'.join(attributes)}]]\n"
        return f"\n![[{filename}]]\n"

    if width:
        return f"\n![[{filename}|{width}]]\n"
    return f"\n![[{filename}]]\n"


def render_portrait_embed(filename):
    if config.its_theme_support:
        return f"![[{filename}|portrait]]"
    return f"![[{filename}|250]]"


def replace_inline_image_tag(match):
    image_id = match.group(1) or match.group(3)
    image_params = match.group(2) or ""
    metadata = resolve_inline_image_metadata(image_id)
    if not metadata:
        if config.missing_inline_image_placeholder_enabled:
            return f"\n> [!warning] Missing image {image_id}\n"
        return match.group(0)

    register_image_job(metadata["url"], metadata["filename"])
    return render_inline_image_embed(metadata["filename"], image_params)


async def download_image(client, semaphore, url, filename):
    if not url or not filename:
        if config.DEBUG:
            print(f"No URL or filename provided for image: {filename}")
        return

    normalized_filename = normalize_image_filename(filename)
    destination_path = os.path.join(config.obsidian_resource_folder, normalized_filename)
    if os.path.exists(destination_path):
        return

    async with semaphore:
        try:
            if config.DEBUG:
                print(url)
            response = await client.get(url)
            response.raise_for_status()
            with open(destination_path, "wb") as image_file:
                image_file.write(response.content)
        except Exception as e:
            print(f"Failed to download or save image {normalized_filename}. Error: {e}")


async def download_images(image_jobs):
    if not image_jobs:
        return

    deduped_jobs = {}
    for url, filename in image_jobs:
        normalized_filename = normalize_image_filename(filename)
        if normalized_filename and url:
            deduped_jobs[normalized_filename] = (url, normalized_filename)

    semaphore = asyncio.Semaphore(config.download_concurrency)
    timeout = httpx.Timeout(config.download_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tasks = [
            download_image(client, semaphore, url, filename)
            for url, filename in deduped_jobs.values()
        ]
        await asyncio.gather(*tasks)
