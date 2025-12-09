"""Fetcher loader utilities."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ..options import StoryScraperOptions
else:
    StoryScraperOptions = Any

ProgressCallback = Callable[[int, int, Path, bool], None]


class Fetcher(Protocol):
    """Fetcher interface."""

    def list_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
    ) -> list[str]: ...

    def fetch_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
        force_fetch: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> list[Path]: ...


def load_fetcher(name: str) -> Fetcher:
    """Instantiate the fetcher implementation from its module name."""

    module_name = name or "auto"
    module_path = f"{__name__}.{module_name}"
    module = import_module(module_path)
    fetcher_cls = getattr(module, "Fetcher", None)
    if fetcher_cls is None:
        raise ImportError(f"Fetcher module '{module_name}' missing Fetcher class")
    return fetcher_cls()
