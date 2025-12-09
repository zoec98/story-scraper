"""Inkitt transformer.

Currently delegates to the auto transformer because Inkitt chapter pages expose
the story content inside a plain <article> that auto handles cleanly. This exists
to make the explicit choice visible and leaves a hook for future site tweaks.
"""

from __future__ import annotations

from .auto import Transformer as AutoTransformer


class Transformer(AutoTransformer):
    """Inkitt-specific transformer (currently inherits auto behavior)."""

    pass
