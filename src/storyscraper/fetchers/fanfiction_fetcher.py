"""FanFiction.Net fetcher that parses the chapter selector."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..options import StoryScraperOptions, slugify
from .auto import Fetcher as AutoFetcher


class Fetcher(AutoFetcher):
    """Fetch stories hosted on fanfiction.net."""

    _CHAPTER_SELECT_ID = "chap_select"
    _TITLE_SELECTOR = "b.xcontrast_txt"
    _AUTHOR_SELECTOR = "a.xcontrast_txt[href^='/u/']"

    def _select_urls(self, base_url: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        select = soup.find(id=self._CHAPTER_SELECT_ID)
        base_story_url, slug = self._story_base_url(base_url)

        if select is None:
            return [base_url]

        ordered: list[str] = []
        for option in select.find_all("option"):
            value = option.get("value")
            if not value:
                continue
            if isinstance(value, list):
                value = value[0] if value else ""
            chapter_url = self._chapter_url(base_story_url, str(value), slug)
            ordered.append(chapter_url)

        return ordered or [base_url]

    def postprocess_listing(
        self,
        options: StoryScraperOptions,
        html: str,
        urls: list[str],
    ) -> StoryScraperOptions:
        soup = BeautifulSoup(html, "html.parser")
        updated = options

        title_tag = soup.select_one(self._TITLE_SELECTOR)
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            if title_text:
                name = options.name or title_text
                slug = options.slug
                chosen_slug = options.chosen_slug
                if not options.slug:
                    slug_candidate = slugify(name or title_text)
                    slug = slug_candidate
                    chosen_slug = slug_candidate
                updated = replace(
                    updated,
                    name=name,
                    slug=slug,
                    chosen_name=title_text,
                    chosen_slug=chosen_slug or slugify(title_text),
                )

        author_tag = soup.select_one(self._AUTHOR_SELECTOR)
        if author_tag:
            author_text = author_tag.get_text(strip=True)
            if author_text:
                updated = replace(
                    updated,
                    author=options.author or author_text,
                    chosen_author=author_text,
                )

        return updated

    def _story_base_url(self, url: str) -> tuple[str, str | None]:
        parsed = urlparse(url)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) < 2 or segments[0].lower() != "s":
            raise ValueError("FanFiction.Net URLs must follow /s/<story_id>/...")

        story_id = segments[1]
        slug = segments[3] if len(segments) > 3 else None

        base = f"{parsed.scheme}://{parsed.netloc}/s/{story_id}/"
        return base, slug

    def _chapter_url(self, base: str, chapter: str, slug: str | None) -> str:
        if slug:
            return urljoin(base, f"{chapter}/{slug}")
        return urljoin(base, chapter)
