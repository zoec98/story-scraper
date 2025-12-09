"""Fetch pipeline orchestration."""

from __future__ import annotations

from pathlib import Path

from .fetchers import load_fetcher, ProgressCallback
from .options import StoryScraperOptions


def run_fetch_list_phase(
    options: StoryScraperOptions,
    *,
    stories_root: Path | None = None,
) -> list[str]:
    """Run the list phase for the configured fetcher."""

    fetcher = load_fetcher(options.fetch_agent)
    root = Path(stories_root) if stories_root is not None else Path("stories")
    return fetcher.list_phase(options, stories_root=root)


def run_fetch_phase(
    options: StoryScraperOptions,
    *,
    stories_root: Path | None = None,
    force_fetch: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> list[Path]:
    """Run the fetch phase for the configured fetcher."""

    fetcher = load_fetcher(options.fetch_agent)
    root = Path(stories_root) if stories_root is not None else Path("stories")
    return fetcher.fetch_phase(
        options,
        stories_root=root,
        force_fetch=force_fetch,
        progress_callback=progress_callback,
    )
