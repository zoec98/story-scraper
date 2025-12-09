"""BDSMLibrary-specific transformer."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from .auto import Transformer as AutoTransformer


class Transformer(AutoTransformer):
    """Convert BDSMLibrary chapters by extracting the h3 title and <pre> body."""

    ENCODING = "cp1252"

    def transform_phase(
        self,
        options,
        *,
        stories_root: Path | None = None,
        progress_callback=None,
    ):
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

        generated = []
        html_files = sorted(html_dir.glob("*.html"))
        total = len(html_files)
        for index, html_path in enumerate(html_files, start=1):
            destination = markdown_dir / f"{options.effective_slug()}-{index:03d}.md"
            try:
                raw_bytes = html_path.read_bytes()
                html_text = raw_bytes.decode(self.ENCODING, errors="replace")
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
        pre = soup.find("pre")
        if pre is None:
            return super()._convert_html_to_markdown(html)

        heading = self._chapter_heading(pre)
        body = self._normalize_text(pre.get_text())

        parts = []
        if heading:
            parts.append(f"# {heading}")
        if body:
            parts.append(body)
        return "\n\n".join(parts)

    def _chapter_heading(self, pre) -> str | None:
        heading_tag = pre.find_previous("h3")
        if heading_tag and heading_tag.get_text(strip=True):
            return heading_tag.get_text(strip=True)
        return None

    def _normalize_text(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        paragraphs: list[str] = []
        current: list[str] = []

        def flush() -> None:
            if current:
                paragraphs.append(" ".join(current).strip())
                current.clear()

        for line in lines:
            stripped = line.strip()
            leading_spaces = len(line) - len(line.lstrip(" "))
            if not stripped:
                flush()
                continue
            if leading_spaces >= 2 and current:
                flush()
            current.append(stripped)

        flush()
        return "\n\n".join(paragraphs)
