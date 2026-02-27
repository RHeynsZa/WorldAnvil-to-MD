import asyncio
import argparse
import json
import os
import re

import httpx
import yaml
from tqdm import tqdm

version = 1.0

DEBUG = False

source_directory = 'World-Anvil-Export' # should point at the local folder with your world anvil exports
destination_directory = '/mnt/c/Users/rheyn/Documents/Obsidian/FateRealms/FateRealms/content' # where you want the formatted files and folders to end up
obsidian_resource_folder = '/mnt/c/Users/rheyn/Documents/Obsidian/FateRealms/FateRealms/images'

attempt_bbcode = True
download_concurrency = 10
download_timeout_seconds = 30.0

# Fields we do not want to export to markdown sections.
ignored_fields = {
    "id", "slug", "state", "isWip", "isDraft", "entityClass", "icon", "url",
    "subscribergroups", "folderId", "updateDate", "position", "wordcount",
    "notificationDate", "likes", "views", "userMetadata", "articleMetadata",
    "cssClasses", "displayCss", "customArticleTemplate", "editor", "author",
    "world", "category", "portrait", "cover", "coverSource", "snippet", "seeded",
    "displaySidebar", "timeline", "prompt", "gallery", "block", "orgchart",
    "showSeeded", "webhookUpdate", "communityUpdate", "commentPlaceholder",
    "passcodecta", "metaTitle", "metaDescription", "coverIsMap",
    "isFeaturedArticle", "isAdultContent", "isLocked", "allowComments",
    "allowContentCopy", "showInToc", "isEmphasized", "displayAuthor",
    "displayChildrenUnder", "displayTitle", "displaySheet", "badge", "editURL",
    "isEditable", "success",
}

# Fields rendered by dedicated logic instead of generic field rendering.
handled_fields = {
    "title", "content", "templateType", "template", "tags",
    "articleParent", "parent", "articleNext", "articlePrevious",
    "creationDate", "publicationDate",
    "sidepanelcontenttop", "sidepanelcontent", "sidebarcontent", "sidebarcontentbottom", "sidepanelcontentbottom",
}

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
    title = sanitize_note_filename((data or {}).get("title"))
    if title:
        return title

    base = os.path.splitext(os.path.basename(source_filename))[0]
    # Export filenames often look like "Template-Title-uid"; trim wrapper bits.
    base = re.sub(r"^[A-Za-z]+-", "", base)
    base = re.sub(r"-[A-Za-z0-9]{3,}$", "", base)
    fallback = sanitize_note_filename(base)
    return fallback or "untitled"

