"""MCStories-specific fetcher with title detection."""

from __future__ import annotations

import re
from dataclasses import replace

from bs4 import BeautifulSoup

from ..options import StoryScraperOptions, slugify
from .auto import Fetcher as AutoFetcher


class Fetcher(AutoFetcher):
    """Fetch MCStories chapters with title/slug inference."""

    def postprocess_listing(
        self,
        options: StoryScraperOptions,
        html: str,
        urls: list[str],
    ) -> StoryScraperOptions:
        soup = BeautifulSoup(html, "html.parser")
        options = self._apply_title(options, soup)
        options = self._apply_author(options, soup)
        return options

    def _apply_title(
        self,
        options: StoryScraperOptions,
        soup: BeautifulSoup,
    ) -> StoryScraperOptions:
        title_tag = soup.select_one("h3.title")
        if title_tag is None:
            return options

        title_text = _normalize_whitespace(
            title_tag.get_text(separator=" ", strip=True)
        )
        if not title_text:
            return options

        new_name = options.name or title_text
        new_slug = options.slug
        chosen_slug = options.chosen_slug

        if not options.slug:
            slug_source = new_name or title_text
            slug_candidate = slugify(slug_source)
            new_slug = slug_candidate
            chosen_slug = slug_candidate

        return replace(
            options,
            name=new_name,
            slug=new_slug,
            chosen_name=title_text,
            chosen_slug=chosen_slug or slugify(title_text),
        )

    def _apply_author(
        self,
        options: StoryScraperOptions,
        soup: BeautifulSoup,
    ) -> StoryScraperOptions:
        if options.author:
            return replace(options, chosen_author=options.author)

        author_tag = soup.select_one("h3.byline")
        if author_tag is None:
            return options

        author_text = _normalize_whitespace(
            author_tag.get_text(separator=" ", strip=True).replace("by ", "", 1)
        )
        if not author_text:
            return options

        return replace(options, chosen_author=author_text)


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
