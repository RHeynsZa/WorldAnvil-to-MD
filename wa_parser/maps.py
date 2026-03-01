import json
import os
import re

from . import config


map_index = []


def normalize_lookup_text(value):
    if not value:
        return ""
    normalized = re.sub(r"[^\w\s-]", " ", str(value).lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def score_map_match(article_norm, map_norm):
    if not article_norm or not map_norm:
        return -1
    if article_norm == map_norm:
        return 1000
    if article_norm in map_norm or map_norm in article_norm:
        return 500 - abs(len(article_norm) - len(map_norm))
    article_tokens = set(article_norm.split())
    map_tokens = set(map_norm.split())
    if not article_tokens or not map_tokens:
        return -1
    overlap = len(article_tokens.intersection(map_tokens))
    if overlap == 0:
        return -1
    return overlap * 10


def choose_map_image(map_title, image_index):
    title_norm = normalize_lookup_text(map_title)
    best = None
    best_score = -1
    for metadata in image_index.values():
        image_title_norm = normalize_lookup_text(metadata.get("title"))
        if not image_title_norm:
            continue
        score = score_map_match(title_norm, image_title_norm)
        if "map" in image_title_norm:
            score += 25
        if "base" in image_title_norm:
            score += 10
        if score > best_score:
            best_score = score
            best = metadata
    return best if best_score > 0 else None


def parse_map_folder(map_folder_path, image_index):
    map_entity = None

    for entry in os.listdir(map_folder_path):
        if not entry.endswith(".json"):
            continue
        file_path = os.path.join(map_folder_path, entry)
        try:
            with open(file_path, "r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)
        except Exception:
            continue

        entity_class = (payload or {}).get("entityClass")
        if entity_class == "Map":
            map_entity = payload

    if not map_entity:
        return None

    map_title = map_entity.get("title") or ""
    map_image = choose_map_image(map_title, image_index)

    return {
        "id": map_entity.get("id"),
        "title": map_title,
        "url": map_entity.get("url"),
        "folder_path": map_folder_path,
        "title_norm": normalize_lookup_text(map_title),
        "image": map_image,
    }


def build_map_index(maps_root_directory, image_index):
    index = []
    if not os.path.isdir(maps_root_directory):
        return index

    for entry in os.listdir(maps_root_directory):
        folder_path = os.path.join(maps_root_directory, entry)
        if not os.path.isdir(folder_path):
            continue
        map_record = parse_map_folder(folder_path, image_index)
        if map_record:
            index.append(map_record)
    return index


def set_map_index(index):
    global map_index
    map_index = index or []


def find_best_map_for_article(article_title):
    article_norm = normalize_lookup_text(article_title)
    if not article_norm:
        return None

    best = None
    best_score = -1
    for map_record in map_index:
        score = score_map_match(article_norm, map_record.get("title_norm", ""))
        if score > best_score:
            best = map_record
            best_score = score
    return best if best_score > 0 else None


def render_leaflet_block(map_record):
    if not map_record:
        return ""
    map_id = (map_record.get("id") or "wa-map").split("-")[0]
    lines = [
        "```leaflet",
        f"id: wa-map-{map_id}",
        f"height: {config.leaflet_default_height}",
    ]

    map_image = map_record.get("image") or {}
    map_image_filename = map_image.get("filename")
    if map_image_filename:
        lines.append(f"image: [[{map_image_filename}]]")
    else:
        return ""

    lines.append("```")
    return "\n".join(lines)


def build_leaflet_context_for_article(article_title):
    if not config.leaflet_plugin_support:
        return {"leaflet_block": "", "leaflet_map_image": None}

    map_record = find_best_map_for_article(article_title)
    if not map_record:
        return {"leaflet_block": "", "leaflet_map_image": None}

    return {
        "leaflet_block": render_leaflet_block(map_record),
        "leaflet_map_image": map_record.get("image"),
    }
