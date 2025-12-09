from __future__ import annotations

from storyscraper.transformers.literotica_transformer import Transformer


def _article_ld_json() -> str:
    return """
    {
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "Harem House - Selene Pt. 01",
      "author": {"@type": "Person", "name": "SirAeghann"}
    }
    """


def test_literotica_transformer_extracts_page_text_and_heading() -> None:
    html = f"""
    <html><body>
    <script type="application/ld+json">{_article_ld_json()}</script>
    pageText:"It all started with Selene."
    </body></html>
    """

    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(html)  # type: ignore[attr-defined]

    assert markdown.lstrip().startswith("# Harem House - Selene Pt. 01")
    assert "It all started with Selene." in markdown


def test_literotica_transformer_combines_paginated_pages() -> None:
    page_one = f"""
    <html><body>
    <script type="application/ld+json">{_article_ld_json()}</script>
    pageText:"It all started with Selene."
    </body></html>
    """
    page_two = """
    <html><body>
    pageText:"\\"You mean like calling me names?\\""
    </body></html>
    """
    combined = f"<!-- page1 -->{page_one}<!-- page2 -->{page_two}"

    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(combined)  # type: ignore[attr-defined]

    assert "It all started with Selene." in markdown
    assert '"You mean like calling me names?"' in markdown
    # Ensure both pages contributed content (we expect more than one break)
    assert markdown.count("\n\n") >= 2


def test_literotica_transformer_converts_tilde_fences_to_hr() -> None:
    raw = """
    <html><body>
    <script type="application/ld+json">{
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "Fence Test"
    }</script>
    pageText:"First line.\\n\\n~~~\\n\\nSecond line."
    </body></html>
    """
    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(raw)  # type: ignore[attr-defined]

    assert "# Fence Test" in markdown
    assert "***" in markdown
    assert "~~~" not in markdown
