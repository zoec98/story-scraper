from __future__ import annotations

from pathlib import Path

from storyscraper.fetch import run_fetch_list_phase
from storyscraper.options import StoryScraperOptions


def _fixture_html() -> str:
    return """
    <html>
      <head>
        <title>BDSM Library - Story: Hired Help</title>
      </head>
      <body>
        <a href="/stories/author.php?authorid=82">Dark One</a>
        <table>
          <tr><td><b><a href="/stories/chapter.php?storyid=122&chapterid=1075">Chapter 1</a></b></td></tr>
          <tr><td><b><a href="/stories/chapter.php?storyid=122&chapterid=1076">Chapter 2</a></b></td></tr>
          <tr><td><b><a href="/stories/chapter.php?storyid=999&chapterid=1">Other Story</a></b></td></tr>
        </table>
      </body>
    </html>
    """


def test_bdsmlibrary_fetcher_extracts_chapters_and_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    html = _fixture_html()
    options = StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="bdsmlibrary_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://www.bdsmlibrary.com/stories/story.php?storyid=122",
        author=None,
        chosen_author=None,
        chosen_name=None,
        chosen_slug=None,
    )

    monkeypatch.setattr(
        "storyscraper.fetchers.bdsmlibrary_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    urls = run_fetch_list_phase(options, stories_root=tmp_path)

    assert len(urls) == 2
    assert urls[0] == (
        "https://www.bdsmlibrary.com/stories/chapter.php?storyid=122&chapterid=1075"
    )
    assert urls[1] == (
        "https://www.bdsmlibrary.com/stories/chapter.php?storyid=122&chapterid=1076"
    )
    assert options.effective_name() == "Hired Help"
    assert options.effective_slug() == "hired-help"
    assert options.effective_author() == "Dark One"

    download_file = tmp_path / "hired-help" / "download_urls.txt"
    assert download_file.exists()
    assert download_file.read_text(encoding="utf-8").splitlines()[0] == urls[0]
