from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from storyscraper.options import StoryScraperOptions
from storyscraper.transform import run_transform_phase
from storyscraper.transformers.auto import Transformer


@pytest.fixture()
def options() -> StoryScraperOptions:
    return StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="auto",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://example.com/story",
        chosen_name="Example Story",
        chosen_slug="example-story",
    )


def test_extract_content_prefers_main() -> None:
    transformer = Transformer()
    html = """
    <html>
        <body>
            <article><p>Article content</p></article>
            <main><p>Main content</p></main>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    root = transformer.extract_content_root(soup)

    assert root.name == "main"
    assert "Main content" in root.get_text()


def test_extract_content_falls_back_to_body_structure() -> None:
    transformer = Transformer()
    html = """
    <html>
        <body>
            <header>Header content</header>
            <div class="content">
                <h1>Heading</h1>
                <p>Body content</p>
            </div>
            <footer>Footer</footer>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    root = transformer.extract_content_root(soup)

    assert root.name == "div"
    assert "Body content" in root.get_text()


def test_transform_phase_writes_markdown_files(
    monkeypatch, tmp_path: Path, options: StoryScraperOptions
) -> None:
    story_dir = tmp_path / options.effective_slug()
    html_dir = story_dir / "html"
    html_dir.mkdir(parents=True)
    html_file = html_dir / f"{options.effective_slug()}-001.html"
    html_file.write_text(
        """
        <html>
            <body>
                <main>
                    <h1>Title</h1>
                    <p>Hello world</p>
                </main>
            </body>
        </html>
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "storyscraper.transformers.auto.html_to_markdown",
        lambda value: "# Title\n\nHello world\n",
    )

    markdown_files = run_transform_phase(options, stories_root=tmp_path)

    assert len(markdown_files) == 1
    output = markdown_files[0]
    assert output.exists()
    contents = output.read_text(encoding="utf-8")
    assert "Hello world" in contents
