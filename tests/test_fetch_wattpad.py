from pathlib import Path

import pytest

from storyscraper.fetch import run_fetch_list_phase
from storyscraper.options import StoryScraperOptions


@pytest.fixture()
def wattpad_options() -> StoryScraperOptions:
    return StoryScraperOptions(
        name="Dedication",
        slug="dedication",
        fetch_agent="wattpad_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://www.wattpad.com/1451697592-dedication-aesthetics",
        author="Author",
        chosen_name="Dedication",
        chosen_slug="dedication",
        chosen_author="Author",
    )


def test_wattpad_fetcher_extracts_table_of_contents(
    monkeypatch, tmp_path: Path, wattpad_options: StoryScraperOptions
) -> None:
    html = """
    <div class="dropdown-menu pull-left">
        <ul class="table-of-contents">
            <li><a class="on-navigate" href="/1451697592-dedication-aesthetics">Dedication &amp; Aesthetics</a></li>
            <li><a class="on-navigate" href="/1451712786-trigger-warnings">Trigger Warnings</a></li>
            <li><a class="on-navigate" href="/1500625748-stuck-with-you">Stuck With You</a></li>
        </ul>
    </div>
    """

    monkeypatch.setattr(
        "storyscraper.fetchers.wattpad_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    urls = run_fetch_list_phase(wattpad_options, stories_root=tmp_path)

    expected = [
        "https://www.wattpad.com/1451697592-dedication-aesthetics",
        "https://www.wattpad.com/1451712786-trigger-warnings",
        "https://www.wattpad.com/1500625748-stuck-with-you",
    ]

    assert urls == expected
    download_file = tmp_path / "dedication" / "download_urls.txt"
    assert download_file.read_text(encoding="utf-8").splitlines() == expected


def test_wattpad_fetcher_warns_on_locked_chapters(
    monkeypatch, tmp_path: Path, wattpad_options: StoryScraperOptions
) -> None:
    html = """
    <div class="dropdown-menu pull-left">
        <ul class="table-of-contents">
            <li><a class="on-navigate" href="/free">Free</a></li>
            <li>
                <a class="on-navigate blocked" href="/locked">
                    Locked
                    <span class="fa fa-lock fa-wp-neutral-2 pull-right" aria-hidden="true"></span>
                </a>
            </li>
        </ul>
    </div>
    """

    monkeypatch.setattr(
        "storyscraper.fetchers.wattpad_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    with pytest.warns(UserWarning, match="Wattpad: skipped 1 locked chapter"):
        urls = run_fetch_list_phase(wattpad_options, stories_root=tmp_path)

    assert urls == ["https://www.wattpad.com/free"]


def test_wattpad_fetcher_falls_back_to_auto_logic(
    monkeypatch, tmp_path: Path, wattpad_options: StoryScraperOptions
) -> None:
    html = """
    <html>
        <body>
            <a href="/story/secondary">Secondary Chapter</a>
            <a href="https://example.com/outside">Ignore</a>
        </body>
    </html>
    """

    monkeypatch.setattr(
        "storyscraper.fetchers.wattpad_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    urls = run_fetch_list_phase(wattpad_options, stories_root=tmp_path)

    assert urls == ["https://www.wattpad.com/story/secondary"]


def test_wattpad_fetcher_updates_title_and_author(
    monkeypatch, tmp_path: Path, wattpad_options: StoryScraperOptions
) -> None:
    html = """
    <div id="funbar-container">
        <div id="funbar">
            <div id="funbar-story" class="dropdown">
                <span class="info">
                    <h2 class="title h5">Between The Crystals</h2>
                    <span class="author h6">by CrystalScherer</span>
                </span>
            </div>
        </div>
        <ul class="table-of-contents">
            <li><a href="/123">One</a></li>
        </ul>
    </div>
    """

    options = wattpad_options
    options.name = None
    options.slug = None
    options.author = None
    options.chosen_author = None

    monkeypatch.setattr(
        "storyscraper.fetchers.wattpad_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    run_fetch_list_phase(options, stories_root=tmp_path)

    assert options.effective_name() == "Between The Crystals"
    assert options.effective_slug() == "between-the-crystals"
    assert options.effective_author() == "CrystalScherer"
