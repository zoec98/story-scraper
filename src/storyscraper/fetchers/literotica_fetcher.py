"""Literotica-specific fetcher."""

from __future__ import annotations

import codecs
import json
import re
import warnings
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from ..options import StoryScraperOptions, slugify
from . import ProgressCallback
from .auto import Fetcher as AutoFetcher


class Fetcher(AutoFetcher):
    """Fetcher that understands Literotica's React payloads."""

    _STATE_RE = re.compile(r"state='((?:[^'\\]|\\.)*)'")

    def list_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
    ) -> list[str]:
        download_url = options.download_url
        if self._is_series_url(download_url):
            return self._series_list_phase(options, stories_root=stories_root)
        if self._is_story_url(download_url):
            return self._single_story_list_phase(options, stories_root=stories_root)
        return super().list_phase(options, stories_root=stories_root)

    def fetch_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
        force_fetch: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> list[Path]:
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
                data = self._fetch_literotica_chapter(url)
            except Exception as exc:  # pragma: no cover - logged for later review
                self._log_failure(log_file, url, exc)
                continue

            destination.write_bytes(data)
            fetched_files.append(destination)
            if progress_callback:
                progress_callback(index, total, destination, False)

        return fetched_files

    def _series_list_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None,
    ) -> list[str]:
        html = self._fetch_text(options.download_url)
        works = self._extract_series_works(html)
        ordered_urls = [self._chapter_url(work) for work in works]
        ordered_urls = [url for url in ordered_urls if url]

        if not ordered_urls:
            return super().list_phase(options, stories_root=stories_root)

        updated_options = self._update_options_from_series(options, html)
        options = self._sync_options(options, updated_options)

        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        story_dir = base_root / options.effective_slug()
        self._write_download_list(story_dir, ordered_urls)
        return ordered_urls

    def _single_story_list_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None,
    ) -> list[str]:
        html = self._fetch_text(options.download_url)
        canonical_url = self._canonical_story_url(options.download_url)
        ordered_urls = [canonical_url]

        updated_options = self._update_options_from_article(options, html)
        options = self._sync_options(options, updated_options)

        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        story_dir = base_root / options.effective_slug()
        self._write_download_list(story_dir, ordered_urls)
        return ordered_urls

    def _extract_series_works(self, html: str) -> list[dict[str, Any]]:
        state = self._load_state_payload(html)
        if not state:
            return []
        series = state.get("series", {})
        works = series.get("works") or []
        if not isinstance(works, list):
            return []
        return [work for work in works if isinstance(work, dict) and "url" in work]

    def _chapter_url(self, work: dict[str, Any]) -> str:
        slug = work.get("url") or ""
        if not isinstance(slug, str):
            return ""
        return urljoin("https://www.literotica.com/s/", slug.lstrip("/"))

    def _update_options_from_series(
        self,
        options: StoryScraperOptions,
        html: str,
    ) -> StoryScraperOptions:
        state = self._load_state_payload(html)
        if not state:
            return options

        series_data = state.get("series", {}).get("data") or {}
        title = series_data.get("title")
        author = (series_data.get("user") or {}).get("username")

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
                new_options = replace(
                    new_options,
                    chosen_slug=slugify(title),
                )

        if isinstance(author, str) and author.strip():
            author = author.strip()
            new_options = replace(
                new_options,
                author=options.author or author,
                chosen_author=author,
            )

        return new_options

    def _update_options_from_article(
        self,
        options: StoryScraperOptions,
        html: str,
    ) -> StoryScraperOptions:
        metadata = self._extract_article_metadata(html)
        if not metadata:
            return options

        series_info = metadata.get("isPartOf")
        if isinstance(series_info, dict) and series_info.get("url"):
            series_url = str(series_info["url"])
            series_name = series_info.get("name")
            warning_parts = [
                "Literotica: this chapter belongs to a series.",
            ]
            if series_name:
                warning_parts.append(f"Series: {series_name}.")
            warning_parts.append(
                f"Download the full series via: uv run storyscraper {series_url}"
            )
            warnings.warn(" ".join(warning_parts), stacklevel=2)

        headline = metadata.get("headline")
        author_info = metadata.get("author")
        author_name = None
        if isinstance(author_info, dict):
            author_name = author_info.get("name")

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
                new_options = replace(
                    new_options,
                    chosen_slug=slugify(headline),
                )

        if isinstance(author_name, str) and author_name.strip():
            author_name = author_name.strip()
            new_options = replace(
                new_options,
                author=options.author or author_name,
                chosen_author=author_name,
            )

        return new_options

    def _fetch_literotica_chapter(self, url: str) -> bytes:
        if not self._is_story_url(url):
            return self._fetch_bytes(url)

        canonical = self._canonical_story_url(url)
        assembled = bytearray()
        page = 1
        while True:
            page_url = (
                canonical if page == 1 else self._with_page_parameter(canonical, page)
            )
            try:
                content = self._fetch_bytes(page_url)
            except requests.HTTPError as exc:
                if page > 1 and self._is_not_found(exc):
                    break
                raise
            assembled.extend(
                f"<!-- Literotica page {page} {page_url} -->\n".encode("utf-8")
            )
            assembled.extend(content)
            page += 1
        return bytes(assembled)

    def _is_not_found(self, exc: requests.HTTPError) -> bool:
        response = exc.response
        return response is not None and response.status_code == 404

    def _canonical_story_url(self, url: str) -> str:
        parsed = urlsplit(url)
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() != "page"
        ]
        rebuilt = urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(query, doseq=True),
                parsed.fragment,
            )
        )
        return rebuilt.rstrip("?")

    def _with_page_parameter(self, url: str, page: int) -> str:
        parsed = urlsplit(url)
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() != "page"
        ]
        query.append(("page", str(page)))
        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(query, doseq=True),
                parsed.fragment,
            )
        )

    def _extract_article_metadata(self, html: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        for script in scripts:
            data = self._parse_ld_json(script.string)
            if not data:
                continue
            if isinstance(data, list):
                for item in data:
                    result = self._coerce_article(item)
                    if result:
                        return result
            else:
                result = self._coerce_article(data)
                if result:
                    return result
        return None

    def _parse_ld_json(self, text: str | None) -> Any:
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _coerce_article(self, data: Any) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None
        type_value = data.get("@type")
        if isinstance(type_value, str) and type_value.lower() == "article":
            return data
        return None

    def _load_state_payload(self, html: str) -> dict[str, Any] | None:
        match = self._STATE_RE.search(html)
        if not match:
            return None
        raw = match.group(1)
        try:
            decoded = codecs.decode(raw, "unicode_escape")
            return json.loads(decoded)
        except Exception:
            return None

    def _is_series_url(self, url: str) -> bool:
        path = urlsplit(url).path.lower()
        return "/series/" in path

    def _is_story_url(self, url: str) -> bool:
        path = urlsplit(url).path.lower()
        return path.startswith("/s/")
