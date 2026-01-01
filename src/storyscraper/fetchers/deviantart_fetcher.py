"""DeviantArt fetcher that treats a URL as a single chapter."""

from __future__ import annotations

from dataclasses import replace
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

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
        if self._is_gallery_url(options.download_url):
            first_html = self._fetch_text(options.download_url)
            first_soup = BeautifulSoup(first_html, "html.parser")
            ordered_urls = self._collect_gallery_urls(
                options.download_url,
                first_html,
                first_soup,
                options,
            )
            updated_options = self._update_options_from_metadata(options, first_soup)
            updated_options = self._update_options_from_gallery_title(
                updated_options,
                first_html,
                original_options=options,
            )
            options = self._sync_options(options, updated_options)

            base_root = (
                Path(stories_root) if stories_root is not None else Path("stories")
            )
            story_dir = base_root / options.effective_slug()
            self._write_download_list(story_dir, ordered_urls)
            return ordered_urls

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

    def _update_options_from_gallery_title(
        self,
        options: StoryScraperOptions,
        html: str,
        *,
        original_options: StoryScraperOptions,
    ) -> StoryScraperOptions:
        title = self._extract_gallery_title(html)
        if not title:
            return options

        new_options = options
        title = title.strip()
        if title:
            new_options = replace(
                new_options,
                name=original_options.name or title,
                chosen_name=title,
            )
            if not original_options.slug:
                slug_candidate = slugify(title)
                new_options = replace(
                    new_options,
                    slug=slug_candidate,
                    chosen_slug=slug_candidate,
                )
            elif not options.chosen_slug:
                new_options = replace(new_options, chosen_slug=slugify(title))
        return new_options

    def _extract_gallery_title(self, html: str) -> str | None:
        state = self._extract_initial_state(html)
        if state is None:
            return None
        gallection = state.get("gallectionSection")
        if not isinstance(gallection, dict):
            return None
        folder_id = gallection.get("selectedFolderId")
        if not isinstance(folder_id, int):
            return None
        entities = state.get("@@entities")
        if not isinstance(entities, dict):
            return None
        folders = entities.get("galleryFolder")
        if not isinstance(folders, dict):
            return None
        folder = folders.get(str(folder_id))
        if not isinstance(folder, dict):
            folder = folders.get(folder_id)
        if not isinstance(folder, dict):
            return None
        name = folder.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        return None

    def _is_gallery_url(self, url: str) -> bool:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        return len(parts) >= 2 and parts[1] == "gallery"

    def _collect_gallery_urls(
        self,
        base_url: str,
        first_html: str,
        soup: BeautifulSoup,
        options: StoryScraperOptions,
    ) -> list[str]:
        parsed_base = urlparse(base_url)
        username = self._extract_gallery_username(parsed_base.path)
        ordered: list[str] = []
        seen: set[str] = set()
        seen_pages: set[str] = set()

        next_url: str | None = base_url
        current_soup: BeautifulSoup | None = soup
        current_html: str | None = first_html
        total_pages: int | None = None

        while next_url:
            if next_url in seen_pages:
                break
            seen_pages.add(next_url)

            if current_soup is None:
                current_html = self._fetch_text(next_url)
                current_soup = BeautifulSoup(current_html, "html.parser")

            page_number, page_total = self._extract_gallery_page_info(
                current_html or "",
                next_url,
            )
            if page_total is not None:
                total_pages = page_total
            self._log_gallery_page_fetch(
                options=options,
                url=next_url,
                page_number=page_number,
                total_pages=total_pages,
            )

            new_count = self._extract_gallery_urls_from_soup(
                base_url=next_url,
                soup=current_soup,
                username=username,
                ordered=ordered,
                seen=seen,
            )
            self._log_gallery_page_result(
                options=options,
                page_number=page_number,
                total_pages=total_pages,
                new_count=new_count,
            )
            next_url = self._extract_next_gallery_page(current_soup, next_url)
            if total_pages is not None and page_number is not None:
                if page_number >= total_pages:
                    break
            current_soup = None
            current_html = None

        return ordered

    def _extract_gallery_urls_from_soup(
        self,
        *,
        base_url: str,
        soup: BeautifulSoup,
        username: str | None,
        ordered: list[str],
        seen: set[str],
    ) -> int:
        new_count = 0
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not isinstance(href, str) or not href:
                continue
            absolute = urljoin(base_url, href)
            cleaned = self._normalize_art_url(absolute)
            if cleaned is None:
                continue
            if username and f"/{username}/art/" not in urlparse(cleaned).path:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                ordered.append(cleaned)
                new_count += 1
        return new_count

    def _extract_next_gallery_page(
        self, soup: BeautifulSoup, base_url: str
    ) -> str | None:
        tag = soup.find("link", rel="next")
        if tag is None:
            return None
        href = tag.get("href")
        if not isinstance(href, str) or not href:
            return None
        return urljoin(base_url, href)

    def _extract_gallery_page_info(
        self,
        html: str,
        url: str,
    ) -> tuple[int | None, int | None]:
        page_number: int | None = None
        total_pages: int | None = None

        state = self._extract_initial_state(html)
        if state is not None:
            page_info = state.get("pageInfo")
            if isinstance(page_info, dict):
                current_page = page_info.get("currentPage")
                page_total = page_info.get("totalPages")
                if isinstance(current_page, int):
                    page_number = current_page
                if isinstance(page_total, int):
                    total_pages = page_total

        if page_number is None:
            parsed = urlparse(url)
            page_values = parse_qs(parsed.query).get("page")
            if page_values and page_values[0].isdigit():
                page_number = int(page_values[0])
            else:
                page_number = 1

        return page_number, total_pages

    def _extract_initial_state(self, html: str) -> dict[str, object] | None:
        match = re.search(
            r'window\.__INITIAL_STATE__\s*=\s*JSON\.parse\("(.*?)"\);',
            html,
            re.DOTALL,
        )
        if match is None:
            return None
        raw = match.group(1)
        try:
            decoded = raw.encode("utf-8").decode("unicode_escape")
            parsed = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if isinstance(parsed, dict):
            return parsed
        return None

    def _log_gallery_page_fetch(
        self,
        *,
        options: StoryScraperOptions,
        url: str,
        page_number: int | None,
        total_pages: int | None,
    ) -> None:
        if options.quiet or not options.verbose:
            return
        page_label = self._format_gallery_page_label(page_number, total_pages)
        print(f"DeviantArt gallery: fetching page {page_label}: {url}")

    def _log_gallery_page_result(
        self,
        *,
        options: StoryScraperOptions,
        page_number: int | None,
        total_pages: int | None,
        new_count: int,
    ) -> None:
        if options.quiet or not options.verbose:
            return
        page_label = self._format_gallery_page_label(page_number, total_pages)
        print(f"DeviantArt gallery: page {page_label} found {new_count} art URL(s)")

    def _format_gallery_page_label(
        self,
        page_number: int | None,
        total_pages: int | None,
    ) -> str:
        if total_pages is not None and page_number is not None:
            return f"{page_number}/{total_pages}"
        if page_number is not None:
            return str(page_number)
        return "unknown"

    def _extract_gallery_username(self, path: str) -> str | None:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[1] == "gallery":
            return parts[0]
        return None

    def _normalize_art_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        if not parsed.netloc.endswith("deviantart.com"):
            return None
        if "/art/" not in parsed.path:
            return None
        scheme = parsed.scheme or "https"
        return urlunparse((scheme, parsed.netloc, parsed.path, "", "", ""))

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
