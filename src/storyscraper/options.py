"""Command-line option parsing for StoryScraper."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Sequence
from urllib.parse import urlparse, unquote

from .urlclassifier import SiteMatch, classify_url

DEFAULT_AGENT = "auto"
_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class StoryScraperOptions:
    """Structured representation of CLI arguments."""

    name: str | None
    slug: str | None
    fetch_agent: str
    transform_agent: str
    packaging_agent: str
    download_url: str
    site_name: str | None = None
    site_documentation: str | None = None
    force_fetch: bool = False
    author: str | None = None
    chosen_name: str | None = None
    chosen_slug: str | None = None
    chosen_author: str | None = None
    verbose: bool = False
    quiet: bool = False
    cookies_from_browser: str | None = None
    invocation_command: str | None = None

    def effective_name(self) -> str:
        """Return the user-specified or derived story name."""

        return self.name or self.chosen_name or "Story"

    def effective_slug(self) -> str:
        """Return the user-specified or derived slug."""

        return self.slug or self.chosen_slug or "story"

    def effective_author(self) -> str:
        """Return the user-specified or derived author."""

        return self.author or self.chosen_author or "Unknown"


def parse_cli_args(argv: Sequence[str] | None = None) -> StoryScraperOptions:
    """Parse CLI arguments into a dataclass."""

    parser = argparse.ArgumentParser(
        prog="storyscraper",
        description="Download and package web stories.",
    )
    parser.add_argument(
        "--name", help="Friendly story title; defaults to URL basename."
    )
    parser.add_argument(
        "--slug",
        help="Directory-friendly slug; defaults to a slugified name.",
    )
    parser.add_argument(
        "--fetch-agent",
        default=DEFAULT_AGENT,
        help='Override the fetch agent (default: "auto").',
    )
    parser.add_argument(
        "--transform-agent",
        default=DEFAULT_AGENT,
        help='Override the transform agent (default: "auto").',
    )
    parser.add_argument(
        "--packaging-agent",
        default=DEFAULT_AGENT,
        help='Override the packaging agent (default: "auto").',
    )
    parser.add_argument(
        "--author",
        help="Author name; defaults to site metadata when available.",
    )
    parser.add_argument(
        "--force-fetch",
        action="store_true",
        help="Force re-downloading chapters even if HTML files already exist.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output (errors only).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed per-file progress for each phase.",
    )
    parser.add_argument(
        "--cookies-from-browser",
        help="Load cookies from the specified browser profile (e.g., 'firefox').",
    )
    parser.add_argument(
        "download_url",
        help="URL to download; required.",
    )

    args = parser.parse_args(argv)
    download_url = args.download_url

    if args.quiet and args.verbose:
        parser.error("--quiet and --verbose cannot be combined.")

    name = args.name
    chosen_name = name or _derive_name_from_url(download_url)

    slug_source = args.slug or chosen_name
    slug = args.slug
    chosen_slug = slugify(slug_source)

    author = args.author
    chosen_author = author
    cookies_from_browser = args.cookies_from_browser
    import shlex
    import sys

    argv_source = list(argv) if argv is not None else sys.argv[1:]
    program = sys.argv[0] if sys.argv else "storyscraper"
    invocation_command = shlex.join([program, *argv_source])

    site_match: SiteMatch | None = classify_url(download_url)
    fetch_agent = _merge_agent(args.fetch_agent, site_match, "fetch_agent")
    transform_agent = _merge_agent(args.transform_agent, site_match, "transform_agent")
    packaging_agent = _merge_agent(args.packaging_agent, site_match, "packaging_agent")

    options = StoryScraperOptions(
        name=name,
        slug=slug,
        fetch_agent=fetch_agent,
        transform_agent=transform_agent,
        packaging_agent=packaging_agent,
        download_url=download_url,
        site_name=site_match.name if site_match else None,
        site_documentation=site_match.documentation if site_match else None,
        force_fetch=args.force_fetch,
        author=author,
        chosen_name=chosen_name,
        chosen_slug=chosen_slug,
        chosen_author=chosen_author,
        verbose=args.verbose,
        quiet=args.quiet,
        cookies_from_browser=cookies_from_browser,
        invocation_command=invocation_command,
    )
    return options


def _merge_agent(
    cli_value: str,
    site_match: SiteMatch | None,
    attr: str,
) -> str:
    """Decide which agent to use, preferring CLI overrides."""

    if cli_value != DEFAULT_AGENT:
        return cli_value

    if site_match is None:
        return DEFAULT_AGENT

    site_agent = getattr(site_match, attr)
    return site_agent or DEFAULT_AGENT


def _derive_name_from_url(url: str) -> str:
    """Create a title-like name from the URL basename."""

    parsed = urlparse(url)
    basename = PurePosixPath(parsed.path).name

    if not basename:
        basename = parsed.netloc or url

    basename = unquote(basename)
    if "." in basename:
        basename = basename.rsplit(".", 1)[0]

    candidate = basename.replace("-", " ").replace("_", " ").strip()
    candidate = " ".join(candidate.split())

    if not candidate:
        candidate = parsed.netloc or "Story"

    return candidate.title()


def slugify(value: str) -> str:
    """Convert arbitrary input to a filesystem-friendly slug. Public, since it is also used elsewhere."""

    slug = _SLUG_INVALID_CHARS.sub("-", value.lower()).strip("-")
    return slug or "story"
