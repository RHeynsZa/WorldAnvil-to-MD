import json
import re

from . import config
from .image_pipeline import build_image_metadata, register_image_job, render_portrait_embed
from .text_formatting import extract_spotify_embeds_and_text, format_content


def note_link_title(entity):
    if not isinstance(entity, dict):
        return None
    title = entity.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    normalized_title = title.strip()
    entity_class = str(entity.get("entityClass") or "").strip().lower()
    if entity_class == "map" and not normalized_title.lower().endswith(" map"):
        return f"{normalized_title} Map"
    return normalized_title


def collect_sections(data):
    collected_sections = []
    if data is None:
        return collected_sections
    sections = data.get("sections", {})
    if sections is not None and isinstance(sections, dict):
        for section_key, section_data in sections.items():
            if isinstance(section_data, dict) and "content" in section_data:
                content = section_data["content"]
                if isinstance(content, str) and len(content) > 10:
                    section_content = format_content({"text": content})
                    section_key = " ".join(section_key.split("_")).title()
                    collected_sections.append((section_key, section_content))
    return collected_sections


def extract_sections(data, markdown_file):
    for section_key, section_content in collect_sections(data):
        markdown_file.write(f"\n## {section_key}\n\n{section_content}\n")


def collect_relations(data):
    collected_relations = []
    if data is None:
        return collected_relations
    relations = data.get("relations", {})
    if relations is not None and isinstance(relations, dict):
        for relation_key, relation_data in relations.items():
            if isinstance(relation_data, dict) and "items" in relation_data:
                content = ""
                if isinstance(relation_data["items"], list):
                    for item in relation_data["items"]:
                        title = item.get("title")
                        if not title:
                            continue
                        if item.get("relationshipType") == "article":
                            content += f"[[{title}]]\n"
                        else:
                            content += f"{title}\n"
                    if content.strip():
                        relation_key = " ".join(relation_key.split("_")).title()
                        collected_relations.append((relation_key, content.strip()))
    return collected_relations


def extract_relations(data, markdown_file):
    for relation_key, content in collect_relations(data):
        markdown_file.write(f"\n## {relation_key}\n\n{content}\n")


def is_empty_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0 or all(is_empty_value(item) for item in value)
    if isinstance(value, dict):
        if "title" in value and not is_empty_value(value.get("title")):
            return False
        if "date" in value and not is_empty_value(value.get("date")):
            return False
        return all(is_empty_value(v) for v in value.values())
    return False


def format_field_name(field_name):
    field_name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", field_name)
    field_name = field_name.replace("_", " ")
    return field_name.strip().title()


def parse_tags(raw_tags):
    def normalize_tag(tag):
        tag_text = str(tag).strip()
        if not tag_text:
            return ""
        return re.sub(r"\s+", "-", tag_text)

    if not raw_tags:
        return []
    if isinstance(raw_tags, str):
        return [normalized for tag in raw_tags.split(",") if (normalized := normalize_tag(tag))]
    if isinstance(raw_tags, list):
        return [normalized for tag in raw_tags if (normalized := normalize_tag(tag))]
    return []


def extract_type_title(data):
    type_value = (data or {}).get("type")
    if isinstance(type_value, dict):
        title = type_value.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    if isinstance(type_value, str) and type_value.strip():
        return type_value.strip()
    return None


def type_folder_name(type_title):
    if not type_title:
        return None
    folder_name = re.sub(r"[^\w\s-]", "", str(type_title)).strip().lower()
    folder_name = re.sub(r"\s+", "-", folder_name)
    return folder_name or None


def build_id_title_index(json_files):
    id_to_title = {}
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                article_id = data.get("id")
                title = note_link_title(data) or data.get("title")
                if article_id and title:
                    id_to_title[article_id] = title
        except Exception as exc:
            if config.DEBUG:
                print(f"Unable to index {json_file}: {exc}")
    return id_to_title


def resolve_link_title(reference, id_to_title):
    if isinstance(reference, dict):
        ref_id = reference.get("id")
        return note_link_title(reference) or id_to_title.get(ref_id)
    if isinstance(reference, str):
        return id_to_title.get(reference)
    return None


