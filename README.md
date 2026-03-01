# WorldAnvil-to-MD

Convert a World Anvil JSON export into Obsidian-ready markdown with frontmatter, wiki-links, template-based rendering, and automatic image downloads.

This project is optimized for campaign/worldbuilding vaults and supports ITS Theme callouts plus optional Leaflet map blocks.

![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![Obsidian](https://img.shields.io/badge/Obsidian-ready-7C3AED?logo=obsidian&logoColor=white)
![Templates](https://img.shields.io/badge/Jinja-ITS%20templates-F97316)
![Leaflet](https://img.shields.io/badge/Leaflet-optional-22C55E)

## Optional integrations

- 🎨 **ITS Theme rendering (optional):** rich callouts, infobox style layouts, card sections.
- 🗺️ **Leaflet support (optional):** map lookup + Obsidian Leaflet block generation for map notes.

## Preview

### Main note rendering

![Main Preview 1](images/preview1.png)
![Main Preview 2](images/preview2.png)

### Hover preview behavior

![Hover Preview 1](images/hover_preview1.png)
![Hover Preview 2](images/hover_preview2.png)

## Features

- Converts exported World Anvil entities into `.md` notes.
- Preserves internal references as Obsidian wiki-links where possible.
- Writes YAML frontmatter (`creationDate`, `publicationDate`, `template`, `world`, `tags`).
- Cleans note filenames for link-safe output (no UID suffixes in normal cases).
- Normalizes tags (spaces become dashes).
- Converts common BBCode and World Anvil markup.
- Converts `[spotify:...]` tags into embeddable Spotify iframes.
- Downloads cover images and inline images used in note content.
- Supports inline image API fallback for missing export metadata.
- Supports ITS Theme template rendering via Jinja.
- Supports optional Leaflet map embedding with fuzzy map lookup.

## Requirements

- Python `>=3.9`
- `uv` (recommended package/environment manager)

## Installation

```bash
git clone <your-fork-or-this-repo-url>
cd WorldAnvil-to-MD
uv sync
```

This installs all runtime dependencies from `pyproject.toml`:

- `httpx`
- `jinja2`
- `pyyaml`
- `tqdm`

## Project layout

Expected high-level structure:

```text
WorldAnvil-to-MD/
├── WA-Parser.py
├── wa_parser/
├── templates/
├── World-Anvil-Export/
│   ├── articles/
│   ├── images/
│   └── maps/
└── (your output folders)
```

## Quick start

1. Export your world JSON from World Anvil.
2. Place the export under `World-Anvil-Export/`.
3. Update settings in `wa_parser/config.py` (see config reference below).
4. Run conversion:

```bash
uv run python WA-Parser.py
```

For local debugging output:

```bash
uv run python WA-Parser.py --output-dir ./debug-output --output-root
```

## CLI usage

```bash
uv run python WA-Parser.py [file_filter] [--file-regex REGEX] [--output-dir PATH] [--output-root]
```

### Arguments

- `file_filter` (optional): plain text filter converted to regex safely.
- `--file-regex`: regex against basename/full path.
- `--output-dir`: override `destination_directory` for markdown output.
- `--output-root`: disable template-type folder nesting for easier debugging.

### Important behavior

When `file_filter`/`--file-regex` matches multiple files, the parser intentionally converts **only the first sorted match**.

## Configuration reference

Main config lives in `wa_parser/config.py`.

### Core paths

- `source_directory`: root of World Anvil export.
- `destination_directory`: markdown output root.
- `obsidian_resource_folder`: downloaded image output folder.

### Parsing and rendering

- `attempt_bbcode`: enable BBCode-to-markdown conversion.
- `its_theme_support`: enable Jinja ITS template rendering.
- `templates_directory`: template folder path.

### Leaflet support

- `leaflet_plugin_support`: enable map lookup + Leaflet block rendering.
- `leaflet_default_height`: Leaflet block height.
- `leaflet_minimal_template`: when `True`, `Map` entities render as map-only body.

### Inline image API fallback

- `inline_image_api_fallback_enabled`
- `worldanvil_api_key`
- `worldanvil_world_id`
- `worldanvil_image_api_url_template` (must contain `{image_id}`)
- `worldanvil_api_auth_header`
- `worldanvil_api_timeout_seconds`
- `worldanvil_api_retries`
- `missing_inline_image_placeholder_enabled`
- `force_missing_inline_image_ids` (test hook)

## Templates

Templates live in `templates/`:

- `generic.j2` (fallback ITS template)
- `location.j2`
- `settlement.j2`
- `article.j2`
- `item.j2`
- `material.j2`
- `organization.j2`
- `person.j2`
- `plot.j2`
- `leaflet-minimal.j2` (map-only body for `Map` entities when enabled)

Template resolution:

- If `its_theme_support = True`, parser tries `<templateType>.j2`, then falls back to `generic.j2`.
- If Leaflet is enabled and `leaflet_minimal_template = True`, `leaflet-minimal.j2` is used for `Map` entities.

## Image handling

The parser handles:

- Cover images (`cover.url`, `cover.title`)
- Inline images:
  - `[img:12345]`
  - `[img]12345[/img]`
  - with optional params like `[img:12345|left|300]`

Behavior:

- Looks up image ID in exported `World-Anvil-Export/images/*.json`
- Falls back to API lookup (if configured)
- Queues resolved images for download into `obsidian_resource_folder`
- If unresolved and placeholders enabled, emits warning callout

## Leaflet map behavior

When enabled:

- Scans `World-Anvil-Export/maps/**` for `Map` entities.
- Fuzzy-matches article title to map title.
- Picks best map image match from indexed images.
- Emits a minimal Leaflet code block in markdown when matched.

Current output style is intentionally minimal (no auto markers).

Leaflet plugin reference: [obsidian-leaflet](https://github.com/javalent/obsidian-leaflet)

## Output structure

By default, notes are written under template folders:

```text
<destination_directory>/<templateType>/<type-title-lowercase>/<Note Title>.md
```

If `--output-root` is set:

```text
<output-dir>/<type-title-lowercase>/<Note Title>.md
```

If no type title exists, the type subfolder is omitted.

## Troubleshooting

- **No files converted**
  - Check `source_directory` and export folder placement.
  - Verify `--file-regex` pattern actually matches.

- **Images not downloading**
  - Ensure `obsidian_resource_folder` exists/is writable.
  - Verify image URLs in export JSON are valid.

- **Inline image IDs unresolved**
  - Configure API fallback settings in `config.py`.
  - Confirm `worldanvil_image_api_url_template` includes `{image_id}`.

- **Template not applied**
  - Ensure `its_theme_support = True`.
  - Ensure template file exists in `templates/`.

## Development

Run a quick syntax check:

```bash
uv run python -m py_compile WA-Parser.py wa_parser/*.py
```

Typical targeted test run:

```bash
uv run python WA-Parser.py --file-regex "^Settlement-Pottersteel-0dc\\.json$" --output-dir ./debug-output --output-root
```

## Contributing

Contributions are welcome:

- Open an issue for bugs/feature requests.
- Submit focused PRs with clear before/after behavior.
- Include a sample conversion case when changing parsing/rendering logic.

## License

See `LICENSE`.
