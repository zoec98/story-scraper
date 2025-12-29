"""DeviantArt-specific transformer that targets deviation literature blocks."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from .auto import Transformer as AutoTransformer
from ..options import StoryScraperOptions


class Transformer(AutoTransformer):
    """Prefer DeviantArt deviation body/description containers."""

    _CONTENT_SELECTORS = (
        "[data-hook='deviation_body']",
        "[data-hook='deviation_description']",
        "[data-hook='deviation_content']",
    )
    _OG_TITLE_SELECTOR = "meta[property='og:title']"

    def transform_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
        progress_callback=None,
    ) -> list[Path]:  # type: ignore[override]
        generated = super().transform_phase(
            options,
            stories_root=stories_root,
            progress_callback=progress_callback,
        )
        self._write_metadata(options, stories_root=stories_root)
        return generated

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

    def _write_metadata(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
    ) -> None:
        base_root = Path(stories_root) if stories_root is not None else Path("stories")
        story_dir = base_root / options.effective_slug()
        html_dir = story_dir / "html"
        html_files = sorted(html_dir.glob("*.html"))
        if not html_files:
            return

        html_text = html_files[0].read_text(encoding="utf-8")
        title, author, tags, stats, badges, extra = self._extract_metadata(html_text)
        payload: dict[str, object] = {
            "tags": tags,
            "title": title,
            "author": author,
            "last_updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        if stats is not None:
            payload["favorites"] = stats.get("favorites")
            payload["comments"] = stats.get("comments")
            payload["views"] = stats.get("views")
        if badges is not None:
            payload["badges"] = badges
        if extra:
            payload.update(extra)
        destination = story_dir / "metadata.json"
        destination.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def _extract_metadata(
        self, html: str
    ) -> tuple[
        str | None,
        str | None,
        list[str],
        dict[str, int] | None,
        dict[str, int] | None,
        dict[str, object],
    ]:
        soup = BeautifulSoup(html, "html.parser")
        title: str | None = None
        author: str | None = None
        og_tag = soup.select_one(self._OG_TITLE_SELECTOR)
        if og_tag is not None:
            content = og_tag.get("content")
            if isinstance(content, str):
                title, author = self._split_title_author(content.strip())

        tags: list[str] = []
        stats: dict[str, int] | None = None
        badges: dict[str, int] | None = None
        extra: dict[str, object] = {}

        initial_state = self._extract_initial_state(html)
        if initial_state is not None:
            deviation_id = self._extract_current_deviation_id(initial_state)
            deviation = self._extract_deviation(initial_state, deviation_id)
            if deviation is not None:
                state_title = deviation.get("title")
                if isinstance(state_title, str) and state_title.strip():
                    title = state_title.strip()
                author_info = deviation.get("author")
                if isinstance(author_info, dict):
                    state_author = author_info.get("username")
                    if isinstance(state_author, str) and state_author.strip():
                        author = state_author.strip()
                stats = self._extract_stats_from_deviation(deviation)
                extra.update(self._extract_deviation_metadata(deviation))

            extended = self._extract_deviation_extended(initial_state, deviation_id)
            if extended is not None:
                state_tags = self._extract_tags_from_extended(extended)
                if state_tags:
                    tags = state_tags
                badges = self._extract_badges_from_extended(extended)
                extra.update(self._extract_extended_metadata(extended))
            if deviation_id is not None:
                extra["deviation_id"] = deviation_id

        if not tags:
            tags = self._extract_tags(html)

        return title, author, tags, stats, badges, extra

    def _extract_initial_state(self, html: str) -> dict[str, object] | None:
        match = re.search(
            r'window\.__INITIAL_STATE__\s*=\s*JSON\.parse\("(.*?)"\);',
            html,
            re.DOTALL,
        )
        if match is None:
            return None
        raw = match.group(1)
        try:
            decoded = raw.encode("utf-8").decode("unicode_escape")
            parsed = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if isinstance(parsed, dict):
            return parsed
        return None

    def _extract_current_deviation_id(self, state: dict[str, object]) -> str | None:
        duperbrowse = state.get("@@DUPERBROWSE")
        if isinstance(duperbrowse, dict):
            root_stream = duperbrowse.get("rootStream")
            if isinstance(root_stream, dict):
                current_open = root_stream.get("currentOpenItem")
                if isinstance(current_open, (int, str)):
                    return str(current_open)
        return None

    def _extract_deviation(
        self, state: dict[str, object], deviation_id: str | None
    ) -> dict[str, object] | None:
        entities = state.get("@@entities")
        if not isinstance(entities, dict):
            return None
        deviations = entities.get("deviation")
        if isinstance(deviations, dict):
            if deviation_id and deviation_id in deviations:
                deviation = deviations.get(deviation_id)
                if isinstance(deviation, dict):
                    return deviation
            for deviation in deviations.values():
                if isinstance(deviation, dict):
                    return deviation
        return None

    def _extract_deviation_extended(
        self, state: dict[str, object], deviation_id: str | None
    ) -> dict[str, object] | None:
        entities = state.get("@@entities")
        if not isinstance(entities, dict):
            return None
        extended = entities.get("deviationExtended")
        if isinstance(extended, dict):
            if deviation_id and deviation_id in extended:
                deviation = extended.get(deviation_id)
                if isinstance(deviation, dict):
                    return deviation
            for deviation in extended.values():
                if isinstance(deviation, dict):
                    return deviation
        return None

    def _extract_stats_from_deviation(
        self, deviation: dict[str, object]
    ) -> dict[str, int] | None:
        stats = deviation.get("stats")
        if not isinstance(stats, dict):
            return None
        favorites_value = stats.get("favourites")
        comments_value = stats.get("comments")
        views_value = stats.get("views")
        if not isinstance(favorites_value, int):
            return None
        if not isinstance(comments_value, int):
            return None
        if not isinstance(views_value, int):
            return None
        return {
            "favorites": favorites_value,
            "comments": comments_value,
            "views": views_value,
        }

    def _extract_deviation_metadata(
        self, deviation: dict[str, object]
    ) -> dict[str, object]:
        fields = {
            "published_time": deviation.get("publishedTime"),
            "mature_level": deviation.get("matureLevel"),
            "is_mature": deviation.get("isMature"),
            "is_nsfg": deviation.get("isNsfg"),
            "is_commentable": deviation.get("isCommentable"),
            "is_deleted": deviation.get("isDeleted"),
            "is_published": deviation.get("isPublished"),
            "is_downloadable": deviation.get("isDownloadable"),
            "is_favouritable": deviation.get("isFavouritable"),
            "is_ai_generated": deviation.get("isAiGenerated"),
            "is_ai_use_disallowed": deviation.get("isAiUseDisallowed"),
            "license": deviation.get("license"),
            "short_url": deviation.get("shortUrl"),
            "url": deviation.get("url"),
            "text_content": deviation.get("textContent"),
            "media": deviation.get("media"),
            "is_adoptable": deviation.get("isAdoptable"),
            "is_shareable": deviation.get("isShareable"),
            "is_text_editable": deviation.get("isTextEditable"),
            "is_background_editable": deviation.get("isBackgroundEditable"),
            "is_upscaled": deviation.get("isUpscaled"),
            "is_video": deviation.get("isVideo"),
            "is_journal": deviation.get("isJournal"),
            "is_purchasable": deviation.get("isPurchasable"),
            "is_default_image": deviation.get("isDefaultImage"),
            "is_antisocial": deviation.get("isAntisocial"),
            "is_blocked": deviation.get("isBlocked"),
            "can_update_ai_claim": deviation.get("canUpdateAiClaim"),
            "has_private_comments": deviation.get("hasPrivateComments"),
            "is_daily_deviation": deviation.get("isDailyDeviation"),
            "is_dreamsofart": deviation.get("isDreamsofart"),
        }
        return {key: value for key, value in fields.items() if value is not None}

    def _extract_extended_metadata(
        self, extended: dict[str, object]
    ) -> dict[str, object]:
        fields = {
            "description_text": extended.get("descriptionText"),
            "deviation_uuid": extended.get("deviationUuid"),
            "group_list_url": extended.get("groupListUrl"),
            "parent_deviation_entity_id": extended.get("parentDeviationEntityId"),
            "can_user_add_to_group": extended.get("canUserAddToGroup"),
            "extended_stats": extended.get("stats"),
        }
        return {key: value for key, value in fields.items() if value is not None}

    def _extract_tags_from_extended(self, extended: dict[str, object]) -> list[str]:
        tags: list[str] = []
        raw_tags = extended.get("tags")
        if isinstance(raw_tags, list):
            for item in raw_tags:
                if isinstance(item, dict):
                    name = item.get("name")
                    if isinstance(name, str):
                        tag = name.strip()
                        if tag and tag not in tags:
                            tags.append(tag)
        return tags

    def _extract_badges_from_extended(
        self, extended: dict[str, object]
    ) -> dict[str, int] | None:
        raw_badges = extended.get("awardedBadges")
        if not isinstance(raw_badges, list):
            return None
        badges: dict[str, int] = {}
        for badge in raw_badges:
            if not isinstance(badge, dict):
                continue
            name = badge.get("title") or badge.get("baseTitle")
            count = badge.get("stackCount")
            if not isinstance(name, str) or not isinstance(count, int):
                continue
            badge_name = name.strip()
            if not badge_name:
                continue
            badges[badge_name] = count
        if not badges:
            return None
        return badges

    def _extract_tags(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        tags: list[str] = []
        for anchor in soup.select("a[data-tagname]"):
            value = anchor.get("data-tagname")
            if not isinstance(value, str):
                continue
            value = value.strip()
            if value and value not in tags:
                tags.append(value)
        return tags
