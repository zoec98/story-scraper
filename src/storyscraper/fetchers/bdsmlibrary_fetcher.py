"""BDSMLibrary-specific fetcher."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from ..options import StoryScraperOptions, slugify
from .auto import Fetcher as AutoFetcher


class Fetcher(AutoFetcher):
    """Extract chapters and metadata from bdsmlibrary story pages."""

    _TITLE_PREFIX = "BDSM Library - Story:"

    def list_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
    ) -> list[str]:
        html = self._fetch_text(options.download_url)
        soup = BeautifulSoup(html, "html.parser")

        story_id = self._story_id_from_url(options.download_url)
        ordered_urls = self._extract_chapter_urls(
            soup.find_all("a", href=True),
            base_url=options.download_url,
            story_id=story_id,
        )

        updated_options = self._update_options(options, soup)
        options = self._sync_options(options, updated_options)

        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        story_dir = base_root / options.effective_slug()
        self._write_download_list(story_dir, ordered_urls)

        return ordered_urls

    def _fetch_text(self, url: str) -> str:
        return self._fetch_bytes(url).decode("cp1252", errors="replace")

    def _extract_chapter_urls(
        self, anchors: Iterable, *, base_url: str, story_id: str | None
    ) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for anchor in anchors:
            href = anchor.get("href")
            if not isinstance(href, str) or "chapter.php" not in href:
                continue
            parsed = urlparse(href)
            query_story_id = parse_qs(parsed.query).get("storyid", [None])[0]
            if story_id is not None and query_story_id != story_id:
                continue
            absolute = urljoin(base_url, href)
            if absolute not in seen:
                seen.add(absolute)
                ordered.append(absolute)
        return ordered

    def _update_options(
        self, options: StoryScraperOptions, soup: BeautifulSoup
    ) -> StoryScraperOptions:
        title_tag = soup.find("title")
        author_links = soup.find_all(
            "a", href=lambda href: isinstance(href, str) and "author.php" in href
        )
        author_link = next(
            (link for link in author_links if link.get_text(strip=True)), None
        )

        new_options = options

        if title_tag and isinstance(title_tag.string, str):
            title = title_tag.string.strip()
            if title.startswith(self._TITLE_PREFIX):
                title = title[len(self._TITLE_PREFIX) :].strip()
            if title:
                new_options = replace(
                    new_options,
                    name=options.name or title,
                    chosen_name=title,
                )
                if not options.slug:
                    slug_candidate = slugify(title)
                    new_options = replace(
                        new_options,
                        slug=slug_candidate,
                        chosen_slug=slug_candidate,
                    )
                elif not options.chosen_slug:
                    new_options = replace(
                        new_options,
                        chosen_slug=slugify(title),
                    )

        if author_link:
            author_text = author_link.get_text(strip=True)
            if author_text:
                new_options = replace(
                    new_options,
                    author=options.author or author_text,
                    chosen_author=author_text,
                )

        return new_options

    def _story_id_from_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        return parse_qs(parsed.query).get("storyid", [None])[0]
