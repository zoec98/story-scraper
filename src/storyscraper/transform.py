"""Transform pipeline orchestration."""

from __future__ import annotations

from pathlib import Path

from .options import StoryScraperOptions
from .transformers import ProgressCallback, load_transformer


def run_transform_phase(
    options: StoryScraperOptions,
    *,
    stories_root: Path | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[Path]:
    """Run the transform phase for the configured transformer."""

    transformer = load_transformer(options.transform_agent)
    root = Path(stories_root) if stories_root is not None else Path("stories")
    return transformer.transform_phase(
        options,
        stories_root=root,
        progress_callback=progress_callback,
    )
