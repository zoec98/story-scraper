from __future__ import annotations

from pathlib import Path

from storyscraper.fetch import run_fetch_list_phase
from storyscraper.options import StoryScraperOptions


def _story_html() -> str:
    return """
    <html>
      <head>
        <title>EroticStories.com: EXPOSING JULIE 1 by jwdoney (seduction)</title>
      </head>
      <body>
        <h1>EXPOSING JULIE 1 (fm:seduction, 8000 words) [1/4] <a href="parts.php?id=61794">show all parts</a></h1>
        <div>Author: <a href="author.php?id=1742">jwdoney</a></div>
      </body>
    </html>
    """


def _parts_html() -> str:
    return """
    <html>
      <head>
        <title>EroticStories.com: All parts of story: EXPOSING JULIE 1</title>
      </head>
      <body>
        <b>Some ad copy</b>
        <table>
          <tr><td><a href="story.php?id=61794"><b>EXPOSING JULIE 1</b></a></td></tr>
          <tr><td><a href="/my/story.php?id=61802"><b>EXPOSING JULIE 2</b></a></td></tr>
          <tr><td><a href="story.php?id=61842"><b>EXPOSING JULIE 3</b></a></td></tr>
        </table>
        <div>Author: <a href="author.php?id=1742">jwdoney</a></div>
      </body>
    </html>
    """


def _single_html() -> str:
    return """
    <html>
      <head>
        <title>EroticStories.com: Single Story by Writer</title>
      </head>
      <body>
        <h1>Single Story (fm:romance, 4000 words)</h1>
        <div>Author: <a href="author.php?id=999">Writer</a></div>
      </body>
    </html>
    """


def test_eroticstories_fetcher_handles_multiparts(monkeypatch, tmp_path: Path) -> None:
    story_html = _story_html()
    parts_html = _parts_html()

    def fake_fetch(
        self, url: str
    ) -> str:  # pragma: no cover - exercised via list phase
        if "parts.php" in url:
            return parts_html
        return story_html

    monkeypatch.setattr(
        "storyscraper.fetchers.eroticstories_fetcher.Fetcher._fetch_text", fake_fetch
    )

    options = StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="eroticstories_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://www.eroticstories.com/my/story.php?id=61794",
        author=None,
        chosen_author=None,
        chosen_name=None,
        chosen_slug=None,
    )

    urls = run_fetch_list_phase(options, stories_root=tmp_path)

    assert urls == [
        "https://www.eroticstories.com/my/story.php?id=61794",
        "https://www.eroticstories.com/my/story.php?id=61802",
        "https://www.eroticstories.com/my/story.php?id=61842",
    ]
    assert options.effective_name() == "EXPOSING JULIE 1"
    assert options.effective_slug() == "exposing-julie-1"
    assert options.effective_author() == "jwdoney"

    download_file = tmp_path / "exposing-julie-1" / "download_urls.txt"
    assert download_file.exists()
    assert download_file.read_text(encoding="utf-8").splitlines() == urls


def test_eroticstories_fetcher_handles_single_part(monkeypatch, tmp_path: Path) -> None:
    html = _single_html()
    monkeypatch.setattr(
        "storyscraper.fetchers.eroticstories_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    options = StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="eroticstories_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://www.eroticstories.com/my/story.php?id=70000",
        author=None,
        chosen_author=None,
        chosen_name=None,
        chosen_slug=None,
    )

    urls = run_fetch_list_phase(options, stories_root=tmp_path)

    assert urls == ["https://www.eroticstories.com/my/story.php?id=70000"]
    assert options.effective_name() == "Single Story"
    assert options.effective_author() == "Writer"
    assert options.effective_slug() == "single-story"

    download_file = tmp_path / "single-story" / "download_urls.txt"
    assert download_file.exists()
    assert download_file.read_text(encoding="utf-8").splitlines() == urls


def test_eroticstories_fetcher_stitches_rest_pages(monkeypatch, tmp_path: Path) -> None:
    main_html = """
    <html>
      <head><title>EroticStories.com: Joined Story by Author</title></head>
      <body>
        <div>
          <a name="textstart"></a>
          <p>Chrome text</p>
          <p>First part starts here.</p>
          <p><a href="story.php?id=1&rest=1">Click here to read the rest of this story</a></p>
        </div>
      </body>
    </html>
    """
    rest_html = """
    <html>
      <head><title>Rest page</title></head>
      <body>
        <div>
          <a name="textstart"></a>
          <p>Second part continues.</p>
          <p>And more text.</p>
        </div>
      </body>
    </html>
    """

    def fake_fetch(
        self, url: str
    ) -> str:  # pragma: no cover - exercised via fetch phase
        if "rest=1" in url:
            return rest_html
        return main_html

    monkeypatch.setattr(
        "storyscraper.fetchers.eroticstories_fetcher.Fetcher._fetch_text", fake_fetch
    )

    options = StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="eroticstories_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://www.eroticstories.com/my/story.php?id=1",
        author=None,
        chosen_author=None,
        chosen_name=None,
        chosen_slug=None,
    )

    run_fetch_list_phase(options, stories_root=tmp_path)

    from storyscraper.fetch import run_fetch_phase

    files = run_fetch_phase(options, stories_root=tmp_path, force_fetch=True)

    assert files, "No files fetched"
    content = files[0].read_text(encoding="utf-8")
    assert "Joined Story by Author" in content
    assert "First part starts here." in content
    assert "Second part continues." in content
