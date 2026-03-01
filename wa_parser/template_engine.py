import os
import re

from jinja2 import Environment, FileSystemLoader

from . import config
from .fields import (
    collect_card_link_sections,
    collect_generic_fields,
    collect_navigation_lines,
    collect_relations,
    collect_sections,
    collect_sidebar_sections,
    extract_type_title,
    format_field_value,
    is_empty_value,
    parse_tags,
)
from .text_formatting import format_content


def build_yaml_data(data, template):
    tags = parse_tags(data.get("tags"))
    type_title = extract_type_title(data)
    if type_title:
        for normalized_type_tag in parse_tags([type_title]):
            if normalized_type_tag not in tags:
                tags.append(normalized_type_tag)
    yaml_data = {
        "creationDate": (data.get("creationDate") or {}).get("date", ""),
        "publicationDate": (data.get("publicationDate") or {}).get("date", ""),
        "template": template,
        "world": (data.get("world") or {}).get("title", ""),
    }
    if tags:
        yaml_data["tags"] = tags
    return yaml_data


def render_markdown_template(template_name, context):
    environment = Environment(
        loader=FileSystemLoader(config.templates_directory),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template(template_name)
    return template.render(**context)


def resolve_its_template_name(template_name):
    normalized = (template_name or "").strip().lower()
    if normalized:
        candidate_path = os.path.join(config.templates_directory, f"{normalized}.j2")
        if os.path.exists(candidate_path):
            return normalized
    return "generic"


def get_infobox_fact_specs(template_name):
    fact_key_map = {
        "generic": [("Template", "templateType"), ("World", "world"), ("Parent", "articleParent")],
        "article": [("Template", "templateType"), ("Parent", "articleParent"), ("World", "world")],
        "item": [("Template", "templateType"), ("Type", "type"), ("Rarity", "rarity"), ("Weight", "weight"), ("Value", "value"), ("World", "world")],
        "location": [("Parent", "parent"), ("Parent", "articleParent"), ("Type", "type"), ("Climate", "climate"), ("World", "world")],
        "material": [("Template", "templateType"), ("Type", "type"), ("Rarity", "rarity"), ("World", "world")],
        "organization": [("Template", "templateType"), ("Type", "type"), ("Leader", "leader"), ("Headquarters", "headquarters"), ("World", "world")],
        "person": [("Template", "templateType"), ("Species", "species"), ("Gender", "gender"), ("Birthplace", "birthplace"), ("Residence", "residence"), ("Affiliation", "affiliation"), ("World", "world")],
        "plot": [("Template", "templateType"), ("Status", "status"), ("World", "world")],
        "settlement": [("Parent", "articleParent"), ("Type", "type"), ("Population", "population"), ("Demonym", "demonym"), ("Alternative Name", "alternativename"), ("World", "world")],
    }
    return fact_key_map.get(template_name, fact_key_map["generic"])


def build_infobox_facts(data, template_name):
    fact_specs = get_infobox_fact_specs(template_name)
    seen_labels = set()
    facts = []
    for label, key in fact_specs:
        if label in seen_labels:
            continue
        if key == "parent":
            value = data.get("parent") or data.get("articleParent")
        else:
            value = data.get(key)
        if is_empty_value(value):
            continue
        rendered_value = format_field_value(value).strip()
        if not rendered_value:
            continue
        rendered_value = re.sub(r"\s*\n\s*", " | ", rendered_value)
        if len(rendered_value) > 240:
            continue
        facts.append((label, rendered_value))
        seen_labels.add(label)

    if "Type" not in seen_labels:
        type_title = extract_type_title(data)
        if type_title:
            type_value = format_field_value({"title": type_title}).strip()
            if type_value:
                facts.append(("Type", type_value))
                seen_labels.add("Type")
    return facts


def collect_top_summary_fields(data, template_name):
    top_field_map = {}
    field_names = top_field_map.get(template_name, [])
    top_fields = []
    for key in field_names:
        value = data.get(key)
        if is_empty_value(value):
            continue
        rendered_value = format_field_value(value).strip()
        if rendered_value:
            # Pass both key and display label for dedup logic.
            top_fields.append((key, key.replace("_", " ").title(), rendered_value))
    return top_fields


def render_its_template_body(data, id_to_title, has_image, cover_title, template_name, leaflet_block=""):
    # Only render map-only output for actual map entities.
    entity_class = str((data or {}).get("entityClass") or "").strip().lower()
    if (
        config.leaflet_plugin_support
        and config.leaflet_minimal_template
        and leaflet_block
        and entity_class == "map"
    ):
        return render_markdown_template(
            "leaflet-minimal.j2",
            {
                "leaflet_block": leaflet_block,
            },
        )

    content = data.get("content")
    main_content = ""
    if not is_empty_value(content):
        main_content = format_content({"text": content})

    resolved_template = resolve_its_template_name(template_name)
    pronunciation = data.get("pronunciation")
    title_pronunciation = ""
    if isinstance(pronunciation, str):
        title_pronunciation = pronunciation.strip()
    subheading = data.get("subheading")
    title_subheading = ""
    if isinstance(subheading, str):
        title_subheading = subheading.strip()
    excerpt = data.get("excerpt")
    title_excerpt = ""
    if not is_empty_value(excerpt):
        title_excerpt = format_field_value(excerpt).strip()
    card_link_sections = collect_card_link_sections(data)
    sidebar_sections = collect_sidebar_sections(data, resolved_template)
    infobox_facts = build_infobox_facts(data, resolved_template)
    top_summary_fields = collect_top_summary_fields(data, resolved_template)
    infobox_fact_keys = {key for _, key in get_infobox_fact_specs(resolved_template)}
    top_summary_keys = {key for key, _, _ in top_summary_fields}
    card_section_keys = {"children", "childrenArticles", "articles"}
    title_field_keys = {"pronunciation", "subheading", "excerpt"}
    skip_keys = infobox_fact_keys.union(top_summary_keys).union(card_section_keys).union(title_field_keys)
    return render_markdown_template(
        f"{resolved_template}.j2",
        {
            "title": data.get("title", ""),
            "title_pronunciation": title_pronunciation,
            "title_subheading": title_subheading,
            "title_excerpt": title_excerpt,
            "has_image": has_image,
            "cover_title": cover_title,
            "main_content": main_content,
            "spotify_blocks": sidebar_sections["spotify_blocks"],
            "sidebar_top_blocks": sidebar_sections["top_blocks"],
            "sidebar_panel_blocks": sidebar_sections["panel_blocks"],
            "sidebar_bottom_blocks": sidebar_sections["bottom_blocks"],
            "leaflet_block": leaflet_block,
            "infobox_facts": infobox_facts,
            "top_summary_fields": [(label, value) for _, label, value in top_summary_fields],
            "navigation_lines": collect_navigation_lines(data, id_to_title),
            "card_link_sections": card_link_sections,
            "generic_fields": collect_generic_fields(data, skip_keys=skip_keys),
            "extra_sections": collect_sections(data),
            "extra_relations": collect_relations(data),
        },
    )
