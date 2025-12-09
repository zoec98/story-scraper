"""Default fetcher that extracts chapter URLs from the starting page."""

from __future__ import annotations

from dataclasses import fields as dataclass_fields
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence
from urllib.parse import ParseResult, urljoin, urlparse

from bs4 import BeautifulSoup

from ..http import fetch_bytes as http_fetch_bytes
from ..options import StoryScraperOptions
from . import ProgressCallback


class Fetcher:
    """Auto fetcher implementation."""

    download_list_filename = "download_urls.txt"
    _OPTION_FIELDS = dataclass_fields(StoryScraperOptions)

    def list_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
    ) -> list[str]:
        html = self._fetch_text(options.download_url)
        ordered_urls = self._select_urls(options.download_url, html)

        updated_options = self.postprocess_listing(
            options=options,
            html=html,
            urls=ordered_urls,
        )
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
        progress_callback: ProgressCallback | None = None,
    ) -> list[Path]:
        """Download HTML chapters listed in download_urls.txt."""

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
                data = self._fetch_bytes(url)
            except (
                Exception
            ) as exc:  # pragma: no cover - network failures mocked in tests
                self._log_failure(log_file, url, exc)
                continue

            destination.write_bytes(data)
            fetched_files.append(destination)
            if progress_callback:
                progress_callback(index, total, destination, False)

        return fetched_files

    def _fetch_text(self, url: str) -> str:
        return self._fetch_bytes(url).decode("utf-8", errors="replace")

    def _fetch_bytes(self, url: str) -> bytes:
        return http_fetch_bytes(url)

    def _select_urls(self, base_url: str, html: str) -> list[str]:
        hrefs = self._extract_links(html)
        canonical = _canonicalize_url(base_url)
        return self._filter_links(base_url, hrefs, canonical)

    def _extract_links(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        hrefs: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href_value = anchor.get("href")
            if isinstance(href_value, str) and href_value:
                hrefs.append(href_value)
            elif isinstance(href_value, Sequence):
                for value in href_value:
                    if isinstance(value, str) and value:
                        hrefs.append(value)
        return hrefs

    def _filter_links(
        self, base_url: str, hrefs: Iterable[str], canonical_url: str | None
    ) -> list[str]:
        parsed_base = urlparse(base_url)
        base_dir = _compute_base_directory(parsed_base.path)
        ordered: list[str] = []

        def add_url(url: str) -> None:
            if url not in ordered:
                ordered.append(url)

        for href in hrefs:
            absolute = urljoin(base_url, href)
            parsed_candidate = urlparse(absolute)
            if _in_scope(parsed_base, parsed_candidate, base_dir):
                add_url(absolute)

        self_urls = [base_url]
        if canonical_url is not None:
            self_urls.append(canonical_url)

        return [
            url
            for url in ordered
            if not any(_urls_equal(url, self_url) for self_url in self_urls)
        ]

    def _load_download_list(self, path: Path) -> list[str]:
        if not path.exists():
            raise FileNotFoundError(
                f"Missing download list at {path}. Run the list-phase first."
            )

        return [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _write_download_list(self, story_dir: Path, urls: list[str]) -> None:
        story_dir.mkdir(parents=True, exist_ok=True)
        destination = story_dir / self.download_list_filename
        with destination.open("w", encoding="utf-8") as handle:
            for url in urls:
                handle.write(f"{url}\n")

    def postprocess_listing(
        self,
        options: StoryScraperOptions,
        html: str,
        urls: list[str],
    ) -> StoryScraperOptions:
        """Hook for subclasses to mutate options after listing but before writing files."""

        return options

    def _sync_options(
        self,
        original: StoryScraperOptions,
        updated: StoryScraperOptions,
    ) -> StoryScraperOptions:
        if original is updated:
            return original

        for field in self._OPTION_FIELDS:
            setattr(original, field.name, getattr(updated, field.name))

        return original

    def _log_failure(self, log_file: Path, url: str, exc: Exception) -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")
        message = f"{timestamp} ERROR {url} -> {exc}\n"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(message)


def _compute_base_directory(path: str) -> str:
    normalized_path = path or "/"
    base_path = PurePosixPath(normalized_path)
    if normalized_path.endswith("/"):
        directory = base_path
    else:
        directory = base_path.parent

    directory_str = str(directory)
    if directory_str in ("", "."):
        directory_str = "/"

    if not directory_str.startswith("/"):
        directory_str = f"/{directory_str}"

    if not directory_str.endswith("/"):
        directory_str = f"{directory_str}/"

    return directory_str


def _in_scope(
    base_parsed: ParseResult, candidate_parsed: ParseResult, base_dir: str
) -> bool:
    return (
        base_parsed.scheme == candidate_parsed.scheme
        and base_parsed.netloc == candidate_parsed.netloc
        and candidate_parsed.path.startswith(base_dir)
    )


def _canonicalize_url(url: str) -> str | None:
    parsed = urlparse(url)
    path = parsed.path
    if not path or path.endswith("/"):
        if not path.endswith("/"):
            path = f"{path}/"
        new_path = f"{path}index.html"
    else:
        new_path = path

    return urljoin(url, new_path)


def _urls_equal(left: str, right: str) -> bool:
    parsed_left = urlparse(left)
    parsed_right = urlparse(right)

    return (
        parsed_left.scheme == parsed_right.scheme
        and parsed_left.netloc == parsed_right.netloc
        and parsed_left.path.rstrip("/") == parsed_right.path.rstrip("/")
    )
