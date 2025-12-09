"""AO3 fetcher that downloads EPUBs and extracts chapters."""

from __future__ import annotations

import posixpath
import warnings
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin
from zipfile import ZipFile

from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET

from ..options import StoryScraperOptions, slugify
from .auto import Fetcher as AutoFetcher


class Fetcher(AutoFetcher):
    """Fetch Archive of Our Own works via their EPUB download."""

    download_selector = "li.download a[href*='epub']"
    title_selector = "h2.title"
    author_selector = "a[rel='author']"

    def _select_urls(self, base_url: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        download_link = soup.select_one(self.download_selector)
        if download_link is None:
            raise ValueError("Unable to locate EPUB download link on AO3 page.")

        href = download_link.get("href")
        if not isinstance(href, str) or not href.strip():
            raise ValueError("Invalid EPUB link on AO3 page.")

        return [urljoin(base_url, href)]

    def postprocess_listing(
        self,
        options: StoryScraperOptions,
        html: str,
        urls: list[str],
    ) -> StoryScraperOptions:
        soup = BeautifulSoup(html, "html.parser")
        updated = options

        title_tag = soup.select_one(self.title_selector)
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

        author_tag = soup.select_one(self.author_selector)
        if author_tag:
            author_text = author_tag.get_text(strip=True)
            if author_text:
                updated = replace(
                    updated,
                    author=options.author or author_text,
                    chosen_author=author_text,
                )

        return updated

    def fetch_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
        force_fetch: bool = False,
        progress_callback=None,
    ):
        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        slug_value = options.effective_slug()
        story_dir = base_root / slug_value
        story_dir.mkdir(parents=True, exist_ok=True)
        urls_file = story_dir / self.download_list_filename
        html_dir = story_dir / "html"
        html_dir.mkdir(parents=True, exist_ok=True)
        log_file = story_dir / "fetch.log"

        urls = self._load_download_list(urls_file)
        if len(urls) != 1:
            warnings.warn(
                "AO3 fetcher expected exactly one EPUB URL; falling back to auto behavior."
            )
            return super().fetch_phase(
                options,
                stories_root=stories_root,
                force_fetch=force_fetch,
                progress_callback=progress_callback,
            )

        epub_url = urls[0]
        destination_prefix = f"{slug_value}-"
        epub_path = story_dir / f"{slug_value}.epub"

        if epub_path.exists() and not force_fetch:
            epub_bytes = epub_path.read_bytes()
        else:
            try:
                epub_bytes = self._fetch_bytes(epub_url)
            except Exception as exc:  # pragma: no cover - logged for later review
                self._log_failure(log_file, epub_url, exc)
                return []
            epub_path.write_bytes(epub_bytes)

        extracted_files = self._extract_epub(
            epub_bytes,
            html_dir,
            destination_prefix,
            progress_callback,
        )
        warnings.warn(
            f"AO3: extracted {len(extracted_files)} chapter(s) from {epub_path.name}.",
            stacklevel=2,
        )
        return extracted_files

    def _extract_epub(
        self,
        data: bytes,
        html_dir: Path,
        prefix: str,
        progress_callback,
    ) -> list[Path]:
        with ZipFile(BytesIO(data)) as archive:
            try:
                spine_items = self._resolve_spine_documents(archive)
            except Exception as exc:  # pragma: no cover
                raise ValueError(f"Invalid EPUB structure: {exc}") from exc

            generated: list[Path] = []
            total = len(spine_items)
            for index, item_path in enumerate(spine_items, start=1):
                try:
                    content = archive.read(item_path)
                except KeyError:
                    continue
                destination = html_dir / f"{prefix}{index:03d}.html"
                destination.write_bytes(content)
                generated.append(destination)
                if progress_callback:
                    progress_callback(index, total, destination, False)

        return generated

    def _resolve_spine_documents(self, archive: ZipFile) -> list[str]:
        container_xml = archive.read("META-INF/container.xml")
        container_tree = ET.fromstring(container_xml)
        rootfile = container_tree.find(".//{*}rootfile")
        if rootfile is None:
            raise ValueError("Missing rootfile in EPUB container.")
        opf_path = rootfile.attrib.get("full-path")
        if not opf_path:
            raise ValueError("rootfile missing full-path attribute.")

        opf_xml = archive.read(opf_path)
        opf_tree = ET.fromstring(opf_xml)
        manifest: dict[str, str] = {}
        opf_dir = posixpath.dirname(opf_path)

        for item in opf_tree.findall(".//{*}manifest/{*}item"):
            item_id = item.attrib.get("id")
            href = item.attrib.get("href")
            if not item_id or not href:
                continue
            manifest[item_id] = posixpath.normpath(
                posixpath.join(opf_dir, href)
            ).lstrip("./")

        ordered: list[str] = []
        for ref in opf_tree.findall(".//{*}spine/{*}itemref"):
            ref_id = ref.attrib.get("idref")
            if not ref_id:
                continue
            href = manifest.get(ref_id)
            if href:
                ordered.append(href)

        return ordered
