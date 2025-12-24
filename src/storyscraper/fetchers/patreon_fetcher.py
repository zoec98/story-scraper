"""Patreon collection fetcher.

Source: user-provided-data/patreon/loader-analysis.md

## Patreon collection loader analysis (Harem House Chapters, collection 1374355)

- The saved HTML (`hhc-index.html`) is a Next.js shell. The `__NEXT_DATA__` payload only contains bootstrap metadata (campaign, creator, collection id) and a `links.self` pointing at `https://www.patreon.com/api/collection/1374355`. There are **no posts** or pagination cursors serialized server-side.
- The visible “Load more” behavior must therefore be driven by client-side API calls. Patreon collections use the `/api/collection/{id}` and related endpoints with pagination (typically `page[size]=N` and a `cursor`/`links.next` for subsequent pages). The bootstrap includes no posts, so the client fetches the first page on load, then uses “Load more” to request the next cursor until exhaustion.
- The collection title shows “23 posts”; assuming the usual page sizes (10 or 20), this means at least one additional fetch (20 + 3) and possibly more if the page size is smaller. The absence of posts in the HTML means you must **replay the API pagination until the returned `links.next` is absent** to fully expand the list—one “Load more” click may not be enough.
- Cookies/session are required (the page was fetched with Firefox cookies). Any automated fetcher will need to:
  1) call the collection API to get the first page of posts, 2) follow `links.next` (or `meta.pagination` cursor) repeatedly, and 3) stop when no next link/cursor is returned. The static HTML cannot be relied on for post data.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..http import get as http_get
from ..options import StoryScraperOptions, slugify
from .auto import Fetcher as AutoFetcher


class Fetcher(AutoFetcher):
    """List-phase fetcher for Patreon collections (download_urls.txt only)."""

    collection_api_template = "https://www.patreon.com/api/collection/{collection_id}"
    _NEXT_DATA_RE = re.compile(
        r'__NEXT_DATA__"?\s*type="application/json">(.*?)</script>', re.S
    )

    def list_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
    ) -> list[str]:
        html = self._fetch_text(options.download_url)
        collection_id = self._extract_collection_id(options.download_url, html)
        metadata = self._extract_metadata_from_ldjson(html)
        metadata = metadata or self._extract_metadata_from_next_data(html)
        fallback = self._extract_metadata_from_title(html)
        if fallback:
            metadata = {**(metadata or {}), **fallback}
        api_root = self.collection_api_template.format(collection_id=collection_id)

        post_ids = self._collect_post_ids(api_root)
        urls = [self._post_url_from_id(post_id) for post_id in post_ids]

        updated_options = self._update_options_from_metadata(options, metadata)
        options = self._sync_options(options, updated_options)

        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        story_dir = base_root / options.effective_slug()
        self._write_download_list(story_dir, urls)

        return urls

    def fetch_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
        force_fetch: bool = False,
        progress_callback=None,
    ) -> list[Path]:
        """Download posts (sequential filenames)."""

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
        return http_get(url, delay=False).content

    def _extract_collection_id(self, url: str, html: str) -> str:
        parsed = urlparse(url)
        if parsed.path.startswith("/collection/"):
            parts = parsed.path.rstrip("/").split("/")
            if len(parts) >= 3 and parts[2].isdigit():
                return parts[2]

        match = re.search(r"/api/collection/(\d+)", html)
        if match:
            return match.group(1)

        raise ValueError("Could not determine collection id for Patreon URL")

    def _collect_post_ids(self, api_url: str) -> list[str]:
        post_ids: list[str] = []
        next_url: str | None = api_url
        while next_url:
            data = self._fetch_json(next_url)
            attributes = data.get("data", {}).get("attributes", {})
            ids = attributes.get("post_ids") or []
            post_ids.extend([str(post_id) for post_id in ids if post_id is not None])
            links = data.get("links") or {}
            next_url = links.get("next")
        return post_ids

    def _fetch_json(self, url: str) -> dict[str, Any]:
        response = http_get(url, delay=False)
        return response.json()

    def _post_url_from_id(self, post_id: str) -> str:
        return f"https://www.patreon.com/posts/{post_id}"

    def _extract_metadata_from_ldjson(self, html: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        for script in scripts:
            text = script.string
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type", "").lower() == "collection":
                return data
        return None

    def _update_options_from_metadata(
        self, options: StoryScraperOptions, metadata: dict[str, Any] | None
    ) -> StoryScraperOptions:
        if not metadata:
            return options

        headline = metadata.get("name") or metadata.get("headline")
        author = None
        author_data = metadata.get("author")
        if isinstance(author_data, dict):
            author = author_data.get("name")
        elif isinstance(author_data, str):
            author = author_data

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

    def _extract_metadata_from_next_data(self, html: str) -> dict[str, Any] | None:
        match = self._NEXT_DATA_RE.search(html)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

        page_props = data.get("props", {}).get("pageProps", {})
        page_bootstrap = (
            page_props.get("bootstrapEnvelope", {}).get("pageBootstrap", {}) or {}
        )
        collection = page_bootstrap.get("collection", {}) or {}
        attributes = collection.get("attributes") or {}
        if not attributes and isinstance(collection, dict):
            collection_data = collection.get("data")
            if isinstance(collection_data, dict):
                attributes = collection_data.get("attributes") or {}

        post = page_bootstrap.get("post", {}) or {}
        post_included = post.get("included", []) if isinstance(post, dict) else []

        author = None
        campaign = page_bootstrap.get("campaign", {}) or {}
        campaign_data = campaign.get("data", {})
        if isinstance(campaign_data, dict):
            campaign_attrs = campaign_data.get("attributes", {}) or {}
            author = campaign_attrs.get("name") or campaign_attrs.get("full_name")

        creator = page_bootstrap.get("creator", {}) or {}
        creator_data = creator.get("data", {})
        if author is None and isinstance(creator_data, dict):
            creator_attrs = creator_data.get("attributes", {}) or {}
            author = creator_attrs.get("full_name") or creator_attrs.get("name")

        result: dict[str, Any] = {}
        title = attributes.get("title")
        if isinstance(title, str) and title.strip():
            result["name"] = title.strip()

        included_collection = self._first_included_attribute(
            post_included, {"collection"}, ("title", "name")
        )
        if included_collection and not result.get("name"):
            result["name"] = included_collection

        author = author or self._first_included_attribute(
            post_included, {"campaign"}, ("name", "full_name")
        )
        author = author or self._first_included_attribute(
            post_included, {"user"}, ("name", "full_name")
        )
        if author:
            result["author"] = author
        return result or None

    def _first_included_attribute(
        self,
        included: list[Any],
        allowed_types: set[str],
        keys: tuple[str, ...],
    ) -> str | None:
        for item in included:
            if not isinstance(item, dict):
                continue
            if item.get("type") not in allowed_types:
                continue
            attributes = item.get("attributes")
            if not isinstance(attributes, dict):
                continue
            for key in keys:
                value = attributes.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _extract_metadata_from_title(self, html: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            text = soup.title.string.strip()
            parts = [part.strip() for part in text.split("|") if part.strip()]
            name = parts[0] if parts else None
            author = None
            for part in parts:
                if part.lower().startswith("collection from"):
                    author = part.replace("Collection from", "").strip()
            result: dict[str, Any] = {}
            if name:
                result["name"] = name
            if author:
                result["author"] = author
            return result or None
        return None
