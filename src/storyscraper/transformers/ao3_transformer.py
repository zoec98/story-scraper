"""AO3-specific transformer that extracts user content blocks."""

from __future__ import annotations

from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_markdown

from .auto import Transformer as AutoTransformer


class Transformer(AutoTransformer):
    """Select AO3's userstuff content and headings."""

    _CONTENT_SELECTOR = ".userstuff"
    _HEADING_SELECTOR = ".heading"

    def _convert_html_to_markdown(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        heading_tag = soup.select_one(self._HEADING_SELECTOR)
        body = soup.body or soup

        markdown = html_to_markdown(str(body))

        if heading_tag:
            heading_text = heading_tag.get_text(strip=True)
            if heading_text:
                return f"# {heading_text}\n\n{markdown.lstrip()}"

        return markdown
