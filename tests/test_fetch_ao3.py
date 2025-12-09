from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZipFile

import pytest

from storyscraper.fetch import run_fetch_list_phase, run_fetch_phase
from storyscraper.options import StoryScraperOptions


@pytest.fixture()
def ao3_options() -> StoryScraperOptions:
    return StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="ao3_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://archiveofourown.org/works/12345",
        chosen_name="Fallback",
        chosen_slug="fallback",
    )


def _sample_html() -> str:
    return """
    <html>
        <body>
            <h2 class="title">Kyoshi Rising</h2>
            <a rel="author">Crystal Scherer</a>
            <li class="download">
                <a href="/downloads/123/Kyoshi_Rising.epub?updated_at=999">EPUB</a>
            </li>
        </body>
    </html>
    """


def _build_epub() -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "<rootfiles>"
            '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles>"
            "</container>",
        )
        archive.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?>'
            '<package xmlns="http://www.idpf.org/2007/opf">'
            "<manifest>"
            '<item id="chap1" href="text/chapter1.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="chap2" href="text/chapter2.xhtml" media-type="application/xhtml+xml"/>'
            "</manifest>"
            "<spine>"
            '<itemref idref="chap1"/>'
            '<itemref idref="chap2"/>'
            "</spine>"
            "</package>",
        )
        archive.writestr(
            "OEBPS/text/chapter1.xhtml",
            "<html><body><p>Chapter one content.</p></body></html>",
        )
        archive.writestr(
            "OEBPS/text/chapter2.xhtml",
            "<html><body><p>Chapter two content.</p></body></html>",
        )
    return buffer.getvalue()


def test_ao3_list_phase_locates_epub(monkeypatch, tmp_path: Path, ao3_options):
    monkeypatch.setattr(
        "storyscraper.fetchers.ao3_fetcher.Fetcher._fetch_text",
        lambda self, url: _sample_html(),
    )

    urls = run_fetch_list_phase(ao3_options, stories_root=tmp_path)

    assert urls == [
        "https://archiveofourown.org/downloads/123/Kyoshi_Rising.epub?updated_at=999"
    ]

    assert ao3_options.effective_name() == "Kyoshi Rising"
    assert ao3_options.effective_author() == "Crystal Scherer"
    assert ao3_options.effective_slug() == "kyoshi-rising"


def test_ao3_fetch_phase_extracts_epub(monkeypatch, tmp_path: Path, ao3_options):
    monkeypatch.setattr(
        "storyscraper.fetchers.ao3_fetcher.Fetcher._fetch_text",
        lambda self, url: _sample_html(),
    )
    run_fetch_list_phase(ao3_options, stories_root=tmp_path)

    fetch_calls = {"count": 0}

    monkeypatch.setattr(
        "storyscraper.fetchers.ao3_fetcher.Fetcher._fetch_bytes",
        lambda self, url: fetch_calls.__setitem__("count", fetch_calls["count"] + 1)
        or _build_epub(),
    )

    files = run_fetch_phase(ao3_options, stories_root=tmp_path)

    assert [path.name for path in files] == [
        "kyoshi-rising-001.html",
        "kyoshi-rising-002.html",
    ]
    assert files[0].read_text(encoding="utf-8").strip().startswith("<html>")
    assert (tmp_path / "kyoshi-rising" / "kyoshi-rising.epub").exists()
    assert fetch_calls["count"] == 1

    # Second run should reuse the stored EPUB without re-downloading
    run_fetch_phase(ao3_options, stories_root=tmp_path)
    assert fetch_calls["count"] == 1
