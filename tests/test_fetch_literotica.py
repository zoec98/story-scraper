from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from storyscraper.fetch import run_fetch_list_phase, run_fetch_phase
from storyscraper.options import StoryScraperOptions


def _article_ld_json(series_url: str | None = None) -> str:
    series_part = (
        f',"isPartOf": {{"@type": "CreativeWorkSeries","name": "Harem House - Selene","url": "{series_url}"}}'
        if series_url
        else ""
    )
    return (
        "{"
        '"@context": "https://schema.org",'
        '"@type": "Article",'
        '"headline": "Harem House - Selene Pt. 01",'
        '"author": {"@type": "Person", "name": "SirAeghann"}'
        f"{series_part}"
        "}"
    )


def _chapter_page_bytes(body_text: str, page: int) -> bytes:
    ld_json = _article_ld_json(
        "https://www.literotica.com/series/se/238024799" if page == 1 else None
    )
    html = f"""
    <html><body>
    <script type="application/ld+json">{ld_json}</script>
    pageText:"{body_text.replace('"', '\\"')}"
    </body></html>
    """
    return html.encode("utf-8")


@pytest.fixture()
def literotica_options() -> StoryScraperOptions:
    return StoryScraperOptions(
        name="Harem House",
        slug="harem-house",
        fetch_agent="literotica_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://www.literotica.com/series/se/238024799",
        author="Author",
        chosen_author="Author",
        chosen_name="Harem House",
        chosen_slug="harem-house",
    )


def test_literotica_series_listing_updates_metadata(
    monkeypatch, tmp_path: Path, literotica_options: StoryScraperOptions
) -> None:
    state_json = r'{"series":{"works":[{"url":"harem-house-selene-pt-01"},{"url":"harem-house-selene-pt-02"}],"data":{"title":"Harem House - Selene","user":{"username":"SirAeghann"}}}}'
    html = f"<html><body><script>var onInteractive=[],prefix='/series/',state='{state_json}'</script></body></html>"
    options = literotica_options
    options.name = None
    options.slug = None
    options.author = None
    options.chosen_name = None
    options.chosen_slug = None
    options.chosen_author = None

    monkeypatch.setattr(
        "storyscraper.fetchers.literotica_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    urls = run_fetch_list_phase(options, stories_root=tmp_path)

    assert len(urls) == 2
    assert urls[0] == "https://www.literotica.com/s/harem-house-selene-pt-01"
    assert urls[-1] == "https://www.literotica.com/s/harem-house-selene-pt-02"
    assert options.effective_name() == "Harem House - Selene"
    assert options.effective_slug() == "harem-house-selene"
    assert options.effective_author() == "SirAeghann"


def test_literotica_single_chapter_listing_warns_about_series(
    monkeypatch, tmp_path: Path, literotica_options: StoryScraperOptions
) -> None:
    html = f'<html><body><script type="application/ld+json">{_article_ld_json("https://www.literotica.com/series/se/238024799")}</script></body></html>'
    options = literotica_options
    options.download_url = (
        "https://www.literotica.com/s/harem-house-selene-pt-01?page=2"
    )
    options.slug = None
    options.chosen_slug = None
    options.name = None
    options.chosen_name = None
    options.author = None
    options.chosen_author = None

    monkeypatch.setattr(
        "storyscraper.fetchers.literotica_fetcher.Fetcher._fetch_text",
        lambda self, url: html,
    )

    with pytest.warns(UserWarning, match="Harem House - Selene"):
        urls = run_fetch_list_phase(options, stories_root=tmp_path)

    assert urls == ["https://www.literotica.com/s/harem-house-selene-pt-01"]
    assert options.effective_name() == "Harem House - Selene Pt. 01"
    assert options.effective_slug() == "harem-house-selene-pt-01"
    assert options.effective_author() == "SirAeghann"


def test_literotica_fetch_phase_combines_paginated_pages(
    monkeypatch, tmp_path: Path, literotica_options: StoryScraperOptions
) -> None:
    story_dir = tmp_path / literotica_options.effective_slug()
    download_list = story_dir / "download_urls.txt"
    download_list.parent.mkdir(parents=True, exist_ok=True)
    canonical_url = "https://www.literotica.com/s/harem-house-selene-pt-01"
    download_list.write_text(f"{canonical_url}\n", encoding="utf-8")

    page_one = _chapter_page_bytes("It all started with Selene.", page=1)
    page_two = _chapter_page_bytes('"You mean like calling me names?"', page=2)
    payloads = {
        canonical_url: page_one,
        f"{canonical_url}?page=2": page_two,
    }

    def fake_fetch_bytes(self, url: str) -> bytes:
        if url in payloads:
            return payloads[url]
        response = SimpleNamespace(status_code=404)
        raise requests.HTTPError("Not Found", response=response)

    monkeypatch.setattr(
        "storyscraper.fetchers.literotica_fetcher.Fetcher._fetch_bytes",
        fake_fetch_bytes,
    )

    files = run_fetch_phase(literotica_options, stories_root=tmp_path)

    assert [file.name for file in files] == ["harem-house-001.html"]
    combined = files[0].read_text(encoding="utf-8")
    assert "<!-- Literotica page 1" in combined
    assert "<!-- Literotica page 2" in combined
    assert "It all started with Selene." in combined
    assert '\\"You mean like calling me names?\\"' in combined
