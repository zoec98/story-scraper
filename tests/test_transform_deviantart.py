import json
from pathlib import Path

from bs4 import BeautifulSoup

from storyscraper.options import StoryScraperOptions
from storyscraper.transform import run_transform_phase
from storyscraper.transformers.deviantart_transformer import Transformer


def test_deviantart_transformer_prefers_deviation_body() -> None:
    html = """
    <html>
      <body>
        <main><p>Main content</p></main>
        <div data-hook="deviation_body"><p>Story content</p></div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    transformer = Transformer()

    root = transformer.extract_content_root(soup)

    assert root.get("data-hook") == "deviation_body"
    assert "Story content" in root.get_text()


def test_deviantart_transformer_extracts_literature_text() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Jack and Monica by stevemnd on DeviantArt">
      </head>
      <body>
        <section class="YGJa8_">
          <span class="I0C9ST"><h2>Literature Text</h2></span>
          <div>
            <p>Line one.</p>
            <p>Line two.</p>
          </div>
        </section>
      </body>
    </html>
    """
    transformer = Transformer()

    markdown = transformer._convert_html_to_markdown(html)

    assert markdown.lstrip().startswith("# Jack and Monica")
    assert "Line one." in markdown
    assert "Line two." in markdown


def test_deviantart_transformer_writes_metadata_json(tmp_path: Path) -> None:
    options = StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="auto",
        transform_agent="deviantart_transformer",
        packaging_agent="auto",
        download_url="https://www.deviantart.com/stevemnd/art/Jack-and-Monica-597938201",
        chosen_name="Jack and Monica",
        chosen_slug="jack-and-monica",
    )
    story_dir = tmp_path / options.effective_slug()
    html_dir = story_dir / "html"
    html_dir.mkdir(parents=True)
    html_dir.joinpath("jack-and-monica-001.html").write_text(
        """
        <html>
          <head>
            <meta property="og:title" content="Jack and Monica by stevemnd on DeviantArt">
          </head>
          <body>
            <section class="YGJa8_">
              <span class="I0C9ST"><h2>Literature Text</h2></span>
              <div><p>Story content</p></div>
            </section>
            <script>
              window.__INITIAL_STATE__ = JSON.parse("{\\"@@DUPERBROWSE\\":{\\"rootStream\\":{\\"currentOpenItem\\":597938201}},\\"@@entities\\":{\\"deviation\\":{\\"597938201\\":{\\"deviationId\\":597938201,\\"title\\":\\"Jack and Monica\\",\\"author\\":{\\"username\\":\\"stevemnd\\"},\\"stats\\":{\\"comments\\":12,\\"favourites\\":103,\\"views\\":10878}}},\\"deviationExtended\\":{\\"597938201\\":{\\"tags\\":[{\\"name\\":\\"asfr\\"},{\\"name\\":\\"costume\\"}]}}}}");
            </script>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    run_transform_phase(options, stories_root=tmp_path)

    metadata_path = story_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    entry = metadata["597938201"]
    assert entry["tags"] == ["asfr", "costume"]
    assert entry["title"] == "Jack and Monica"
    assert entry["author"] == "stevemnd"
    assert entry["deviation_id"] == "597938201"
    assert entry["saveto"] == "html/jack-and-monica-001.html"
    assert entry["last_updated"].endswith("+00:00")


def test_deviantart_transformer_orders_by_publish_date(tmp_path: Path) -> None:
    options = StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="auto",
        transform_agent="deviantart_transformer",
        packaging_agent="auto",
        download_url="https://www.deviantart.com/example_user/art/example-111",
        chosen_name="Example Story",
        chosen_slug="example-story",
    )
    story_dir = tmp_path / options.effective_slug()
    html_dir = story_dir / "html"
    html_dir.mkdir(parents=True)

    html_dir.joinpath("example-story-002.html").write_text(
        """
        <html>
          <head>
            <meta property="og:title" content="Example Story by example_user on DeviantArt">
          </head>
          <body>
            <script>
              window.__INITIAL_STATE__ = JSON.parse("{\\"@@DUPERBROWSE\\":{\\"rootStream\\":{\\"currentOpenItem\\":222}},\\"@@entities\\":{\\"deviation\\":{\\"222\\":{\\"deviationId\\":222,\\"publishedTime\\":\\"2025-10-02T10:00:00-0700\\"}}}}");
            </script>
            <section class="YGJa8_">
              <span class="I0C9ST"><h2>Literature Text</h2></span>
              <div><p>Second chapter.</p></div>
            </section>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    html_dir.joinpath("example-story-001.html").write_text(
        """
        <html>
          <head>
            <meta property="og:title" content="Example Story by example_user on DeviantArt">
          </head>
          <body>
            <script>
              window.__INITIAL_STATE__ = JSON.parse("{\\"@@DUPERBROWSE\\":{\\"rootStream\\":{\\"currentOpenItem\\":111}},\\"@@entities\\":{\\"deviation\\":{\\"111\\":{\\"deviationId\\":111,\\"publishedTime\\":\\"2025-09-30T10:00:00-0700\\"}}}}");
            </script>
            <section class="YGJa8_">
              <span class="I0C9ST"><h2>Literature Text</h2></span>
              <div><p>First chapter.</p></div>
            </section>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    transformed = run_transform_phase(options, stories_root=tmp_path)

    assert len(transformed) == 2
    first_markdown = (story_dir / "markdown" / "example-story-001.md").read_text(
        encoding="utf-8"
    )
    second_markdown = (story_dir / "markdown" / "example-story-002.md").read_text(
        encoding="utf-8"
    )
    assert "First chapter." in first_markdown
    assert "Second chapter." in second_markdown