def format_field_value(value):
    if isinstance(value, str):
        return format_content({"text": value})
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        link_title = note_link_title(value)
        if link_title:
            return f"[[{link_title}]]"
        if not is_empty_value(value.get("date")):
            return str(value.get("date"))
        lines = []
        for key, item in value.items():
            if is_empty_value(item):
                continue
            item_text = format_field_value(item)
            if item_text:
                lines.append(f"- **{format_field_name(key)}**: {item_text}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if is_empty_value(item):
                continue
            item_text = format_field_value(item)
            if item_text:
                lines.append(f"- {item_text}")
        return "\n".join(lines)
    return str(value)


def collect_navigation_lines(data, id_to_title):
    navigation = []
    parent_title = resolve_link_title(data.get("articleParent"), id_to_title)
    if parent_title:
        navigation.append(f"- Parent: [[{parent_title}]]")

    if not parent_title:
        alt_parent_title = resolve_link_title(data.get("parent"), id_to_title)
        if alt_parent_title:
            navigation.append(f"- Parent: [[{alt_parent_title}]]")

    previous_title = resolve_link_title(data.get("articlePrevious"), id_to_title)
    if previous_title:
        navigation.append(f"- Previous: [[{previous_title}]]")

    next_title = resolve_link_title(data.get("articleNext"), id_to_title)
    if next_title:
        navigation.append(f"- Next: [[{next_title}]]")
    return navigation


def render_navigation(data, markdown_file, id_to_title):
    navigation = collect_navigation_lines(data, id_to_title)
    if navigation:
        markdown_file.write("## Navigation\n\n")
        markdown_file.write("\n".join(navigation))
        markdown_file.write("\n\n")


def collect_card_link_sections(data):
    sections = []
    if data is None or not isinstance(data, dict):
        return sections

    for key, label in (
        ("children", "Children"),
        ("childrenArticles", "Children Articles"),
        ("articles", "Articles"),
    ):
        value = data.get(key)
        if not isinstance(value, list):
            continue

        links = []
        for item in value:
            if isinstance(item, dict):
                title = note_link_title(item) or item.get("title")
                if isinstance(title, str) and title.strip():
                    links.append(f"[[{title.strip()}]]")
            elif isinstance(item, str) and item.strip():
                links.append(f"[[{item.strip()}]]")

        if links:
            sections.append((label, links))
    return sections


def collect_generic_fields(data, skip_keys=None):
    skip_keys = skip_keys or set()
    collected_fields = []
    for key, value in data.items():
        if key in config.ignored_fields or key in config.handled_fields or key in skip_keys:
            continue
        if is_empty_value(value):
            continue
        rendered_value = format_field_value(value)
        if not rendered_value.strip():
            continue
        collected_fields.append((format_field_name(key), rendered_value))
    return collected_fields


def render_generic_fields(data, markdown_file):
    for field_name, rendered_value in collect_generic_fields(data):
        markdown_file.write(f"## {field_name}\n\n{rendered_value}\n\n")


def collect_sidebar_blocks(data, template_name=None):
    sidebar_sections = collect_sidebar_sections(data, template_name)
    return (
        sidebar_sections["spotify_blocks"]
        + sidebar_sections["top_blocks"]
        + sidebar_sections["panel_blocks"]
        + sidebar_sections["bottom_blocks"]
    )


def collect_sidebar_sections(data, template_name=None):
    resolved_template = (template_name or data.get("templateType") or data.get("template") or "").lower()
    sidepanel_top_value = data.get("sidepanelcontenttop")
    sidepanel_value = data.get("sidepanelcontent")
    sidebar_bottom_value = data.get("sidebarcontentbottom") or data.get("sidepanelcontentbottom")
    sidebarcontent_value = data.get("sidebarcontent")
    spotify_blocks = []
    sidebarcontent_remainder = None

    if isinstance(sidebarcontent_value, str):
        spotify_blocks, remaining_sidebarcontent = extract_spotify_embeds_and_text(sidebarcontent_value)
        if remaining_sidebarcontent.strip():
            sidebarcontent_remainder = remaining_sidebarcontent
    elif not is_empty_value(sidebarcontent_value):
        sidebarcontent_remainder = sidebarcontent_value

    top_values = [sidepanel_top_value]
    panel_values = [sidepanel_value]
    if sidebarcontent_remainder is not None:
        panel_values.append(sidebarcontent_remainder)

    if resolved_template == "person":
        portrait_metadata = build_image_metadata(data.get("portrait") or {})
        if portrait_metadata:
            register_image_job(portrait_metadata["url"], portrait_metadata["filename"])
            top_values.insert(0, render_portrait_embed(portrait_metadata["filename"]))

    def render_sidebar_values(values):
        rendered_blocks = []
        for value in values:
            if is_empty_value(value):
                continue
            rendered_value = format_field_value(value).strip()
            if rendered_value:
                rendered_blocks.append(rendered_value)
        return rendered_blocks

    return {
        "spotify_blocks": spotify_blocks,
        "top_blocks": render_sidebar_values(top_values),
        "panel_blocks": render_sidebar_values(panel_values),
        "bottom_blocks": render_sidebar_values([sidebar_bottom_value]),
    }


def render_sidebar_content(data, markdown_file):
    rendered_blocks = collect_sidebar_blocks(data)
    if not rendered_blocks:
        return

    markdown_file.write(
        '<aside class="wa-sidebar" style="float: right; width: min(360px, 42%); margin: 0 0 1rem 1rem;">\n\n'
    )
    markdown_file.write("\n\n---\n\n".join(rendered_blocks))
    markdown_file.write("\n\n</aside>\n\n")
