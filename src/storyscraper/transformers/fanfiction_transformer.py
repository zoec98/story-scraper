"""FanFiction.Net transformer that focuses on the story text block."""

from __future__ import annotations

from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_markdown

from .auto import Transformer as AutoTransformer


class Transformer(AutoTransformer):
    """Convert FanFiction.Net story text into Markdown."""

    _CONTENT_SELECTOR = "#storytext, .storytext"

    def _convert_html_to_markdown(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        content = soup.select_one(self._CONTENT_SELECTOR)
        if content is None:
            return super()._convert_html_to_markdown(html)

        heading_tag = content.find("strong")
        heading_text = None
        if heading_tag:
            heading_text = heading_tag.get_text(strip=True)
            heading_tag.decompose()

        markdown = html_to_markdown(str(content))
        if heading_text:
            return f"# {heading_text}\n\n{markdown.lstrip()}"

        return markdown
