from __future__ import annotations

from pathlib import Path

from storyscraper.fetch import run_fetch_list_phase
from storyscraper.options import StoryScraperOptions

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "user-provided-data" / "bdsmlibrary"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="cp1252")


def test_bdsmlibrary_fetcher_extracts_chapters_and_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    html = _load_fixture("story-122-index.html")
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

    assert len(urls) == 53
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
