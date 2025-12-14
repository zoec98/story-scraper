from __future__ import annotations

import pytest

import json

from storyscraper.fetch import run_fetch_list_phase
from storyscraper.options import StoryScraperOptions


def _collection_api_response(next_link: str | None = None) -> dict:
    return {
        "data": {
            "id": "1374355",
            "type": "collection",
            "attributes": {
                "post_ids": [1, 2],
            },
        },
        "links": {"next": next_link} if next_link else {},
    }


def _collection_api_response_second_page() -> dict:
    return {
        "data": {
            "id": "1374355",
            "type": "collection",
            "attributes": {
                "post_ids": [3],
            },
        },
        "links": {},
    }


def _next_data_html(title: str, author: str) -> str:
    payload = {
        "props": {
            "pageProps": {
                "bootstrapEnvelope": {
                    "pageBootstrap": {
                        "post": {
                            "included": [
                                {"type": "collection", "attributes": {"title": title}},
                                {"type": "campaign", "attributes": {"name": author}},
                            ]
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


@pytest.fixture()
def patreon_options() -> StoryScraperOptions:
    return StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="patreon_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://www.patreon.com/collection/1374355?view=expanded",
        author=None,
        chosen_author=None,
        chosen_name=None,
        chosen_slug=None,
    )


def test_patreon_fetcher_collects_paginated_posts(
    monkeypatch, tmp_path, patreon_options: StoryScraperOptions
) -> None:
    html = """
    <html><head>
    <script type="application/ld+json">{
      "@context": "http://schema.org",
      "@type": "Collection",
      "name": "Harem House Chapters",
      "author": {"@type": "Person", "name": "S. E. Aeghann"}
    }</script>
    </head><body></body></html>
    """

    responses = [
        _collection_api_response(
            "https://www.patreon.com/api/collection/1374355?page=2"
        ),
        _collection_api_response_second_page(),
    ]

    def fake_fetch_json(url: str) -> dict:
        return responses.pop(0)

    monkeypatch.setattr(
        "storyscraper.fetchers.patreon_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )
    monkeypatch.setattr(
        "storyscraper.fetchers.patreon_fetcher.Fetcher._fetch_json",
        lambda self, url: fake_fetch_json(url),
    )

    urls = run_fetch_list_phase(patreon_options, stories_root=tmp_path)

    assert urls == [
        "https://www.patreon.com/posts/1",
        "https://www.patreon.com/posts/2",
        "https://www.patreon.com/posts/3",
    ]
    assert patreon_options.effective_name() == "Harem House Chapters"
    assert patreon_options.effective_slug() == "harem-house-chapters"
    assert patreon_options.effective_author() == "S. E. Aeghann"


def test_patreon_fetcher_reads_metadata_from_next_data(
    monkeypatch, tmp_path, patreon_options: StoryScraperOptions
) -> None:
    html = _next_data_html("Harem House Chapters", "S. E. Aeghann")
    responses = [
        _collection_api_response(
            "https://www.patreon.com/api/collection/1374355?page=2"
        ),
        _collection_api_response_second_page(),
    ]

    def fake_fetch_json(url: str) -> dict:
        return responses.pop(0)

    monkeypatch.setattr(
        "storyscraper.fetchers.patreon_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )
    monkeypatch.setattr(
        "storyscraper.fetchers.patreon_fetcher.Fetcher._fetch_json",
        lambda self, url: fake_fetch_json(url),
    )

    run_fetch_list_phase(patreon_options, stories_root=tmp_path)

    assert patreon_options.effective_name() == "Harem House Chapters"
    assert patreon_options.effective_slug() == "harem-house-chapters"
    assert patreon_options.effective_author() == "S. E. Aeghann"
