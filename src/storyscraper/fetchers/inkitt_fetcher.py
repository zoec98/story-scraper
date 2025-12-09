"""Inkitt-specific fetcher that reads the chapter dropdown."""

from __future__ import annotations

import json
import warnings
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..options import StoryScraperOptions, slugify
from .auto import Fetcher as AutoFetcher


class Fetcher(AutoFetcher):
    """Extract Inkitt chapter URLs from the story page."""

    chapter_list_selector = "ul.nav.nav-list.chapter-list-dropdown"
    ld_json_selector = 'script[type="application/ld+json"]'

    def list_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
    ) -> list[str]:
        html = self._fetch_text(options.download_url)
        soup = BeautifulSoup(html, "html.parser")

        ordered_urls, locked_count = self._extract_chapters(
            soup, base_url=options.download_url
        )
        if locked_count:
            warnings.warn(
                f"Inkitt: skipped {locked_count} locked chapter(s); unlock them to download the full story.",
                stacklevel=2,
            )

        updated_options = self._update_options_from_metadata(options, soup)
        options = self._sync_options(options, updated_options)

        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        story_dir = base_root / options.effective_slug()
        self._write_download_list(story_dir, ordered_urls)

        return ordered_urls

    def _extract_chapters(
        self, soup: BeautifulSoup, *, base_url: str
    ) -> tuple[list[str], int]:
        container = soup.select_one(self.chapter_list_selector)
        if container is None:
            return super()._select_urls(base_url, str(soup)), 0  # type: ignore[arg-type]

        ordered: list[str] = []
        seen: set[str] = set()
        locked = 0

        for li in container.find_all("li"):
            anchor = li.find("a", class_="chapter-link", href=True)
            if anchor is None:
                continue
            href = anchor.get("href")
            if not isinstance(href, str) or not href.strip():
                continue
            absolute = urljoin(base_url, href)
            if li.find(class_="chapter-patron-icon"):
                locked += 1
                continue
            if absolute not in seen:
                seen.add(absolute)
                ordered.append(absolute)

        return ordered, locked

    def _update_options_from_metadata(
        self, options: StoryScraperOptions, soup: BeautifulSoup
    ) -> StoryScraperOptions:
        metadata = self._extract_article_metadata(soup)
        if not metadata:
            return options

        headline = metadata.get("headline")
        author = None
        author_data = metadata.get("author")
        if isinstance(author_data, dict):
            author = author_data.get("name")

        new_options = options
        if isinstance(headline, str) and headline.strip():
            headline = headline.strip()
            new_options = replace(
                new_options,
                name=options.name or headline,
                chosen_name=headline,
            )
            if not options.slug:
                slug_candidate = slugify(headline)
                new_options = replace(
                    new_options,
                    slug=slug_candidate,
                    chosen_slug=slug_candidate,
                )
            elif not options.chosen_slug:
                new_options = replace(new_options, chosen_slug=slugify(headline))

        if isinstance(author, str) and author.strip():
            author = author.strip()
            new_options = replace(
                new_options,
                author=options.author or author,
                chosen_author=author,
            )

        return new_options

    def _extract_article_metadata(self, soup: BeautifulSoup) -> dict[str, Any] | None:
        scripts = soup.select(self.ld_json_selector)
        for script in scripts:
            text = script.string
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type", "").lower() == "article":
                return data
        return None
