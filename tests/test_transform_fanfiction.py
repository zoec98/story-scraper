from storyscraper.transformers.fanfiction_transformer import Transformer


def test_fanfiction_transformer_converts_storytext() -> None:
    html = """
    <html>
        <body>
            <div class='storytext xcontrast_txt nocopy' id='storytext'>
                <p><strong>Chapter Title</strong></p>
                <p>First paragraph.</p>
                <p>Second paragraph.</p>
            </div>
        </body>
    </html>
    """

    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(html)  # type: ignore[attr-defined]

    assert markdown.startswith("# Chapter Title")
    assert "First paragraph." in markdown
    assert "Second paragraph." in markdown
