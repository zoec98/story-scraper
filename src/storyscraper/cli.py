"""Command-line interface for StoryScraper."""

from __future__ import annotations

import csv
import json
import warnings
from io import StringIO
from pathlib import Path
from typing import Callable

from . import http as http_client
from .fetch import run_fetch_list_phase, run_fetch_phase
from .makefile import write_makefile
from .options import parse_cli_args
from .urlclassifier import list_site_rules
from .transform import run_transform_phase

ProgressCallback = Callable[[int, int, Path, bool], None]


def main(argv: list[str] | None = None) -> int:
    """Entry-point invoked by the `storyscraper` console script."""

    options = parse_cli_args(argv)
    if options.list_site_rules_format:
        print(_render_site_rules(options.list_site_rules_format))
        return 0
    logger = _build_logger(options.quiet)
    verbose = options.verbose and not options.quiet

    _configure_http(options, logger)

    logger("List phase: starting")
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        listed = run_fetch_list_phase(options)
    _log_warning_records(caught_warnings, logger)

    logger(f"List phase: discovered {len(listed)} chapter URL(s)")

    fetch_progress = _build_progress_logger(logger, "Fetch phase") if verbose else None

    logger("Fetch phase: starting")
    with warnings.catch_warnings(record=True) as fetch_warnings:
        warnings.simplefilter("always")
        fetched = run_fetch_phase(
            options,
            force_fetch=options.force_fetch,
            progress_callback=fetch_progress,
        )
    _log_warning_records(fetch_warnings, logger)
    logger(
        f"Fetch phase: downloaded {len(fetched)} file(s) (out of {len(listed)} listed)"
    )

    transform_progress = (
        _build_progress_logger(logger, "Transform phase") if verbose else None
    )

    logger("Transform phase: starting")
    with warnings.catch_warnings(record=True) as transform_warnings:
        warnings.simplefilter("always")
        transformed = run_transform_phase(
            options,
            progress_callback=transform_progress,
        )
    _log_warning_records(transform_warnings, logger)
    logger(
        f"Transform phase: wrote {len(transformed)} markdown file(s) "
        f"for '{options.effective_name()}' ({options.effective_slug()})"
    )

    write_makefile(options)
    logger("Makefile: generated pandoc build file")

    return 0


def _render_site_rules(fmt: str) -> str:
    rules = list_site_rules()
    payload = [
        {
            "pattern": rule.pattern.pattern,
            "name": rule.name,
            "full_name": rule.full_name,
            "documentation": rule.documentation,
            "fetch_agent": rule.fetch_agent,
            "transform_agent": rule.transform_agent,
        }
        for rule in rules
    ]

    if fmt == "json":
        return json.dumps(payload, indent=2, sort_keys=True)

    if fmt == "csv":
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "pattern",
                "name",
                "full_name",
                "documentation",
                "fetch_agent",
                "transform_agent",
            ],
        )
        writer.writeheader()
        writer.writerows(payload)
        return output.getvalue().rstrip()

    lines = []
    for entry in payload:
        lines.append(
            " | ".join(
                [
                    entry["name"] or "",
                    entry["full_name"] or "",
                    entry["pattern"] or "",
                    entry["fetch_agent"] or "",
                    entry["transform_agent"] or "",
                    entry["documentation"] or "",
                ]
            )
        )
    return "\n".join(lines)


def _configure_http(options, log) -> None:
    sleep_min = getattr(options, "sleep_min", None)
    sleep_max = getattr(options, "sleep_max", None)
    if sleep_min is not None or sleep_max is not None:
        http_client.set_delay_bounds(sleep_min, sleep_max)
    if not options.cookies_from_browser:
        return

    from . import cookies as cookie_loader

    browser = options.cookies_from_browser
    try:
        jar = cookie_loader.extract_cookies_from_browser(
            browser,
            logger=cookie_loader.YDLLogger(),
        )
    except cookie_loader.CookieLoadError as exc:
        log(f"Cookies: failed to load from {browser}: {exc}")
        return
    except Exception as exc:  # pragma: no cover - unexpected runtime issues
        log(f"Cookies: unexpected error loading from {browser}: {exc}")
        return

    http_client.configure_session(cookies=jar)
    log(f"Cookies: loaded {len(jar)} entries from {browser}")


def _build_logger(quiet: bool) -> Callable[[str], None]:
    def _log(message: str) -> None:
        if not quiet:
            print(message)

    return _log


def _build_progress_logger(
    log: Callable[[str], None],
    label: str,
) -> ProgressCallback:
    def _progress(
        current: int,
        total: int,
        destination: Path,
        skipped: bool,
    ) -> None:
        status = "skipped" if skipped else "done"
        log(f"{label} {current}/{total}: {destination.name} [{status}]")

    return _progress


def _log_warning_records(
    records: list[warnings.WarningMessage], log: Callable[[str], None]
) -> None:
    for record in records:
        message = str(record.message)
        if message:
            log(f"Warning: {message}")
