from storyscraper.transformers.ao3_transformer import Transformer


def test_ao3_transformer_extracts_user_content():
    html = """
    <div class="wrapper">
        <h2 class="heading">Chapter 12</h2>
        <div class="userstuff">
            <p>Paragraph one.</p>
            <p>Paragraph two.</p>
        </div>
        <div class="userstuff">
            <p>More text.</p>
        </div>
    </div>
    """

    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(html)  # type: ignore[attr-defined]

    assert markdown.lstrip().startswith("# Chapter 12")
    assert "Paragraph one." in markdown
    assert "More text." in markdown
