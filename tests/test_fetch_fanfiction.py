from __future__ import annotations

from pathlib import Path

import pytest

from storyscraper.fetch import run_fetch_list_phase
from storyscraper.options import StoryScraperOptions


@pytest.fixture()
def fanfiction_options() -> StoryScraperOptions:
    return StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="fanfiction_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://www.fanfiction.net/s/14308516/2/A-Reimagination-of-H2O-Just-Add-Water-Season-Three",
        chosen_name="Fallback",
        chosen_slug="fallback",
    )


def _sample_html() -> str:
    return """
    <html>
        <body>
            <div>
                <b class='xcontrast_txt'>A Reimagination of H2O: Just Add Water, Season Three</b>
                <span class='xcontrast_txt'>By:</span>
                <a class='xcontrast_txt' href='/u/16067946/MerJen1193'>MerJen1193</a>
            </div>
            <select id="chap_select">
                <option value="1">1. New Beginnings</option>
                <option value="2">2. And Then There Were Four</option>
                <option value="3">3. A Quick Little Visit</option>
            </select>
        </body>
    </html>
    """


def test_fanfiction_fetcher_discovers_chapters(
    monkeypatch, tmp_path: Path, fanfiction_options: StoryScraperOptions
) -> None:
    monkeypatch.setattr(
        "storyscraper.fetchers.fanfiction_fetcher.Fetcher._fetch_text",
        lambda self, url: _sample_html(),
    )

    urls = run_fetch_list_phase(fanfiction_options, stories_root=tmp_path)

    expected = [
        "https://www.fanfiction.net/s/14308516/1/A-Reimagination-of-H2O-Just-Add-Water-Season-Three",
        "https://www.fanfiction.net/s/14308516/2/A-Reimagination-of-H2O-Just-Add-Water-Season-Three",
        "https://www.fanfiction.net/s/14308516/3/A-Reimagination-of-H2O-Just-Add-Water-Season-Three",
    ]
    assert urls == expected
    assert (
        fanfiction_options.effective_name()
        == "A Reimagination of H2O: Just Add Water, Season Three"
    )
    assert fanfiction_options.effective_author() == "MerJen1193"
    assert (
        fanfiction_options.effective_slug()
        == "a-reimagination-of-h2o-just-add-water-season-three"
    )
