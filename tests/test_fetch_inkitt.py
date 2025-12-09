from __future__ import annotations

import pytest

from storyscraper.fetch import run_fetch_list_phase
from storyscraper.options import StoryScraperOptions


def _inkitt_html(include_locked: bool = True) -> str:
    locked_li = (
        """
        <li class=''>
            <a class="chapter-link" rel="nofollow" href="/stories/1548300/chapters/34">
                <span class='chapter-patron-icon'><img src="locked.svg"></span>
                <span class='chapter-nr'>34</span>
                <span class='chapter-title'>Chapter 33</span>
            </a>
        </li>
        """
        if include_locked
        else ""
    )
    return f"""
    <html>
      <head>
        <script type="application/ld+json">{{
          "@context":"http://schema.org",
          "@type":"Article",
          "headline":"Mated to the Ice King",
          "author":{{"@type":"Person","name":"Amal A. Usman"}}
        }}</script>
      </head>
      <body>
        <ul class='nav nav-list chapter-list-dropdown'>
          <li class='active'>
            <a class="chapter-link" rel="nofollow" href="/stories/1548300/chapters/1">
              <span class='chapter-nr'>1</span>
              <span class='chapter-title'>Chapter 1</span>
            </a>
          </li>
          <li class=''>
            <a class="chapter-link" rel="nofollow" href="/stories/1548300/chapters/2">
              <span class='chapter-nr'>2</span>
              <span class='chapter-title'>Chapter 2</span>
            </a>
          </li>
          {locked_li}
        </ul>
      </body>
    </html>
    """


@pytest.fixture()
def inkitt_options() -> StoryScraperOptions:
    return StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="inkitt_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://www.inkitt.com/stories/1548300",
        author=None,
        chosen_author=None,
        chosen_name=None,
        chosen_slug=None,
    )


def test_inkitt_fetcher_extracts_chapters_and_metadata(
    monkeypatch, tmp_path, inkitt_options: StoryScraperOptions
) -> None:
    html = _inkitt_html(include_locked=False)

    monkeypatch.setattr(
        "storyscraper.fetchers.inkitt_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    urls = run_fetch_list_phase(inkitt_options, stories_root=tmp_path)

    assert urls == [
        "https://www.inkitt.com/stories/1548300/chapters/1",
        "https://www.inkitt.com/stories/1548300/chapters/2",
    ]
    assert inkitt_options.effective_name() == "Mated to the Ice King"
    assert inkitt_options.effective_slug() == "mated-to-the-ice-king"
    assert inkitt_options.effective_author() == "Amal A. Usman"


def test_inkitt_fetcher_warns_on_locked_chapters(
    monkeypatch, tmp_path, inkitt_options: StoryScraperOptions
) -> None:
    html = _inkitt_html(include_locked=True)

    monkeypatch.setattr(
        "storyscraper.fetchers.inkitt_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    with pytest.warns(UserWarning, match="Inkitt: skipped 1 locked chapter"):
        urls = run_fetch_list_phase(inkitt_options, stories_root=tmp_path)

    assert urls == [
        "https://www.inkitt.com/stories/1548300/chapters/1",
        "https://www.inkitt.com/stories/1548300/chapters/2",
    ]
