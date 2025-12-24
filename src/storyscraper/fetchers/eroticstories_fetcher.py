"""EroticStories.com fetcher with multi-part detection."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..options import StoryScraperOptions, slugify
from .auto import Fetcher as AutoFetcher


class Fetcher(AutoFetcher):
    """Extract single-part or multi-part story URLs and metadata."""

    def list_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
    ) -> list[str]:
        html = self._fetch_text(options.download_url)
        soup = BeautifulSoup(html, "html.parser")

        story_id = self._story_id_from_url(options.download_url)
        parts_url = self._find_parts_url(soup, options.download_url, story_id)

        metadata_html = html
        ordered_urls: list[str]
        if parts_url:
            parts_html = self._fetch_text(parts_url)
            metadata_html = parts_html
            ordered_urls = self._extract_parts(parts_html, base_url=parts_url)
            if not ordered_urls:
                ordered_urls = [options.download_url]
        else:
            ordered_urls = [options.download_url]

        updated_options = self._update_options(options, metadata_html)
        options = self._sync_options(options, updated_options)

        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        story_dir = base_root / options.effective_slug()
        self._write_download_list(story_dir, ordered_urls)

        return ordered_urls

    def fetch_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
        force_fetch: bool = False,
        progress_callback=None,
    ) -> list[Path]:
        """Download chapters, stitching rest pages when present."""

        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        slug_value = options.effective_slug()

        story_dir = base_root / slug_value
        story_dir.mkdir(parents=True, exist_ok=True)
        urls_file = story_dir / self.download_list_filename
        html_dir = story_dir / "html"
        html_dir.mkdir(parents=True, exist_ok=True)
        log_file = story_dir / "fetch.log"

        urls = self._load_download_list(urls_file)
        fetched_files: list[Path] = []

        total = len(urls)

        for index, url in enumerate(urls, start=1):
            destination = html_dir / f"{slug_value}-{index:03d}.html"
            if destination.exists() and not force_fetch:
                if progress_callback:
                    progress_callback(index, total, destination, True)
                continue
            try:
                synthetic_html = self._fetch_and_stitch(url)
            except (
                Exception
            ) as exc:  # pragma: no cover - network failures mocked in tests
                self._log_failure(log_file, url, exc)
                continue

            destination.write_text(synthetic_html, encoding="utf-8")
            fetched_files.append(destination)
            if progress_callback:
                progress_callback(index, total, destination, False)

        return fetched_files

    def _fetch_text(self, url: str) -> str:
        return self._fetch_bytes(url).decode("cp1252", errors="replace")

    def _find_parts_url(
        self, soup: BeautifulSoup, base_url: str, story_id: str | None
    ) -> str | None:
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not isinstance(href, str) or "parts.php" not in href:
                continue
            parsed = urlparse(href)
            query_id = parse_qs(parsed.query).get("id", [None])[0]
            if story_id and query_id and query_id != story_id:
                continue
            return urljoin(base_url, href)
        return None

    def _extract_parts(self, html: str, *, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        ordered: list[str] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not isinstance(href, str) or "story.php" not in href:
                continue
            parsed = urlparse(href)
            story_id = parse_qs(parsed.query).get("id", [None])[0]
            if not story_id:
                continue
            absolute = urljoin(base_url, href)
            if absolute in seen:
                continue
            seen.add(absolute)
            ordered.append(absolute)
        return ordered

    def _fetch_and_stitch(self, url: str) -> str:
        primary_html = self._fetch_text(url)
        primary_soup = BeautifulSoup(primary_html, "html.parser")
        rest_url = self._find_rest_url(primary_soup, base_url=url)

        rest_soup: BeautifulSoup | None = None
        if rest_url:
            rest_html = self._fetch_text(rest_url)
            rest_soup = BeautifulSoup(rest_html, "html.parser")

        content_blocks = []
        primary_block = self._extract_content_block(primary_soup)
        if primary_block:
            content_blocks.append(primary_block)
        if rest_soup:
            rest_block = self._extract_content_block(rest_soup)
            if rest_block:
                content_blocks.append(rest_block)

        return self._build_synthetic_html(
            primary_soup=primary_soup,
            secondary_soup=rest_soup,
            content_blocks=content_blocks,
        )

    def _find_rest_url(self, soup: BeautifulSoup, *, base_url: str) -> str | None:
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not isinstance(href, str):
                continue
            if "rest=1" in href:
                return urljoin(base_url, href)
        return None

    def _extract_content_block(self, soup: BeautifulSoup) -> Tag | None:
        anchor = soup.find("a", attrs={"name": "textstart"})
        if not anchor:
            return None
        parent = anchor.parent if isinstance(anchor.parent, Tag) else anchor

        # Skip control boilerplate before the story text
        collecting = False
        filtered_children = []
        for child in list(parent.children):
            if not collecting:
                if isinstance(child, Tag):
                    text = child.get_text(" ", strip=True).lower()
                    if text and not self._is_chrome_text(text):
                        collecting = True
                elif str(child).strip():
                    collecting = True
            if collecting:
                filtered_children.append(child)

        if not filtered_children:
            return parent

        cleaned = BeautifulSoup("", "html.parser").new_tag("div")
        for child in filtered_children:
            cleaned.append(child)
        return cleaned

    def _is_chrome_text(self, text: str) -> bool:
        chrome_markers = [
            "you can change the width",
            "use how much percent of the screen width",
            "options:",
            "don't forget to vote",
            "click here to read the first",
            "show all parts",
        ]
        return any(marker in text for marker in chrome_markers)

    def _build_synthetic_html(
        self,
        *,
        primary_soup: BeautifulSoup,
        secondary_soup: BeautifulSoup | None,
        content_blocks: list[Tag],
    ) -> str:
        doc = BeautifulSoup("", "html.parser")
        html_tag = doc.new_tag("html")
        head_tag = doc.new_tag("head")
        body_tag = doc.new_tag("body")
        doc.append(html_tag)
        html_tag.append(head_tag)
        html_tag.append(body_tag)

        title_text = self._extract_title(primary_soup) or ""
        author_text = self._extract_author(primary_soup) or ""
        if not title_text and secondary_soup:
            title_text = self._extract_title(secondary_soup) or ""
        if not author_text and secondary_soup:
            author_text = self._extract_author(secondary_soup) or ""

        title_tag = doc.new_tag("title")
        title_tag.string = title_text or "Story"
        head_tag.append(title_tag)
        if author_text:
            author_meta = doc.new_tag(
                "meta", attrs={"name": "author", "content": author_text}
            )
            head_tag.append(author_meta)

        content_wrapper = doc.new_tag("div", id="content")
        for block in content_blocks:
            content_wrapper.append(block)
        body_tag.append(content_wrapper)

        return doc.prettify(formatter="html")

    def _update_options(
        self, options: StoryScraperOptions, html: str
    ) -> StoryScraperOptions:
        soup = BeautifulSoup(html, "html.parser")
        title = self._extract_title(soup)
        author = self._extract_author(soup)

        new_options = options

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
                new_options = replace(new_options, chosen_slug=slugify(title))

        if author:
            new_options = replace(
                new_options,
                author=options.author or author,
                chosen_author=author,
            )

        return new_options

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(" ", strip=True)
            normalized = self._normalize_title(text)
            if normalized:
                return normalized

        story_anchor = self._find_story_anchor(soup)
        if story_anchor:
            text = story_anchor.get_text(" ", strip=True)
            normalized = self._normalize_title(text)
            if normalized:
                return normalized

        if soup.title and isinstance(soup.title.string, str):
            raw = soup.title.string.strip()
            if ":" in raw:
                raw = raw.split(":")[-1].strip()
            normalized = self._normalize_title(raw)
            if normalized:
                return normalized

        return None

    def _normalize_title(self, text: str) -> str:
        collapsed = " ".join(text.split())
        if not collapsed:
            return ""
        match = re.match(r"(.+?)(?:\s*[\[(].*)?$", collapsed)
        candidate = match.group(1) if match else collapsed
        candidate = candidate.strip(":- ")
        return candidate

    def _extract_author(self, soup: BeautifulSoup) -> str | None:
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if isinstance(href, str) and "author.php" in href:
                text = anchor.get_text(strip=True)
                if text:
                    return text
        return None

    def _story_id_from_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        return parse_qs(parsed.query).get("id", [None])[0]

    def _find_story_anchor(self, soup: BeautifulSoup) -> Tag | None:
        anchors: Iterable = soup.find_all(
            "a", href=lambda href: isinstance(href, str) and "story.php" in href
        )
        for anchor in anchors:
            text = anchor.get_text(" ", strip=True)
            if not text:
                continue
            lowered = text.lower()
            if lowered in {"next part", "prev part", "previous part"}:
                continue
            if not anchor.find("b") and not anchor.find("strong"):
                continue
            return anchor
        return None
