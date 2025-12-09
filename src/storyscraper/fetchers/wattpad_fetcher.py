"""Wattpad-specific fetcher that reads the table of contents."""

from __future__ import annotations

import warnings
from dataclasses import replace
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..options import StoryScraperOptions, slugify
from .auto import Fetcher as AutoFetcher


class Fetcher(AutoFetcher):
    """Extract Wattpad chapter URLs from the rendered table of contents."""

    toc_selector = "ul.table-of-contents"
    funbar_selector = "#funbar-story span.info"

    def _select_urls(self, base_url: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        toc = soup.select_one(self.toc_selector)
        if toc is None:
            return super()._select_urls(base_url, html)

        seen: set[str] = set()
        ordered: list[str] = []
        locked = 0

        for anchor in toc.find_all("a", href=True):
            if self._is_locked(anchor):
                locked += 1
                continue
            href = anchor.get("href")
            if not isinstance(href, str) or not href.strip():
                continue
            absolute = urljoin(base_url, href)
            if absolute not in seen:
                seen.add(absolute)
                ordered.append(absolute)

        if locked:
            warnings.warn(
                f"Wattpad: skipped {locked} locked chapter(s); unlock them to download the full story.",
                stacklevel=2,
            )

        return ordered or super()._select_urls(base_url, html)

    def postprocess_listing(
        self,
        options: StoryScraperOptions,
        html: str,
        urls: list[str],
    ) -> StoryScraperOptions:
        soup = BeautifulSoup(html, "html.parser")
        info = soup.select_one(self.funbar_selector)
        if info is None:
            return options

        new_options = options
        title_tag = info.select_one("h2.title")
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
                new_options = replace(
                    new_options,
                    name=name,
                    slug=slug,
                    chosen_name=title_text,
                    chosen_slug=chosen_slug or slugify(title_text),
                )

        author_tag = info.select_one("span.author")
        if author_tag:
            author_text = author_tag.get_text(strip=True)
            if author_text.lower().startswith("by "):
                author_text = author_text[3:]
            author_text = author_text.strip()
            if author_text:
                new_options = replace(
                    new_options,
                    author=options.author or author_text,
                    chosen_author=author_text,
                )

        return new_options

    def _is_locked(self, anchor) -> bool:
        classes = anchor.get("class") or []
        if isinstance(classes, str):
            classes = [classes]
        if any(
            cls.strip().lower() == "blocked" for cls in classes if isinstance(cls, str)
        ):
            return True
        if anchor.select_one(".fa-lock") is not None:
            return True
        return False
