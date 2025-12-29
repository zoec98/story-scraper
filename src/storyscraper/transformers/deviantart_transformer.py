"""DeviantArt-specific transformer that targets deviation literature blocks."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from .auto import Transformer as AutoTransformer


class Transformer(AutoTransformer):
    """Prefer DeviantArt deviation body/description containers."""

    _CONTENT_SELECTORS = (
        "[data-hook='deviation_body']",
        "[data-hook='deviation_description']",
        "[data-hook='deviation_content']",
    )
    _OG_TITLE_SELECTOR = "meta[property='og:title']"

    def extract_content_root(self, soup: BeautifulSoup) -> Tag:
        candidates: list[Tag] = []
        for selector in self._CONTENT_SELECTORS:
            candidates.extend(soup.select(selector))

        preferred = self._pick_largest_text(candidates)
        if preferred is not None:
            return preferred

        return super().extract_content_root(soup)

    def _convert_html_to_markdown(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        title = self._extract_title_from_og(soup)
        literature_section = self._extract_literature_div(soup)
        if literature_section is not None:
            body_markdown = super()._convert_html_to_markdown(str(literature_section))
            if title:
                return f"# {title}\n\n{body_markdown.lstrip()}"
            return body_markdown
        return super()._convert_html_to_markdown(html)

    def _extract_title_from_og(self, soup: BeautifulSoup) -> str | None:
        tag = soup.select_one(self._OG_TITLE_SELECTOR)
        if tag is None:
            return None
        content = tag.get("content")
        if not isinstance(content, str):
            return None
        title, _ = self._split_title_author(content.strip())
        return title

    def _split_title_author(self, title: str) -> tuple[str | None, str | None]:
        suffix = " on DeviantArt"
        if suffix not in title:
            return title, None
        prefix = title.split(suffix, 1)[0].strip()
        if " by " not in prefix:
            return prefix or None, None
        story_title, author = prefix.rsplit(" by ", 1)
        return story_title.strip() or None, author.strip() or None

    def _extract_literature_div(self, soup: BeautifulSoup) -> Tag | None:
        headings = soup.find_all("h2")
        for heading in headings:
            if heading.get_text(strip=True) != "Literature Text":
                continue
            section = heading.find_parent("section")
            if section is None:
                continue
            content_div = section.find("div", recursive=False)
            if content_div is not None:
                return content_div
        return None
