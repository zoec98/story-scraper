"""EroticStories.com transformer that trims chrome and stitches story text."""

from __future__ import annotations

from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import markdownify as html_to_markdown

from .auto import Transformer as AutoTransformer


class Transformer(AutoTransformer):
    """Extract the story text from stitched EroticStories HTML."""

    _BLOCK_TAGS = ("p", "table", "div")
    _HEADER_MARKERS = (
        "click here to read the first",
        "don't forget to vote",
        "has been interviewed",
        "you can change the width",
    )
    _SEGMENT_END_MARKERS = (
        "click here to read the rest of this story",
        "do you like this story",
        "request from webmaster",
    )

    def _convert_html_to_markdown(self, html: str) -> str:
        soup = BeautifulSoup(html, "html5lib")
        content = soup.select_one("div#content")
        if content is None:
            return super()._convert_html_to_markdown(html)

        segments = [
            segment
            for segment in content.find_all("div", recursive=False)
            if segment.find("a", attrs={"name": "textstart"})
        ]
        if not segments:
            segments = [content]

        cleaned_segments: list[Tag] = []
        for index, segment in enumerate(segments):
            is_first = index == 0
            cleaned = self._extract_segment(segment, is_first=is_first)
            if cleaned is not None:
                cleaned_segments.append(cleaned)

        if not cleaned_segments:
            return super()._convert_html_to_markdown(html)

        combined = BeautifulSoup("", "html.parser").new_tag("div")
        for cleaned in cleaned_segments:
            combined.append(cleaned)

        return html_to_markdown(str(combined))

    def _extract_segment(self, segment: Tag, *, is_first: bool) -> Tag | None:
        blocks = self._segment_blocks(segment)
        if not blocks:
            return None

        header_end = self._header_end_index(blocks)
        if header_end < 0:
            header_end = -1
        start = header_end + 1

        end = self._segment_end_index(blocks, is_first=is_first)
        if end < 0:
            end = len(blocks)

        if start >= end:
            return None

        cleaned = BeautifulSoup("", "html.parser").new_tag("div")
        for block in blocks[start:end]:
            cleaned.append(block)
        return cleaned

    def _segment_blocks(self, segment: Tag) -> list[Tag]:
        blocks: list[Tag] = []
        for child in segment.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if not text:
                    continue
                paragraph = BeautifulSoup("", "html.parser").new_tag("p")
                paragraph.string = text
                blocks.append(paragraph)
                continue
            if not isinstance(child, Tag):
                continue
            if child.name in self._BLOCK_TAGS:
                if child.get_text(" ", strip=True):
                    blocks.append(child)
                continue
            descendant_blocks = [
                block
                for block in child.find_all(self._BLOCK_TAGS, recursive=True)
                if block.get_text(" ", strip=True)
            ]
            blocks.extend(descendant_blocks)
        return blocks

    def _header_end_index(self, blocks: list[Tag]) -> int:
        last_marker = -1
        for index, block in enumerate(blocks[:12]):
            text = block.get_text(" ", strip=True).lower()
            if any(marker in text for marker in self._HEADER_MARKERS):
                last_marker = index
        return last_marker

    def _segment_end_index(self, blocks: list[Tag], *, is_first: bool) -> int:
        for index, block in enumerate(blocks):
            text = block.get_text(" ", strip=True).lower()
            if "click here to read the rest of this story" in text:
                return index if is_first else -1
            if "do you like this story" in text:
                return index
            if "request from webmaster" in text:
                return index
        return -1
