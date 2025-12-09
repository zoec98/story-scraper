"""MCStories-specific transformer with custom HTML tweaks."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from .auto import Transformer as AutoTransformer


class Transformer(AutoTransformer):
    """Adjust MCStories HTML before running the default transformer."""

    def extract_content_root(self, soup: BeautifulSoup) -> Tag:
        self._normalize_document(soup)
        return super().extract_content_root(soup)

    def _normalize_document(self, soup: BeautifulSoup) -> None:
        self._promote_titles(soup)
        self._remove_trailers(soup)
        self._convert_milestones(soup)
        self._italicize_foreword(soup)

    def _promote_titles(self, soup: BeautifulSoup) -> None:
        for title in soup.select("h3.title"):
            title.name = "h1"

    def _remove_trailers(self, soup: BeautifulSoup) -> None:
        for trailer in soup.select("h3.trailer"):
            trailer.decompose()

    def _convert_milestones(self, soup: BeautifulSoup) -> None:
        for milestone in soup.select("span.milestone"):
            milestone.name = "hr"
            milestone.attrs.clear()
            milestone.string = ""

    def _italicize_foreword(self, soup: BeautifulSoup) -> None:
        for foreword in soup.select("section.foreword"):
            foreword.name = "em"
