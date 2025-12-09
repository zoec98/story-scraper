"""Transformer loader utilities."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, Callable

if TYPE_CHECKING:
    from ..options import StoryScraperOptions

ProgressCallback = Callable[[int, int, Path, bool], None]


class Transformer(Protocol):
    """Transformer interface."""

    def transform_phase(
        self,
        options: StoryScraperOptions,
        *,
        stories_root: Path | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> list[Path]: ...


def load_transformer(name: str) -> Transformer:
    """Instantiate a transformer implementation."""

    module_name = name or "auto"
    module_path = f"{__name__}.{module_name}"
    module = import_module(module_path)
    transformer_cls = getattr(module, "Transformer", None)
    if transformer_cls is None:
        raise ImportError(
            f"Transformer module '{module_name}' missing Transformer class"
        )
    return transformer_cls()
