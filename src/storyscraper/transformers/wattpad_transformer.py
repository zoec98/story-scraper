"""Wattpad-specific transformer that trims reader chrome."""

from __future__ import annotations

from bs4 import BeautifulSoup

from .auto import Transformer as AutoTransformer


class Transformer(AutoTransformer):
    """Strip Wattpad reader scaffolding before converting to Markdown."""

    _PANEL_SELECTOR = "div.panel-reading"

    def _convert_html_to_markdown(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        header = soup.select_one(".part-header h1")
        container = soup.select_one("#parts-container-new") or soup
        panels = container.select(self._PANEL_SELECTOR)
        if panels:
            fragments: list[str] = []
            for panel in panels:
                for placeholder in panel.select(".trinityAudioPlaceholder"):
                    placeholder.decompose()
                fragments.append(str(panel))
            markdown = super()._convert_html_to_markdown("\n".join(fragments))
        else:
            markdown = super()._convert_html_to_markdown(html)

        if header:
            heading_text = header.get_text(strip=True)
            if heading_text:
                return f"# {heading_text}\n\n{markdown.lstrip()}"

        return markdown
