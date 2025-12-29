"""DeviantArt fetcher that treats a URL as a single chapter."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from bs4 import BeautifulSoup

from ..options import StoryScraperOptions, slugify
from .auto import Fetcher as AutoFetcher


class Fetcher(AutoFetcher):
    """Fetch DeviantArt pages without chapter discovery."""

    og_title_selector = "meta[property='og:title']"
    og_url_selector = "meta[property='og:url']"
    title_selector = "title"
    literature_heading = "Literature Text"

    def list_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
    ) -> list[str]:
        html = self._fetch_text(options.download_url)
        soup = BeautifulSoup(html, "html.parser")

        if not self._has_literature_content(soup):
            self._warn_non_literature(options.download_url)
            return []

        canonical_url = self._extract_meta_content(soup, self.og_url_selector)
        ordered_urls = [canonical_url or options.download_url]

        updated_options = self._update_options_from_metadata(options, soup)
        options = self._sync_options(options, updated_options)

        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        story_dir = base_root / options.effective_slug()
        self._write_download_list(story_dir, ordered_urls)
        return ordered_urls

    def _update_options_from_metadata(
        self, options: StoryScraperOptions, soup: BeautifulSoup
    ) -> StoryScraperOptions:
        title, author = self._extract_metadata(soup)
        new_options = options

        if isinstance(title, str) and title.strip():
            title = title.strip()
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
                new_options = replace(new_options, chosen_slug=slugify(title))

        if isinstance(author, str) and author.strip():
            author = author.strip().lstrip("@")
            new_options = replace(
                new_options,
                author=options.author or author,
                chosen_author=author,
            )

        return new_options

    def _extract_metadata(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        title = None
        author = None

        og_title = self._extract_meta_content(soup, self.og_title_selector)
        if og_title:
            og_title = og_title.strip()
            split_title, split_author = self._split_title_author(og_title)
            title = title or split_title
            author = author or split_author
        if not title or not author:
            page_title = self._extract_title_tag(soup)
            if page_title:
                split_title, split_author = self._split_title_author(page_title)
                title = title or split_title
                author = author or split_author

        return title, author

    def _extract_meta_content(self, soup: BeautifulSoup, selector: str) -> str | None:
        tag = soup.select_one(selector)
        if tag is None:
            return None
        content = tag.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        return None

    def _extract_title_tag(self, soup: BeautifulSoup) -> str | None:
        tag = soup.select_one(self.title_selector)
        if tag is None:
            return None
        text = tag.get_text(strip=True)
        return text or None

    def _has_literature_content(self, soup: BeautifulSoup) -> bool:
        for heading in soup.find_all("h2"):
            if heading.get_text(strip=True) != self.literature_heading:
                continue
            section = heading.find_parent("section")
            if section is None:
                continue
            content_div = section.find("div", recursive=False)
            if content_div is not None:
                return True
        return False

    def _warn_non_literature(self, url: str) -> None:
        import warnings

        warnings.warn(
            f"DeviantArt: URL does not contain content that can be recognized as a Literature Deviation: {url}",
            stacklevel=2,
        )

    def _split_title_author(self, title: str) -> tuple[str | None, str | None]:
        suffix = " on DeviantArt"
        if suffix not in title:
            return title, None
        prefix = title.split(suffix, 1)[0].strip()
        if " by " not in prefix:
            return prefix or None, None
        story_title, author = prefix.rsplit(" by ", 1)
        return story_title.strip() or None, author.strip() or None
