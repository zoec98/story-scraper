"""Fetch pipeline orchestration."""

from __future__ import annotations

import os
import shlex
import stat
from pathlib import Path

from .fetchers import load_fetcher, ProgressCallback
from .options import StoryScraperOptions, load_urls_from_file


def run_fetch_list_phase(
    options: StoryScraperOptions,
    *,
    stories_root: Path | None = None,
) -> list[str]:
    """Run the list phase for the configured fetcher."""

    root = Path(stories_root) if stories_root is not None else Path("stories")
    story_dir = root / options.effective_slug()
    if options.from_file:
        urls = load_urls_from_file(Path(options.from_file))
        _write_download_list(story_dir, urls)
        _write_doit_file(story_dir, options)
        return urls

    fetcher = load_fetcher(options.fetch_agent)
    urls = fetcher.list_phase(options, stories_root=root)
    story_dir = root / options.effective_slug()
    _write_doit_file(story_dir, options)
    return urls


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


def _write_doit_file(story_dir: Path, options: StoryScraperOptions) -> None:
    story_dir.mkdir(parents=True, exist_ok=True)
    destination = story_dir / "doit"

    if options.invocation_command:
        command = options.invocation_command
    else:
        command = shlex.join(["storyscraper", options.download_url])

    try:
        import pwd  # Available on Unix-like systems

        home_dir = pwd.getpwuid(os.getuid()).pw_dir
        if command.startswith(home_dir):
            command = "~" + command[len(home_dir) :]
    except Exception:  # pragma: no cover - non-Unix platforms or lookup failures
        pass

    content = f"#! /usr/bin/env bash\n{command}\n"
    destination.write_text(content, encoding="utf-8")
    mode = destination.stat().st_mode
    destination.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_download_list(story_dir: Path, urls: list[str]) -> None:
    story_dir.mkdir(parents=True, exist_ok=True)
    destination = story_dir / "download_urls.txt"
    content = "\n".join(urls) + ("\n" if urls else "")
    destination.write_text(content, encoding="utf-8")
