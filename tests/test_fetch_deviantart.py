from dataclasses import replace
from pathlib import Path

import pytest

from storyscraper.fetch import run_fetch_list_phase
from storyscraper.options import StoryScraperOptions


@pytest.fixture()
def deviantart_options() -> StoryScraperOptions:
    return StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="deviantart_fetcher",
        transform_agent="deviantart_transformer",
        packaging_agent="auto",
        download_url="https://www.deviantart.com/stevemnd/art/Jack-and-Monica-597938201",
        author=None,
        chosen_author=None,
        chosen_name=None,
        chosen_slug=None,
    )


def test_deviantart_fetcher_lists_single_url_and_updates_metadata(
    monkeypatch, tmp_path: Path, deviantart_options: StoryScraperOptions
) -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Jack and Monica by stevemnd on DeviantArt">
        <meta property="og:url" content="https://www.deviantart.com/stevemnd/art/Jack-and-Monica-597938201">
      </head>
      <body>
        <section class="YGJa8_">
          <span class="I0C9ST"><h2>Literature Text</h2></span>
          <div><p>Story</p></div>
        </section>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "storyscraper.fetchers.deviantart_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    urls = run_fetch_list_phase(deviantart_options, stories_root=tmp_path)

    assert urls == ["https://www.deviantart.com/stevemnd/art/Jack-and-Monica-597938201"]
    assert deviantart_options.effective_name() == "Jack and Monica"
    assert deviantart_options.effective_slug() == "jack-and-monica"
    assert deviantart_options.effective_author() == "stevemnd"

    download_file = tmp_path / "jack-and-monica" / "download_urls.txt"
    assert download_file.read_text(encoding="utf-8").splitlines() == urls


def test_deviantart_fetcher_uses_og_title_for_metadata_with_by_in_title(
    monkeypatch, tmp_path: Path, deviantart_options: StoryScraperOptions
) -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Step by Step by testbytest on DeviantArt">
      </head>
      <body>
        <section class="YGJa8_">
          <span class="I0C9ST"><h2>Literature Text</h2></span>
          <div><p>Story</p></div>
        </section>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "storyscraper.fetchers.deviantart_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    run_fetch_list_phase(deviantart_options, stories_root=tmp_path)

    assert deviantart_options.effective_name() == "Step by Step"
    assert deviantart_options.effective_author() == "testbytest"


