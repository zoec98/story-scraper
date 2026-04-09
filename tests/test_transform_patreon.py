from __future__ import annotations

import json
from pathlib import Path

from storyscraper.options import StoryScraperOptions
from storyscraper.transformers.patreon_transformer import Transformer


def _next_data_html(title: str, body: str) -> str:
    payload = {
        "props": {
            "pageProps": {
                "bootstrapEnvelope": {
                    "pageBootstrap": {
                        "post": {
                            "data": {
                                "attributes": {
                                    "title": title,
                                    "content": f"<div><p>{body}</p><div>In collection footer</div></div>",
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    return f"""
    <html><body>
    <script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>
    </body></html>
    """


def _api_json_payload(title: str, body: str) -> str:
    payload = {
        "data": {
            "type": "post",
            "attributes": {
                "title": title,
                "content": f"<div><p>{body}</p></div>",
            },
        }
    }
    return json.dumps(payload)


def _api_json_rich_payload(title: str, body: str) -> str:
    payload = {
        "data": {
            "type": "post",
            "attributes": {
                "title": title,
                "content": None,
                "content_json_string": json.dumps(
                    {
                        "type": "doc",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": body,
                                    }
                                ],
                            }
                        ],
                    }
                ),
            },
        }
    }
    return json.dumps(payload)


def test_patreon_transformer_extracts_post_content() -> None:
    html = _next_data_html(
        "Harem House Chapter 43",
        "The forest embraces us like a protective mother.",
    )
    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(html)  # type: ignore[attr-defined]

    assert markdown.lstrip().startswith("# Harem House Chapter 43")
    assert "The forest embraces us like a protective mother." in markdown


def test_patreon_transformer_reads_api_json() -> None:
    html = _api_json_payload(
        "Harem House Chapter 44",
        "A second chapter body appears.",
    )
    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(html)  # type: ignore[attr-defined]

    assert markdown.lstrip().startswith("# Harem House Chapter 44")
    assert "A second chapter body appears." in markdown


def test_patreon_transformer_reads_api_json_rich_content() -> None:
    html = _api_json_rich_payload(
        "Harem House Chapter 45",
        "A richer chapter body appears.",
    )
    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(html)  # type: ignore[attr-defined]

    assert markdown.lstrip().startswith("# Harem House Chapter 45")
    assert "A richer chapter body appears." in markdown


def test_patreon_transformer_sanitizes_tilde_fences() -> None:
    html = _next_data_html(
        "Fence Check",
        "First line.<br/>  ~~~  <br/>Second line.",
    )
    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(html)  # type: ignore[attr-defined]

    assert "---" in markdown
    assert "~~~" not in markdown


def test_patreon_transformer_renames_output_by_title(tmp_path: Path) -> None:
    stories_root = tmp_path / "stories"
    slug = "harem-house-chapters"
    html_dir = stories_root / slug / "html"
    html_dir.mkdir(parents=True)

    html = _next_data_html("Blabla Chapter 43 Part 4", "Body text.")
    (html_dir / f"{slug}-001.html").write_text(html, encoding="utf-8")

    options = StoryScraperOptions(
        name="Blabla",
        slug=slug,
        fetch_agent="patreon_fetcher",
        transform_agent="patreon_transformer",
        packaging_agent="auto",
        download_url="https://www.patreon.com/collection/1374355",
        author=None,
        chosen_author=None,
        chosen_name=None,
        chosen_slug=None,
        verbose=False,
        quiet=False,
        cookies_from_browser=None,
    )

    transformer = Transformer()
    outputs = transformer.transform_phase(options, stories_root=stories_root)

    expected = stories_root / slug / "markdown" / "blabla-043-4.md"
    assert expected in outputs
    assert expected.exists()