async def download_image(client, semaphore, url, filename):
    if not url or not filename:
        if DEBUG:
            print(f"No URL or filename provided for image: {filename}")
        return

    normalized_filename = normalize_image_filename(filename)
    destination_path = os.path.join(obsidian_resource_folder, normalized_filename)
    if os.path.exists(destination_path):
        return

    async with semaphore:
        try:
            if DEBUG:
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

    semaphore = asyncio.Semaphore(download_concurrency)
    timeout = httpx.Timeout(download_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tasks = [
            download_image(client, semaphore, url, filename)
            for url, filename in deduped_jobs.values()
        ]
        await asyncio.gather(*tasks)

# Function for extracting the extra sections if they are above 10 length,
# this is sections like the scrapbook, geography, etc.
def extract_sections(data, markdown_file):
    if data is None:
        return
    sections = data.get("sections", {})
    if sections is not None and isinstance(sections, dict):
        for section_key, section_data in sections.items():
            if isinstance(section_data, dict) and "content" in section_data:
                content = section_data["content"]
                if isinstance(content, str) and len(content) > 10:
                    section_content = format_content({'text': content})
                    section_key = ' '.join(section_key.split('_')).title()
                    markdown_file.write(f"\n## {section_key}\n\n{section_content}\n")

def extract_relations(data, markdown_file):
    if data is None:
        return
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
                        markdown_file.write(f"\n## {relation_key}\n\n{content}\n")

def create_parent_directory(file_path):
    parent_directory = os.path.dirname(file_path)
    os.makedirs(parent_directory, exist_ok=True)

def replace_spotify_tag(match):
    spotify_url = match.group(1).strip()
    spotify_type = match.group(2).strip().lower()
    spotify_id = match.group(3).strip()
    embed_height = 152 if spotify_type == "track" else 352
    embed_url = f"https://open.spotify.com/embed/{spotify_type}/{spotify_id}"
    return (
        f'<iframe style="border-radius:12px" src="{embed_url}" width="100%" '
        f'height="{embed_height}" frameBorder="0" allowfullscreen="" '
        f'allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" '
        f'loading="lazy"></iframe>'
    )

def format_content(content):
    if not content:
        return ""
    text = content['text']
    if not isinstance(text, str):
        return str(text)

    text = re.sub(r'@\[([^\]]+)\]\([^)]+\)', r'[[\1]]', text) # Replaces World Anvil links with Obsidian internal links
    text = re.sub(r'\r\n\r', r'\n', text) # This was to fix some extra spacing issues that came from my export
    text = re.sub(
        r"\[spotify:(https?://open\.spotify\.com/(track|album|playlist|episode|show)/([A-Za-z0-9]+)(?:\?[^\]]*)?)\]",
        replace_spotify_tag,
        text,
        flags=re.IGNORECASE,
    )

    # THIS SECTION IS A WIP, some of these are ChatGPT-assisted regexes that aren't perfect
    if attempt_bbcode:
        text = re.sub(r'[ \t]+', ' ', text) # Strip extra spaces and tabs
        text = re.sub(r'\n +(\[h\d\])', r'\n\1', text) # Remove leading spaces before headings
        text = re.sub(r'\[br\]', r'\n', text) # [br] to newline
        text = re.sub(r'\[h1\](.*?)\[/h1\]', r'# \1', text) # Convert [h1]...[/h1] to # ... (L1 heading)
        text = re.sub(r'\[h2\](.*?)\[/h2\]', r'## \1', text) # Convert [h2]...[/h2] to ## ... (L2 heading)
        text = re.sub(r'\[h3\](.*?)\[/h3\]', r'### \1', text) # Convert [h3]...[/h3] to ### ... (L3 heading)
        text = re.sub(r'\[h4\](.*?)\[/h4\]', r'#### \1', text) # Convert [h4]...[/h4] to #### ... (L4 heading)
        text = re.sub(r'\[p\](.*?)\[/p\]', r'\1\n', text) # Convert [p]...[/p] to a simple newline-delimited paragraph
        text = re.sub(r'\[b\](.*?)\[/b\]', r'**\1**', text) # Convert [b]...[/b] to **...** (bold)
        text = re.sub(r'\[i\](.*?)\[/i\]', r'*\1*', text) # Convert [i]...[/i] to *...* (italic)
        text = re.sub(r'\[u\](.*?)\[/u\]', r'<u>\1</u>', text) # Convert [u]...[/u] to <u>...</u> (underline)
        text = re.sub(r'\[s\](.*?)\[/s\]', r'~~\1~~', text) # Convert [s]...[/s] to ~~...~~ (strikethrough)
        text = re.sub(r'\[url\](.*?)\[/url\]', r'[\1]', text) # Convert [url]URL[/url] to [text](URL)
        text = re.sub(r'\[list\](.*?)\[/list\]', lambda m: re.sub(r'\[\*\](.*?)\n?', r'* \1\n', m.group(1), flags=re.DOTALL), text, flags=re.DOTALL) # Convert [list]...[/list] to bullet point lists
        text = re.sub(r'\[code\](.*?)\[/code\]', r'```\n\1\n```', text) # Convert [code]...[/code] to code blocks
        text = re.sub(r'\[quote\]([\s\S]*?)\[/quote\]', lambda m: '> ' + '\n> '.join(m.group(1).split('\n')), text, flags=re.DOTALL) # Convert [quote] ... [/quote] to Obsidian block quotes
        
        # These two items will require a CSS snippet to work properly, I included a sample in the repo
        text = re.sub(r'\[sup\](.*?)\[/sup\]', r'<sup>\1</sup>', text) # Superscript
        text = re.sub(r'\[sub\](.*?)\[/sub\]', r'<sub>\1</sub>', text) # Subscript

        # List Items
        text = re.sub(r'\[ol\]|\[/ol\]', r'', text)
        text = re.sub(r'\[ul\]|\[/ul\]', r'', text)
        text = re.sub(r'\[li\](.*?)\[/li\]', r'- \1', text)

    return text

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

def build_id_title_index(json_files):
    id_to_title = {}
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                article_id = data.get("id")
                title = data.get("title")
                if article_id and title:
                    id_to_title[article_id] = title
        except Exception as exc:
            if DEBUG:
                print(f"Unable to index {json_file}: {exc}")
    return id_to_title

def resolve_link_title(reference, id_to_title):
    if isinstance(reference, dict):
        ref_id = reference.get("id")
        return reference.get("title") or id_to_title.get(ref_id)
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
        if not is_empty_value(value.get("title")):
            return f"[[{value.get('title')}]]"
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

def render_navigation(data, markdown_file, id_to_title):
    navigation = []
    parent_title = resolve_link_title(data.get("articleParent"), id_to_title)
    if parent_title:
        navigation.append(f"- Parent: [[{parent_title}]]")

    # Some location templates also expose parent under the plain `parent` key.
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

    if navigation:
        markdown_file.write("## Navigation\n\n")
        markdown_file.write("\n".join(navigation))
        markdown_file.write("\n\n")

def render_generic_fields(data, markdown_file):
    for key, value in data.items():
        if key in ignored_fields or key in handled_fields:
            continue
        if is_empty_value(value):
            continue

        rendered_value = format_field_value(value)
        if not rendered_value.strip():
            continue

        markdown_file.write(f"## {format_field_name(key)}\n\n{rendered_value}\n\n")

def render_sidebar_content(data, markdown_file):
    sidebar_values = [
        data.get("sidepanelcontenttop"),
        data.get("sidepanelcontent"),
        data.get("sidebarcontent"),
        data.get("sidebarcontentbottom") or data.get("sidepanelcontentbottom"),
    ]
    rendered_blocks = []
    for value in sidebar_values:
        if is_empty_value(value):
            continue
        rendered_value = format_field_value(value).strip()
        if rendered_value:
            rendered_blocks.append(rendered_value)

    if not rendered_blocks:
        return

    markdown_file.write(
        '<aside class="wa-sidebar" style="float: right; width: min(360px, 42%); margin: 0 0 1rem 1rem;">\n\n'
    )
    markdown_file.write("\n\n---\n\n".join(rendered_blocks))
    markdown_file.write("\n\n</aside>\n\n")

def build_yaml_data(data, template):
    tags = parse_tags(data.get("tags"))
    yaml_data = {
        "creationDate": (data.get("creationDate") or {}).get("date", ""),
        "publicationDate": (data.get("publicationDate") or {}).get("date", ""),
        "template": template,
        "world": (data.get("world") or {}).get("title", ""),
    }
    if tags:
        yaml_data["tags"] = tags
    return yaml_data

def process_json_file(json_file, id_to_title, output_directory, use_template_folders=True):
    image_job = None
    filename = os.path.basename(json_file)
    with open(json_file, "r", encoding="utf-8") as source_file:
        data = json.load(source_file)

    if data is None:
        print(f"No data found for {filename}")
        return image_job

    template = data.get("templateType") or data.get("template") or "other"
    yaml_data = build_yaml_data(data, template)

    note_filename = build_note_filename(data, filename)
    if use_template_folders:
        markdown_filename = os.path.join(output_directory, template, f"{note_filename}.md")
    else:
        markdown_filename = os.path.join(output_directory, f"{note_filename}.md")
    create_parent_directory(markdown_filename)
    with open(markdown_filename, "w", encoding="utf-8") as markdown_file:
        cover = data.get("cover") or {}
        cover_url = cover.get("url")
        cover_title = normalize_image_filename(cover.get("title"))
        has_image = bool(cover_url and cover_title)

        if has_image:
            image_job = (cover_url, cover_title)

        markdown_file.write("---\n")
        yaml.dump(yaml_data, markdown_file, default_style="", default_flow_style=False, sort_keys=False)
        markdown_file.write("---\n")

        if has_image:
            markdown_file.write(f"![[{cover_title}]]\n\n")

        title = data.get("title")
        if title:
            markdown_file.write(f"# {title}\n\n")

        render_sidebar_content(data, markdown_file)

        content = data.get("content")
        if not is_empty_value(content):
            markdown_file.write(f"{format_content({'text': content})}\n\n")

        render_navigation(data, markdown_file, id_to_title)

        markdown_file.write("# Extras\n\n")
        render_generic_fields(data, markdown_file)
        extract_sections(data, markdown_file)
        extract_relations(data, markdown_file)
        markdown_file.write('<div style="clear: both;"></div>\n')

    return image_job

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
    output_directory = args.output_dir or destination_directory
    os.makedirs(output_directory, exist_ok=True)
    os.makedirs(obsidian_resource_folder, exist_ok=True)
    all_json_files = list_json_files(source_directory)
    file_pattern = args.file_regex
    if not file_pattern and args.file_filter:
        # Treat positional argument as a simple substring-style matcher.
        file_pattern = re.escape(args.file_filter)

    selected_json_files = select_json_files(all_json_files, file_pattern)
    if not selected_json_files:
        return

    # Keep global index for link resolution even in single-file mode.
    id_to_title = build_id_title_index(all_json_files)
    image_jobs = []
    progress_bar = tqdm(total=len(selected_json_files), unit=" articles")

    try:
        for json_file in selected_json_files:
            image_job = process_json_file(
                json_file,
                id_to_title,
                output_directory=output_directory,
                use_template_folders=not args.output_root,
            )
            if image_job:
                image_jobs.append(image_job)
            progress_bar.update(1)
    except Exception as e:
        print(f"Failed to convert. Error: {e}")
        raise
    finally:
        progress_bar.close()

    await download_images(image_jobs)
    print("WA-Parser is finished; Please validate your results")


if __name__ == "__main__":
    asyncio.run(main())
