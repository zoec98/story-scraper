"""Default HTML-to-Markdown transformer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as html_to_markdown

from . import ProgressCallback
from ..options import StoryScraperOptions


class Transformer:
    """Auto transformer that extracts story content and converts it to Markdown."""

    MARKDOWN_EXTENSION = ".md"
    _CHROME_SELECTORS = [
        "nav",
        "header",
        "footer",
        '[role="navigation"]',
        '[role="banner"]',
        '[role="contentinfo"]',
    ]
    _ARTICLE_KEYWORDS = (
        "article",
        "blogposting",
        "newsarticle",
        "creativework",
    )

    def transform_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> list[Path]:
        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        story_dir = base_root / options.effective_slug()
        html_dir = story_dir / "html"
        markdown_dir = story_dir / "markdown"
        log_file = story_dir / "transform.log"

        if not html_dir.exists():
            raise FileNotFoundError(
                f"Missing HTML directory at {html_dir}. Run the fetch phase first."
            )

        markdown_dir.mkdir(parents=True, exist_ok=True)

        generated: list[Path] = []
        html_files = sorted(html_dir.glob("*.html"))
        total = len(html_files)
        for index, html_path in enumerate(html_files, start=1):
            destination = markdown_dir / f"{options.effective_slug()}-{index:03d}.md"
            try:
                html_text = html_path.read_text(encoding="utf-8")
                markdown = self._convert_html_to_markdown(html_text)
                destination.write_text(markdown, encoding="utf-8")
                generated.append(destination)
                if progress_callback:
                    progress_callback(index, total, destination, False)
            except Exception as exc:  # pragma: no cover - logged for later review
                self._log_failure(log_file, html_path, exc)

        return generated

    def _convert_html_to_markdown(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        root = self.extract_content_root(soup)
        return html_to_markdown(str(root))

    def extract_content_root(self, soup: BeautifulSoup) -> Tag:
        """Select the most relevant content subtree based on heuristics."""

        candidate = self._pick_largest_text(soup.find_all("main"))
        if candidate:
            return candidate

        role_main = [
            element
            for element in soup.find_all(attrs={"role": True})
            if self._stringify_itemtype(element.get("role")).lower() == "main"
        ]
        candidate = self._pick_largest_text(role_main)
        if candidate:
            return candidate

        candidate = self._pick_largest_text(soup.find_all("article"))
        if candidate:
            return candidate

        article_like = [
            element
            for element in soup.find_all(attrs={"itemtype": True})
            if self._is_article_like(element.get("itemtype"))
        ]
        candidate = self._pick_largest_text(article_like)
        if candidate:
            return candidate

        structured_candidate = self._structured_layout_candidate(soup)
        if structured_candidate:
            return structured_candidate

        return soup.body or soup

    def _pick_largest_text(self, elements: Iterable[Tag]) -> Tag | None:
        best: Tag | None = None
        best_length = 0
        for element in elements:
            length = self._visible_text_length(element)
            if length > best_length:
                best = element
                best_length = length
        return best

    def _visible_text_length(self, element: Tag) -> int:
        text = element.get_text(separator=" ", strip=True)
        return len(text)

    def _is_article_like(self, itemtype_value: object) -> bool:
        combined = self._stringify_itemtype(itemtype_value)
        if not combined:
            return False

        combined = combined.lower()
        return any(keyword in combined for keyword in self._ARTICLE_KEYWORDS)

    def _structured_layout_candidate(self, soup: BeautifulSoup) -> Tag | None:
        if soup.body is None:
            return None

        body_clone = BeautifulSoup(str(soup.body), "html.parser").body
        if body_clone is None:
            return None

        for selector in self._CHROME_SELECTORS:
            for element in body_clone.select(selector):
                element.decompose()

        best: Tag | None = None
        best_depth = -1
        best_length = 0

        for element in body_clone.find_all(True):
            if element.find(["h1", "h2"]) is None:
                continue
            length = self._visible_text_length(element)
            if length == 0:
                continue
            depth = self._node_depth(element)
            if depth > best_depth or (depth == best_depth and length > best_length):
                best = element
                best_depth = depth
                best_length = length

        return best

    def _node_depth(self, element: Tag) -> int:
        depth = 0
        current = element
        while current.parent is not None:
            depth += 1
            current = current.parent  # type: ignore[assignment]
        return depth

    def _stringify_itemtype(self, value: object) -> str:
        if not value:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return " ".join(str(part) for part in value)
        return str(value)

    def _log_failure(self, log_file: Path, html_path: Path, exc: Exception) -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")
        message = f"{timestamp} ERROR {html_path.name} -> {exc}\n"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(message)
