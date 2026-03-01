import re

from . import config
from .image_pipeline import replace_inline_image_tag

SPOTIFY_TAG_PATTERN = re.compile(
    r"\[spotify:(https?://open\.spotify\.com/(track|album|playlist|episode|show)/([A-Za-z0-9]+)(?:\?[^\]]*)?)\]",
    flags=re.IGNORECASE,
)


def replace_spotify_tag(match):
    spotify_type = match.group(2).strip().lower()
    spotify_id = match.group(3).strip()
    embed_height = 84 if spotify_type == "track" else 180
    embed_url = f"https://open.spotify.com/embed/{spotify_type}/{spotify_id}"
    return (
        f'<iframe style="border-radius:12px" src="{embed_url}" width="100%" '
        f'height="{embed_height}" frameBorder="0" allowfullscreen="" '
        f'allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" '
        f'loading="lazy"></iframe>'
    )


def extract_spotify_embeds_and_text(raw_text):
    if not isinstance(raw_text, str):
        return [], raw_text
    embeds = [replace_spotify_tag(match) for match in SPOTIFY_TAG_PATTERN.finditer(raw_text)]
    remaining_text = SPOTIFY_TAG_PATTERN.sub("", raw_text)
    return embeds, remaining_text


def format_content(content):
    if not content:
        return ""
    text = content["text"]
    if not isinstance(text, str):
        return str(text)

    text = re.sub(r"@\[([^\]]+)\]\([^)]+\)", r"[[\1]]", text)
    text = re.sub(r"\r\n\r", r"\n", text)
    text = SPOTIFY_TAG_PATTERN.sub(replace_spotify_tag, text)
    text = re.sub(
        r"\[img:(\d+)(\|[^\]]*)?\]|\[img\](\d+)\[/img\]",
        replace_inline_image_tag,
        text,
        flags=re.IGNORECASE,
    )

    if config.attempt_bbcode:
        text = re.sub(r"\[section:[^\]]*\]|\[/section\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[container:[^\]]*\]|\[/container\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n +(\[h\d\])", r"\n\1", text)
        text = re.sub(r"\[br\]", r"\n", text)
        text = re.sub(r"\[h1\](.*?)\[/h1\]", r"# \1", text)
        text = re.sub(r"\[h2\](.*?)\[/h2\]", r"## \1", text)
        text = re.sub(r"\[h3\](.*?)\[/h3\]", r"### \1", text)
        text = re.sub(r"\[h4\](.*?)\[/h4\]", r"#### \1", text)
        text = re.sub(r"\[p\](.*?)\[/p\]", r"\1\n", text)
        text = re.sub(r"\[b\](.*?)\[/b\]", r"**\1**", text)
        text = re.sub(r"\[i\](.*?)\[/i\]", r"*\1*", text)
        text = re.sub(r"\[u\](.*?)\[/u\]", r"<u>\1</u>", text)
        text = re.sub(r"\[s\](.*?)\[/s\]", r"~~\1~~", text)
        text = re.sub(r"\[url\](.*?)\[/url\]", r"[\1]", text)
        text = re.sub(
            r"\[list\](.*?)\[/list\]",
            lambda m: re.sub(r"\[\*\](.*?)\n?", r"* \1\n", m.group(1), flags=re.DOTALL),
            text,
            flags=re.DOTALL,
        )
        text = re.sub(r"\[code\](.*?)\[/code\]", r"```\n\1\n```", text)
        text = re.sub(
            r"\[quote\]([\s\S]*?)\[/quote\]",
            lambda m: "> " + "\n> ".join(m.group(1).split("\n")),
            text,
            flags=re.DOTALL,
        )
        text = re.sub(r"\[sup\](.*?)\[/sup\]", r"<sup>\1</sup>", text)
        text = re.sub(r"\[sub\](.*?)\[/sub\]", r"<sub>\1</sub>", text)
        text = re.sub(r"\[ol\]|\[/ol\]", r"", text)
        text = re.sub(r"\[ul\]|\[/ul\]", r"", text)
        text = re.sub(r"\[li\](.*?)\[/li\]", r"- \1", text)

    return text
