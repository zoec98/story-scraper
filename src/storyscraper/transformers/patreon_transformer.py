"""Patreon-specific transformer that extracts post content from __NEXT_DATA__."""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .auto import Transformer as AutoTransformer
from ..options import StoryScraperOptions, slugify


class Transformer(AutoTransformer):
    """Extract post HTML from the embedded Next.js state and convert to Markdown."""

    _NEXT_DATA_RE = re.compile(
        r'__NEXT_DATA__"?\s*type="application/json">(.*?)</script>', re.S
    )

    def transform_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
        progress_callback=None,
    ) -> list[Path]:  # type: ignore[override]
        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        story_dir = base_root / options.effective_slug()
        html_dir = story_dir / "html"
        markdown_dir = story_dir / "markdown"
        log_file = story_dir / "transform.log"

        if not html_dir.exists():
            raise FileNotFoundError(
                f"Missing HTML directory at {html_dir}. Run the fetch phase first."
            )

        markdown_dir.mkdir(parents=True, exist_ok=True)

        generated: list[Path] = []
        html_files = sorted(html_dir.glob("*.html"))
        total = len(html_files)
        for index, html_path in enumerate(html_files, start=1):
            try:
                html_text = html_path.read_text(encoding="utf-8")
                markdown = self._convert_html_to_markdown(html_text)
                basename = self._derive_basename(
                    html_text, index, options.effective_slug()
                )
                destination = markdown_dir / f"{basename}.md"
                destination.write_text(markdown, encoding="utf-8")
                generated.append(destination)
                if progress_callback:
                    progress_callback(index, total, destination, False)
            except Exception as exc:  # pragma: no cover - logged for later review
                self._log_failure(log_file, html_path, exc)

        return generated

    def _convert_html_to_markdown(self, html: str) -> str:
        content_html, title = self._extract_content_and_title(html)
        if content_html:
            markdown = super()._convert_html_to_markdown(content_html)
            markdown = self._sanitize_markdown(markdown)
            if title:
                return f"# {title}\n\n{markdown.lstrip()}"
            return markdown
        return super()._convert_html_to_markdown(html)

    def _extract_content_and_title(self, html: str) -> tuple[str | None, str | None]:
        match = self._NEXT_DATA_RE.search(html)
        if not match:
            return None, None
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None, None

        page_props = data.get("props", {}).get("pageProps", {})
        post = (
            page_props.get("bootstrapEnvelope", {})
            .get("pageBootstrap", {})
            .get("post", {})
        )
        post_data = post.get("data", {}) if isinstance(post, dict) else {}
        attributes = (
            post_data.get("attributes", {}) if isinstance(post_data, dict) else {}
        )

        content_html = (
            attributes.get("content") if isinstance(attributes, dict) else None
        )
        title = attributes.get("title") if isinstance(attributes, dict) else None

        if isinstance(content_html, str):
            soup = BeautifulSoup(content_html, "html.parser")
            for marker in soup.find_all(
                string=lambda s: isinstance(s, str) and "in collection" in s.lower()
            ):
                parent = marker.parent
                if parent:
                    parent.decompose()
            cleaned_html = str(soup)
            return cleaned_html, title if isinstance(title, str) else None
        return None, None

    def _sanitize_markdown(self, html: str) -> str:
        """Replace fence-like tilde lines with a Markdown HR to avoid code blocks."""

        return re.sub(r"^[ \t]*~{3,}[ \t]*$", "---", html, flags=re.MULTILINE)

    def _derive_basename(self, html: str, index: int, slug_value: str) -> str:
        _, title = self._extract_content_and_title(html)
        if not title:
            title = self._extract_fallback_title(html)
        if not title:
            return f"{slug_value}-{index:03d}"

        chapter = self._parse_number(title, r"chapter\s*(\d+)")
        part = self._parse_number(title, r"part\s*(\d+)")
        prefix_slug = self._prefix_slug(title)

        if chapter is not None:
            base = prefix_slug or slug_value
            suffix = f"{chapter:03d}"
            if part is not None:
                suffix = f"{suffix}-{part}"
            return f"{base}-{suffix}"

        if part is not None:
            base = prefix_slug or slug_value
            return f"{base}-{part:03d}"

        return f"{slug_value}-{index:03d}"

    def _parse_number(self, title: str, pattern: str) -> int | None:
        match = re.search(pattern, title, re.I)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _prefix_slug(self, title: str) -> str | None:
        chapter_match = re.search(r"(chapter|part)\s*\d+", title, re.I)
        prefix = title[: chapter_match.start()] if chapter_match else ""
        prefix = prefix.strip(" -_:")
        if not prefix:
            return None
        return slugify(prefix)

    def _extract_fallback_title(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            text = soup.title.string.strip()
            return text or None
        return None
