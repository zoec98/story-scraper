"""Determine site-specific defaults for fetch/transform/packaging agents.

The classifier keeps a registry of known sites. Each registry entry defines:
1. A regex that matches eligible URLs.
2. Friendly site metadata (display name, optional documentation).
3. Optional fetch/transform/packaging agent overrides.

When a download URL is provided, the classifier scans the registry in order
and returns the first matching entry. Missing agent names default to "auto".
This lets the CLI collect generic StoryScraperOptions while still honoring
site-specific strategies when users or automation do not override them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Pattern


@dataclass(frozen=True, slots=True)
class SiteRule:
    """Configuration for a single site match."""

    pattern: Pattern[str]
    name: str
    full_name: str
    fetch_agent: str | None = None
    transform_agent: str | None = None
    packaging_agent: str | None = None
    documentation: str | None = None


@dataclass(frozen=True, slots=True)
class SiteMatch:
    """Result of classifying a URL."""

    name: str
    full_name: str
    fetch_agent: str | None
    transform_agent: str | None
    packaging_agent: str | None
    documentation: str | None = None


def classify_url(url: str) -> SiteMatch | None:
    """Return metadata for the first matching rule, if any."""

    for rule in _iter_rules():
        if rule.pattern.search(url):
            return SiteMatch(
                name=rule.name,
                full_name=rule.full_name,
                fetch_agent=rule.fetch_agent,
                transform_agent=rule.transform_agent,
                packaging_agent=rule.packaging_agent,
                documentation=rule.documentation,
            )
    return None


def _iter_rules() -> Iterable[SiteRule]:
    """Yield all site rules in priority order."""

    return (
        SiteRule(
            pattern=re.compile(r"https?://(?:www\.)?literotica\.com/.*", re.IGNORECASE),
            name="literotica",
            full_name="Literotica",
            fetch_agent="literotica_fetcher",
            transform_agent="literotica_transformer",
            documentation="Stories hosted on literotica.com.",
        ),
        SiteRule(
            pattern=re.compile(
                r"https?://(?:www\.)?bdsmlibrary\.com/stories/.*", re.IGNORECASE
            ),
            name="bdsmlibrary",
            full_name="BDSM Library",
            fetch_agent="bdsmlibrary_fetcher",
            transform_agent="bdsmlibrary_transformer",
            documentation="Stories hosted on bdsmlibrary.com.",
        ),
        SiteRule(
            pattern=re.compile(
                r"https?://(?:www\.)?inkitt\.com/stories/.*", re.IGNORECASE
            ),
            name="inkitt",
            full_name="Inkitt",
            fetch_agent="inkitt_fetcher",
            transform_agent="inkitt_transformer",
            documentation="Stories hosted on inkitt.com.",
        ),
        SiteRule(
            pattern=re.compile(
                r"https?://(?:www\.)?patreon\.com/collection/\d+", re.IGNORECASE
            ),
            name="patreon",
            full_name="Patreon",
            fetch_agent="patreon_fetcher",
            transform_agent="patreon_transformer",
            documentation="Public Patreon collections (requires cookies for gated posts).",
        ),
        SiteRule(
            pattern=re.compile(r"https?://(?:www\.)?mcstories\.com/.*", re.IGNORECASE),
            name="mcstories",
            full_name="The Erotic Mind-Control Story Archive",
            fetch_agent="mcstories_fetcher",
            transform_agent="mcstories_transformer",
            documentation="Stories hosted on mcstories.com.",
        ),
        SiteRule(
            pattern=re.compile(r"https?://(?:www\.)?wattpad\.com/.*", re.IGNORECASE),
            name="wattpad",
            full_name="Wattpad",
            fetch_agent="wattpad_fetcher",
            transform_agent="wattpad_transformer",
            documentation="Stories hosted on wattpad.com.",
        ),
        SiteRule(
            pattern=re.compile(
                r"https?://(?:www\.)?archiveofourown\.org/.*", re.IGNORECASE
            ),
            name="ao3",
            full_name="Archive of Our Own",
            fetch_agent="ao3_fetcher",
            transform_agent="ao3_transformer",
            documentation="Stories hosted on archiveofourown.org.",
        ),
        SiteRule(
            pattern=re.compile(r"https?://(?:www\.)?fanfiction\.net/.*", re.IGNORECASE),
            name="fanfiction",
            full_name="FanFiction.Net",
            fetch_agent="fanfiction_fetcher",
            transform_agent="fanfiction_transformer",
            documentation="Stories hosted on fanfiction.net.",
        ),
    )
