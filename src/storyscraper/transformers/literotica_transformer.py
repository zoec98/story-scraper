"""Literotica-specific transformer that extracts pageText payloads."""

from __future__ import annotations

import codecs
import json
import re
from typing import Any

from bs4 import BeautifulSoup

from .auto import Transformer as AutoTransformer


class Transformer(AutoTransformer):
    """Convert Literotica stories by decoding their inline pageText strings."""

    _PAGETEXT_RE = re.compile(r'pageText:"((?:\\.|[^"\\])*)"')

    def _convert_html_to_markdown(self, html: str) -> str:
        segments = self._extract_page_texts(html)
        if not segments:
            return super()._convert_html_to_markdown(html)

        body = "\n\n".join(segments)
        heading = self._extract_heading(html)
        if heading:
            return f"# {heading}\n\n{body}\n"
        return body

    def _extract_heading(self, html: str) -> str | None:
        metadata = self._extract_article_metadata(html)
        if not metadata:
            return None
        headline = metadata.get("headline")
        if isinstance(headline, str):
            headline = headline.strip()
        return headline or None

    def _extract_page_texts(self, html: str) -> list[str]:
        matches = self._PAGETEXT_RE.findall(html)
        texts: list[str] = []
        for raw in matches:
            try:
                decoded = codecs.decode(raw, "unicode_escape")
            except Exception:
                continue
            decoded = decoded.replace("\r\n", "\n").replace("\r", "\n").strip()
            decoded = self._sanitize_markdown(decoded)
            if decoded:
                texts.append(decoded)
        return texts

    def _sanitize_markdown(self, text: str) -> str:
        """Replace fence-like tilde lines with a Markdown HR to avoid code blocks."""

        return re.sub(r"^~{3,}\s*$", "***", text, flags=re.MULTILINE)

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
