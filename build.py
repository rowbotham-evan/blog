#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import html
import json
import re
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
POSTS_ROOT = ROOT / "posts"

POST_TAB_DIRS = ("tab1", "tab2")

DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
)

SITE_CONFIG_PATH = ROOT / "site.json"
DEFAULT_SITE_CONFIG: dict[str, str] = {
    "document_title": "Evan Rowbotham Blog",
    "nav_title": "Evan Rowbotham",
    "banner_kicker": "BLOG",
    "banner_title": "Evan's Blog (renaming soon).",
    "banner_subtitle": "Discrete Thoughts.",
    "home_intro": "Blorf snizzle wobbleflux drifts through the gloaming while quarky noodles hum quietly.",
}


@dataclass
class Post:
    source_path: Path
    output_path: Path
    href: str
    title: str
    date_display: str
    sort_date: datetime
    done: bool
    references: list[str]
    body_markdown: str


class MetadataError(ValueError):
    pass


def load_site_config() -> dict[str, str]:
    config = DEFAULT_SITE_CONFIG.copy()

    if not SITE_CONFIG_PATH.exists():
        return config

    try:
        raw = json.loads(SITE_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MetadataError(
            f"{SITE_CONFIG_PATH}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(raw, dict):
        raise MetadataError(f"{SITE_CONFIG_PATH}: expected a top-level JSON object")

    for key in DEFAULT_SITE_CONFIG:
        value = raw.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise MetadataError(f"{SITE_CONFIG_PATH}: '{key}' must be a string")
        config[key] = value

    return config


def strip_wrapping_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        return value[1:-1].strip()
    return value


def parse_references_value(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []

    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [strip_wrapping_quotes(part) for part in inner.split(",") if part.strip()]

    if "," in value:
        return [strip_wrapping_quotes(part) for part in value.split(",") if part.strip()]

    return [strip_wrapping_quotes(value)]


def parse_bool(value: str, path: Path) -> bool:
    lowered = value.strip().lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    raise MetadataError(f"{path}: 'done' must be true or false, got: {value!r}")


def parse_date_for_sort(value: str) -> datetime:
    raw = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    try:
        normalized = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min


def parse_metadata_and_body(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    metadata: dict[str, object] = {}
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()

        if not stripped:
            idx += 1
            break

        match = re.match(r"^([A-Za-z][A-Za-z0-9 _-]*)\s*:\s*(.*)$", line)
        if not match:
            raise MetadataError(
                f"{path}: invalid metadata line {idx + 1}. "
                "Expected key: value pairs at the top of the file."
            )

        key = match.group(1).strip().lower()
        value = match.group(2).strip()

        if key == "references":
            refs = parse_references_value(value)
            idx += 1

            while idx < len(lines):
                next_line = lines[idx]
                next_stripped = next_line.strip()

                if not next_stripped:
                    break

                if re.match(r"^[A-Za-z][A-Za-z0-9 _-]*\s*:\s*.*$", next_line):
                    break

                bullet_match = re.match(r"^(?:-|\*)\s+(.+)$", next_stripped)
                ordered_match = re.match(r"^\d+\.\s+(.+)$", next_stripped)
                if bullet_match:
                    refs.append(strip_wrapping_quotes(bullet_match.group(1).strip()))
                    idx += 1
                    continue
                if ordered_match:
                    refs.append(strip_wrapping_quotes(ordered_match.group(1).strip()))
                    idx += 1
                    continue
                break

            metadata[key] = [ref for ref in refs if ref]
            continue

        metadata[key] = strip_wrapping_quotes(value)
        idx += 1

    body = "\n".join(lines[idx:]).strip()

    required = ("title", "date", "done", "references")
    missing = [field for field in required if field not in metadata]
    if missing:
        raise MetadataError(f"{path}: missing required metadata fields: {', '.join(missing)}")

    return metadata, body


def inline_markdown_to_html(text: str) -> str:
    escaped = html.escape(text, quote=False)
    token_map: dict[str, str] = {}

    def add_token(value: str) -> str:
        token = f"@@TOKEN_{len(token_map)}@@"
        token_map[token] = value
        return token

    def code_replacer(match: re.Match[str]) -> str:
        code_text = html.escape(match.group(1), quote=False)
        return add_token(f"<code>{code_text}</code>")

    escaped = re.sub(r"`([^`]+)`", code_replacer, escaped)

    def image_replacer(match: re.Match[str]) -> str:
        alt_text = html.escape(match.group(1), quote=True)
        url = html.escape(match.group(2).strip(), quote=True)
        return f"<img src=\"{url}\" alt=\"{alt_text}\">"

    escaped = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", image_replacer, escaped)

    def link_replacer(match: re.Match[str]) -> str:
        label = match.group(1)
        url = html.escape(match.group(2).strip(), quote=True)
        return f"<a href=\"{url}\">{label}</a>"

    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_replacer, escaped)

    for token, value in token_map.items():
        escaped = escaped.replace(token, value)

    return escaped


def markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    output: list[str] = []
    paragraph_lines: list[str] = []
    list_type: str | None = None
    list_items: list[str] = []
    in_code_block = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        paragraph = "\n".join(line.strip() for line in paragraph_lines).strip()
        if paragraph:
            output.append(f"<p>{inline_markdown_to_html(paragraph)}</p>")
        paragraph_lines = []

    def flush_list() -> None:
        nonlocal list_type, list_items
        if not list_type or not list_items:
            list_type = None
            list_items = []
            return
        output.append(f"<{list_type}>")
        for item in list_items:
            output.append(f"  <li>{inline_markdown_to_html(item.strip())}</li>")
        output.append(f"</{list_type}>")
        list_type = None
        list_items = []

    def flush_code_block() -> None:
        nonlocal code_lines
        code_body = html.escape("\n".join(code_lines), quote=False)
        output.append(f"<pre><code>{code_body}</code></pre>")
        code_lines = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if in_code_block:
            if stripped.startswith("```"):
                in_code_block = False
                flush_code_block()
            else:
                code_lines.append(raw_line)
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            in_code_block = True
            code_lines = []
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = len(heading_match.group(1))
            text = inline_markdown_to_html(heading_match.group(2).strip())
            output.append(f"<h{level}>{text}</h{level}>")
            continue

        bullet_match = re.match(r"^(?:-|\*)\s+(.+)$", stripped)
        ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if bullet_match:
            flush_paragraph()
            if list_type and list_type != "ul":
                flush_list()
            list_type = "ul"
            list_items.append(bullet_match.group(1))
            continue
        if ordered_match:
            flush_paragraph()
            if list_type and list_type != "ol":
                flush_list()
            list_type = "ol"
            list_items.append(ordered_match.group(1))
            continue

        if stripped.startswith("<") and stripped.endswith(">"):
            flush_paragraph()
            flush_list()
            output.append(line)
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    flush_list()

    if in_code_block:
        flush_code_block()

    return "\n".join(output)


def render_post_html(post: Post) -> str:
    article_html = markdown_to_html(post.body_markdown)

    references_html = ""
    if post.references:
        items = []
        for url in post.references:
            safe_url = html.escape(url, quote=True)
            items.append(f'      <li><a href="{safe_url}">{safe_url}</a></li>')
        references_html = (
            "\n    <section class=\"references\">\n"
            "      <h2>References</h2>\n"
            "      <ol>\n"
            + "\n".join(items)
            + "\n      </ol>\n"
            "    </section>\n"
        )

    title = html.escape(post.title)
    date_display = html.escape(post.date_display)

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>{title}</title>
  <link rel=\"icon\" type=\"image/png\" href=\"../../../purple_tile_no_back.png\">
  <link rel=\"stylesheet\" href=\"../../../style.css\">
  <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css\">
  <script defer src=\"https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js\"></script>
  <script defer src=\"https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js\"></script>
  <script defer src=\"../../../script.js\"></script>
</head>
<body>
  <header class=\"post-header\">
    <a class=\"back-link\" href=\"../../../index.html\">&larr; Back</a>
  </header>

  <main class=\"post-content\">
    <h1>{title}</h1>
    <p class=\"date\">{date_display}</p>

{article_html}{references_html}
  </main>
</body>
</html>
"""


def build_index_html(posts: list[Post], site_config: dict[str, str]) -> str:
    def render_rows(posts: list[Post]) -> str:
        lines = []
        for post in posts:
            safe_title = html.escape(post.title)
            safe_date = html.escape(post.date_display)
            safe_href = html.escape(post.href, quote=True)
            lines.append(
                f"      <a class=\"post-row\" href=\"{safe_href}\">\n"
                f"        <span class=\"post-row-title\">{safe_title}</span>\n"
                f"        <span class=\"post-row-date\">{safe_date}</span>\n"
                "      </a>"
            )
        return "\n".join(lines)

    rows_html = render_rows(posts)
    document_title = html.escape(site_config["document_title"])
    banner_kicker = html.escape(site_config["banner_kicker"])
    banner_title = html.escape(site_config["banner_title"])
    banner_subtitle = html.escape(site_config["banner_subtitle"])
    intro_paragraph = html.escape(site_config["home_intro"])

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>{document_title}</title>
  <link rel=\"icon\" type=\"image/png\" href=\"purple_tile_no_back.png\">
  <link rel=\"stylesheet\" href=\"style.css\">
  <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css\">
  <script defer src=\"https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js\"></script>
  <script defer src=\"https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js\"></script>
  <script defer src=\"script.js\"></script>
</head>
<body>
  <main>
    <section class=\"landing-banner\" aria-label=\"Site introduction\">
      <p class=\"banner-kicker\">{banner_kicker}</p>
      <h1>{banner_title}</h1>
      <p class=\"banner-subtitle\">{banner_subtitle}</p>
    </section>
    <p class=\"home-intro\">{intro_paragraph}</p>
    <section class=\"post-list\" aria-label=\"Posts\">
{rows_html}
    </section>
  </main>
</body>
</html>
"""


def load_posts() -> list[Post]:
    posts: list[Post] = []

    for tab_key in POST_TAB_DIRS:
        tab_dir = POSTS_ROOT / tab_key
        if not tab_dir.exists():
            continue

        for source_path in sorted(tab_dir.rglob("post.md")):
            metadata, body_markdown = parse_metadata_and_body(source_path)

            title = str(metadata["title"])
            date_display = str(metadata["date"])
            done = parse_bool(str(metadata["done"]), source_path)
            references = [str(ref) for ref in metadata.get("references", [])]

            output_path = source_path.with_suffix(".html")
            href = output_path.relative_to(ROOT).as_posix()

            posts.append(
                Post(
                    source_path=source_path,
                    output_path=output_path,
                    href=href,
                    title=title,
                    date_display=date_display,
                    sort_date=parse_date_for_sort(date_display),
                    done=done,
                    references=references,
                    body_markdown=body_markdown,
                )
            )

    return posts


def build() -> None:
    site_config = load_site_config()
    posts = load_posts()
    published_posts: list[Post] = []

    for post in posts:
        if post.done:
            rendered = render_post_html(post)
            post.output_path.write_text(rendered, encoding="utf-8")
            published_posts.append(post)
        elif post.output_path.exists():
            post.output_path.unlink()

    published_posts.sort(key=lambda post: (post.sort_date, post.title), reverse=True)

    index_html = build_index_html(published_posts, site_config)
    (ROOT / "index.html").write_text(index_html, encoding="utf-8")

    published_count = len(published_posts)
    print(f"Published {published_count} posts.")


def source_snapshot() -> dict[str, int]:
    snapshot: dict[str, int] = {}
    for path in sorted(POSTS_ROOT.rglob("post.md")):
        snapshot[path.as_posix()] = path.stat().st_mtime_ns
    if SITE_CONFIG_PATH.exists():
        snapshot[SITE_CONFIG_PATH.as_posix()] = SITE_CONFIG_PATH.stat().st_mtime_ns
    return snapshot


def watch_and_build(interval_seconds: float = 0.5) -> None:
    print(f"Watching for changes every {interval_seconds:.2f}s. Press Ctrl+C to stop.")
    build()
    previous = source_snapshot()

    try:
        while True:
            time.sleep(interval_seconds)
            current = source_snapshot()
            if current == previous:
                continue

            changed_paths = sorted(set(current).symmetric_difference(previous))
            changed_paths.extend(
                path
                for path in sorted(set(current).intersection(previous))
                if current[path] != previous[path]
            )
            if changed_paths:
                preview = ", ".join(changed_paths[:3])
                if len(changed_paths) > 3:
                    preview += f", +{len(changed_paths) - 3} more"
                print(f"Change detected: {preview}")

            build()
            previous = current
    except KeyboardInterrupt:
        print("\nStopped watching.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the blog from Markdown sources.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously rebuild when source files change.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Polling interval in seconds when using --watch (default: 0.5).",
    )
    args = parser.parse_args()

    if args.watch:
        watch_and_build(interval_seconds=max(args.interval, 0.1))
    else:
        build()
