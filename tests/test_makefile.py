from pathlib import Path

from storyscraper.makefile import write_makefile
from storyscraper.options import StoryScraperOptions


def test_write_makefile_creates_file(tmp_path: Path) -> None:
    options = StoryScraperOptions(
        name="Story",
        slug="story",
        fetch_agent="auto",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://example.com",
        chosen_name="Story",
        chosen_slug="story",
        chosen_author="Author",
    )

    path = write_makefile(options, stories_root=tmp_path)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert 'TITLE := "Story"' in content
    assert 'AUTHOR := "Author"' in content
