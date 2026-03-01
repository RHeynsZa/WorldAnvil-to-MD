import io
import json
import os

import yaml
from jinja2 import TemplateNotFound

from . import config
from .fields import (
    extract_type_title,
    extract_relations,
    extract_sections,
    is_empty_value,
    render_generic_fields,
    render_navigation,
    render_sidebar_content,
    type_folder_name,
)
from .image_pipeline import begin_image_job_collection, end_image_job_collection, register_image_job
from .maps import build_leaflet_context_for_article
from .template_engine import build_yaml_data, render_its_template_body
from .text_formatting import format_content
from .utils import build_note_filename, create_parent_directory, normalize_image_filename

TO_SKIP = ["Image", "Manuscript"]

CUSTOM_ENTITY_TYPE_FOLDER_MAP = {
    "Category": "category",
}

def process_json_file(json_file, id_to_title, output_directory, use_template_folders=True):
    begin_image_job_collection()
    filename = os.path.basename(json_file)
    with open(json_file, "r", encoding="utf-8") as source_file:
        data = json.load(source_file)

    if data is None:
        print(f"No data found for {filename}")
        return end_image_job_collection()

    template = data.get("templateType") or data.get("template") or CUSTOM_ENTITY_TYPE_FOLDER_MAP.get(data.get("entityClass")) or "other"
    yaml_data = build_yaml_data(data, template)

    if data.get("entityClass") in TO_SKIP:
        return end_image_job_collection()

    note_filename = build_note_filename(data, filename)
    type_subfolder = type_folder_name(extract_type_title(data))
    entity_class = str(data.get("entityClass") or "").strip().lower()
    if entity_class == "map":
        leaflet_context = build_leaflet_context_for_article(data.get("title") or "")
    else:
        leaflet_context = {"leaflet_block": "", "leaflet_map_image": {}}
    leaflet_block = leaflet_context.get("leaflet_block") or ""
    leaflet_map_image = leaflet_context.get("leaflet_map_image") or {}
    if use_template_folders:
        if type_subfolder:
            markdown_filename = os.path.join(output_directory, template, type_subfolder, f"{note_filename}.md")
        else:
            markdown_filename = os.path.join(output_directory, template, f"{note_filename}.md")
    else:
        if type_subfolder:
            markdown_filename = os.path.join(output_directory, type_subfolder, f"{note_filename}.md")
        else:
            markdown_filename = os.path.join(output_directory, f"{note_filename}.md")
    create_parent_directory(markdown_filename)
    with open(markdown_filename, "w", encoding="utf-8") as markdown_file:
        cover = data.get("cover") or {}
        cover_url = cover.get("url")
        cover_title = normalize_image_filename(cover.get("title"))
        has_image = bool(cover_url and cover_title)

        if has_image:
            register_image_job(cover_url, cover_title)
        if leaflet_map_image.get("url") and leaflet_map_image.get("filename"):
            register_image_job(leaflet_map_image["url"], leaflet_map_image["filename"])

        frontmatter_buffer = io.StringIO()
        yaml.dump(yaml_data, frontmatter_buffer, default_style="", default_flow_style=False, sort_keys=False)
        markdown_file.write("---\n")
        markdown_file.write(frontmatter_buffer.getvalue())
        markdown_file.write("---\n")

        template_applied = False
        if config.its_theme_support:
            try:
                rendered_body = render_its_template_body(
                    data,
                    id_to_title,
                    has_image,
                    cover_title,
                    template_name=template,
                    leaflet_block=leaflet_block,
                )
                markdown_file.write(rendered_body)
                if not rendered_body.endswith("\n"):
                    markdown_file.write("\n")
                template_applied = True
            except TemplateNotFound:
                if config.DEBUG:
                    print(f"ITS template not found for type '{template}'; falling back to default renderer.")

        if not template_applied:
            if has_image:
                markdown_file.write(f"![[{cover_title}]]\n\n")

            title = data.get("title")
            if title:
                markdown_file.write(f"# {title}\n\n")

            render_sidebar_content(data, markdown_file)
            if leaflet_block:
                markdown_file.write(f"\n{leaflet_block}\n\n")

            content = data.get("content")
            if not is_empty_value(content):
                markdown_file.write(f"{format_content({'text': content})}\n\n")

            render_navigation(data, markdown_file, id_to_title)

            markdown_file.write("# Extras\n\n")
            render_generic_fields(data, markdown_file)
            extract_sections(data, markdown_file)
            extract_relations(data, markdown_file)
            markdown_file.write('<div style="clear: both;"></div>\n')

    return end_image_job_collection()
