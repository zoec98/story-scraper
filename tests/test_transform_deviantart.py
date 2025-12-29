from bs4 import BeautifulSoup

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
