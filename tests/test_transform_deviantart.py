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


def test_deviantart_transformer_writes_tags_json(tmp_path: Path) -> None:
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
            <div class="k_p5oR KVzYJT">
              <a href="https://www.deviantart.com/tag/asfr" data-tagname="asfr">asfr</a>
              <a href="https://www.deviantart.com/tag/costume" data-tagname="costume">costume</a>
            </div>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    run_transform_phase(options, stories_root=tmp_path)

    tags_path = story_dir / "tags.json"
    tags = json.loads(tags_path.read_text(encoding="utf-8"))
    assert tags == {"tags": ["asfr", "costume"]}