def test_deviantart_fetcher_uses_title_tag_for_metadata(
    monkeypatch, tmp_path: Path, deviantart_options: StoryScraperOptions
) -> None:
    html = """
    <html>
      <head>
        <title>Step by Step by testbytest on DeviantArt</title>
      </head>
      <body>
        <section class="YGJa8_">
          <span class="I0C9ST"><h2>Literature Text</h2></span>
          <div><p>Story</p></div>
        </section>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "storyscraper.fetchers.deviantart_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    run_fetch_list_phase(deviantart_options, stories_root=tmp_path)

    assert deviantart_options.effective_name() == "Step by Step"
    assert deviantart_options.effective_author() == "testbytest"


def test_deviantart_fetcher_skips_non_literature(
    monkeypatch, tmp_path: Path, deviantart_options: StoryScraperOptions
) -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Not Literature by testbytest on DeviantArt">
      </head>
      <body>
        <main>
          <div data-hook="deviation_body"><p>Image only</p></div>
        </main>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "storyscraper.fetchers.deviantart_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    with pytest.warns(
        UserWarning,
        match="DeviantArt: URL does not contain content that can be recognized as a Literature Deviation",
    ):
        urls = run_fetch_list_phase(deviantart_options, stories_root=tmp_path)

    assert urls == []


def test_deviantart_fetcher_lists_gallery_urls(
    monkeypatch, tmp_path: Path, deviantart_options: StoryScraperOptions
) -> None:
    html_page_one = """
    <html>
      <head>
        <meta property="og:title" content="Example User Profile | DeviantArt">
        <link rel="next" href="https://www.deviantart.com/example_user/gallery/123/example-story?page=2">
        <script>
          window.__INITIAL_STATE__ = JSON.parse("{\\"gallectionSection\\":{\\"selectedFolderId\\":123},\\"@@entities\\":{\\"galleryFolder\\":{\\"123\\":{\\"name\\":\\"Example Story Title\\"}}}}");
        </script>
      </head>
      <body>
        <a href="https://www.deviantart.com/example_user/art/Chapter-One-123">One</a>
        <a href="https://www.deviantart.com/example_user/art/Chapter-One-123#comments">One comments</a>
        <a href="/example_user/art/Chapter-Two-456?view=1">Two</a>
        <a href="https://www.deviantart.com/other/art/Other-999">Other</a>
      </body>
    </html>
    """
    html_page_two = """
    <html>
      <head></head>
      <body>
        <a href="https://www.deviantart.com/example_user/art/Chapter-Three-789">Three</a>
      </body>
    </html>
    """

    monkeypatch.setattr(
        "storyscraper.fetchers.deviantart_fetcher.Fetcher._fetch_text",
        lambda self, url: html_page_two if "page=2" in url else html_page_one,
    )

    gallery_options = replace(
        deviantart_options,
        download_url=(
            "https://www.deviantart.com/example_user/gallery/123/example-story"
        ),
    )

    urls = run_fetch_list_phase(gallery_options, stories_root=tmp_path)

    assert urls == [
        "https://www.deviantart.com/example_user/art/Chapter-One-123",
        "https://www.deviantart.com/example_user/art/Chapter-Two-456",
        "https://www.deviantart.com/example_user/art/Chapter-Three-789",
    ]
    assert gallery_options.effective_name() == "Example Story Title"
    assert gallery_options.effective_slug() == "example-story-title"


def test_deviantart_fetcher_stops_at_total_pages(
    monkeypatch, tmp_path: Path, deviantart_options: StoryScraperOptions
) -> None:
    html_page_one = """
    <html>
      <head>
        <link rel="next" href="https://www.deviantart.com/example_user/gallery/1?page=2">
        <script>
          window.__INITIAL_STATE__ = JSON.parse("{\\"pageInfo\\":{\\"currentPage\\":1,\\"totalPages\\":2}}");
        </script>
      </head>
      <body>
        <a href="https://www.deviantart.com/example_user/art/Chapter-One-123">One</a>
      </body>
    </html>
    """
    html_page_two = """
    <html>
      <head>
        <link rel="next" href="https://www.deviantart.com/example_user/gallery/1?page=3">
        <script>
          window.__INITIAL_STATE__ = JSON.parse("{\\"pageInfo\\":{\\"currentPage\\":2,\\"totalPages\\":2}}");
        </script>
      </head>
      <body>
        <a href="https://www.deviantart.com/example_user/art/Chapter-Two-456">Two</a>
      </body>
    </html>
    """
    html_page_three = """
    <html>
      <body>
        <a href="https://www.deviantart.com/example_user/art/Chapter-Three-789">Three</a>
      </body>
    </html>
    """
    calls: list[str] = []

    def _fake_fetch(self, url: str) -> str:
        calls.append(url)
        if "page=2" in url:
            return html_page_two
        if "page=3" in url:
            return html_page_three
        return html_page_one

    monkeypatch.setattr(
        "storyscraper.fetchers.deviantart_fetcher.Fetcher._fetch_text",
        _fake_fetch,
    )

    gallery_options = replace(
        deviantart_options,
        download_url="https://www.deviantart.com/example_user/gallery/1",
    )

    urls = run_fetch_list_phase(gallery_options, stories_root=tmp_path)

    assert urls == [
        "https://www.deviantart.com/example_user/art/Chapter-One-123",
        "https://www.deviantart.com/example_user/art/Chapter-Two-456",
    ]
    assert not any("page=3" in url for url in calls)
