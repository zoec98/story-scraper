import os
from pathlib import Path

import pytest

from storyscraper.fetch import run_fetch_list_phase, run_fetch_phase
from storyscraper.fetchers.mcstories_fetcher import Fetcher as McstoriesFetcher
from storyscraper.options import StoryScraperOptions


@pytest.fixture()
def options() -> StoryScraperOptions:
    return StoryScraperOptions(
        name="Silver Leash",
        slug="silver-leash",
        fetch_agent="auto",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://mcstories.com/SilverLeash/index.html",
        author="Author",
        chosen_author="Author",
        chosen_name="Silver Leash",
        chosen_slug="silver-leash",
    )


@pytest.fixture()
def options_trailing_slash() -> StoryScraperOptions:
    return StoryScraperOptions(
        name="Silver Leash",
        slug="silver-leash",
        fetch_agent="auto",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://mcstories.com/SilverLeash/",
        author="Author",
        chosen_author="Author",
        chosen_name="Silver Leash",
        chosen_slug="silver-leash",
    )


def test_run_fetch_list_phase_auto(
    monkeypatch, tmp_path: Path, options: StoryScraperOptions
) -> None:
    html = """
    <html>
        <body>
            <a href="chapter01.html">1</a>
            <a href="/SilverLeash/chapter02.html">2</a>
            <a href="https://mcstories.com/SilverLeash/bonus.html">bonus</a>
            <a href="https://mcstories.com/OtherStory/chapter03.html">skip</a>
            <a href="https://example.com/outside.html">skip</a>
        </body>
    </html>
    """

    def fake_fetch(self, url: str) -> str:
        return html

    monkeypatch.setattr(
        "storyscraper.fetchers.auto.Fetcher._fetch_text",
        fake_fetch,
    )

    urls = run_fetch_list_phase(options, stories_root=tmp_path)

    expected = [
        "https://mcstories.com/SilverLeash/chapter01.html",
        "https://mcstories.com/SilverLeash/chapter02.html",
        "https://mcstories.com/SilverLeash/bonus.html",
    ]

    assert urls == expected

    download_file = tmp_path / "silver-leash" / "download_urls.txt"
    assert download_file.read_text(encoding="utf-8").splitlines() == expected
    doit = tmp_path / "silver-leash" / "doit"
    assert doit.exists()
    doit_text = doit.read_text(encoding="utf-8").splitlines()
    assert doit_text[0] == "#! /usr/bin/env bash"
    assert "storyscraper" in doit_text[1]
    assert options.download_url in doit_text[1]
    assert os.access(doit, os.X_OK)


def test_run_fetch_list_phase_auto_creates_story_directory(
    monkeypatch, tmp_path: Path, options: StoryScraperOptions
) -> None:
    monkeypatch.setattr(
        "storyscraper.fetchers.auto.Fetcher._fetch_text",
        lambda self, url: "<html></html>",
    )

    run_fetch_list_phase(options, stories_root=tmp_path)

    assert (tmp_path / "silver-leash").exists()


def test_run_fetch_list_phase_auto_trailing_slash(
    monkeypatch, tmp_path: Path, options_trailing_slash: StoryScraperOptions
) -> None:
    html = """
    <html>
        <body>
            <a href="chapter01.html">1</a>
        </body>
    </html>
    """
    monkeypatch.setattr(
        "storyscraper.fetchers.auto.Fetcher._fetch_text",
        lambda self, url: html,
    )

    urls = run_fetch_list_phase(options_trailing_slash, stories_root=tmp_path)

    assert urls == ["https://mcstories.com/SilverLeash/chapter01.html"]


def test_run_fetch_list_phase_from_file(
    monkeypatch, tmp_path: Path, options: StoryScraperOptions
) -> None:
    url_file = tmp_path / "urls.txt"
    urls = [
        "https://example.com/one",
        "https://example.com/two",
    ]
    url_file.write_text("\n".join(urls) + "\n", encoding="utf-8")

    options.from_file = str(url_file)
    options.download_url = urls[0]

    monkeypatch.setattr(
        "storyscraper.fetch.load_fetcher",
        lambda *_args, **_kwargs: pytest.fail("load_fetcher should not be called"),
    )

    listed = run_fetch_list_phase(options, stories_root=tmp_path)

    assert listed == urls
    download_file = tmp_path / "silver-leash" / "download_urls.txt"
    assert download_file.read_text(encoding="utf-8").splitlines() == urls


def _write_download_list(path: Path, urls: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(urls), encoding="utf-8")


def test_run_fetch_phase_downloads_missing_chapters(
    monkeypatch, tmp_path: Path, options: StoryScraperOptions
) -> None:
    story_dir = tmp_path / options.slug
    download_list = story_dir / "download_urls.txt"
    urls = [
        "https://example.com/story/1.html",
        "https://example.com/story/2.html",
    ]
    _write_download_list(download_list, urls)

    payloads = {
        urls[0]: b"<html>chapter1</html>",
        urls[1]: b"<html>chapter2</html>",
    }

    monkeypatch.setattr(
        "storyscraper.fetchers.auto.Fetcher._fetch_bytes",
        lambda self, url: payloads[url],
    )

    files = run_fetch_phase(options, stories_root=tmp_path)

    assert [file.name for file in files] == [
        "silver-leash-001.html",
        "silver-leash-002.html",
    ]
    assert (story_dir / "html" / "silver-leash-001.html").read_bytes() == payloads[
        urls[0]
    ]
    assert (story_dir / "html" / "silver-leash-002.html").read_bytes() == payloads[
        urls[1]
    ]


def test_run_fetch_phase_skips_existing_files_when_not_forced(
    monkeypatch, tmp_path: Path, options: StoryScraperOptions
) -> None:
    story_dir = tmp_path / options.slug
    download_list = story_dir / "download_urls.txt"
    urls = [
        "https://example.com/story/1.html",
        "https://example.com/story/2.html",
    ]
    _write_download_list(download_list, urls)
    html_dir = story_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    existing_file = html_dir / "silver-leash-002.html"
    existing_file.write_text("old", encoding="utf-8")

    fetched = []

    def fake_fetch_bytes(self, url: str) -> bytes:
        fetched.append(url)
        return f"<html>{url}</html>".encode("utf-8")

    monkeypatch.setattr(
        "storyscraper.fetchers.auto.Fetcher._fetch_bytes",
        fake_fetch_bytes,
    )

    files = run_fetch_phase(options, stories_root=tmp_path)

    assert fetched == [urls[0]]
    assert [file.name for file in files] == ["silver-leash-001.html"]
    assert existing_file.read_text(encoding="utf-8") == "old"


def test_run_fetch_phase_respects_force_fetch(
    monkeypatch, tmp_path: Path, options: StoryScraperOptions
) -> None:
    story_dir = tmp_path / options.slug
    download_list = story_dir / "download_urls.txt"
    urls = ["https://example.com/story/1.html"]
    _write_download_list(download_list, urls)
    html_dir = story_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    destination = html_dir / "silver-leash-001.html"
    destination.write_text("old", encoding="utf-8")

    monkeypatch.setattr(
        "storyscraper.fetchers.auto.Fetcher._fetch_bytes",
        lambda self, url: b"new",
    )

    files = run_fetch_phase(options, stories_root=tmp_path, force_fetch=True)

    assert [file.name for file in files] == ["silver-leash-001.html"]
    assert destination.read_text(encoding="utf-8") == "new"


def test_run_fetch_phase_logs_failures(
    monkeypatch, tmp_path: Path, options: StoryScraperOptions
) -> None:
    story_dir = tmp_path / options.slug
    download_list = story_dir / "download_urls.txt"
    urls = [
        "https://example.com/story/1.html",
        "https://example.com/story/2.html",
    ]
    _write_download_list(download_list, urls)

    def fake_fetch_bytes(self, url: str) -> bytes:
        if url.endswith("2.html"):
            raise ValueError("boom")
        return b"ok"

    monkeypatch.setattr(
        "storyscraper.fetchers.auto.Fetcher._fetch_bytes",
        fake_fetch_bytes,
    )

    run_fetch_phase(options, stories_root=tmp_path)

    log_file = story_dir / "fetch.log"
    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8")
    assert "ERROR https://example.com/story/2.html" in contents


def test_mcstories_postprocess_infers_title_and_slug(
    monkeypatch, tmp_path: Path, options: StoryScraperOptions
) -> None:
    html = """
    <html>
        <body>
            <h3 class="title">
                The Silver <em>Leash</em>
            </h3>
            <h3 class="byline">by Example Author</h3>
            <a href="chapter01.html">1</a>
        </body>
    </html>
    """

    monkeypatch.setattr(
        "storyscraper.fetchers.mcstories_fetcher.AutoFetcher._fetch_text",
        lambda self, url: html,
    )

    fetcher = McstoriesFetcher()
    opts = StoryScraperOptions(
        name=None,
        slug=None,
        fetch_agent="mcstories_fetcher",
        transform_agent="auto",
        packaging_agent="auto",
        download_url="https://mcstories.com/SilverLeash/index.html",
        chosen_name="Index",
        chosen_slug="index",
    )
    urls = fetcher.list_phase(opts, stories_root=tmp_path)

    assert urls == ["https://mcstories.com/SilverLeash/chapter01.html"]

    download_file = tmp_path / "the-silver-leash" / "download_urls.txt"
    assert download_file.exists()
    assert opts.effective_name() == "The Silver Leash"
    assert opts.effective_slug() == "the-silver-leash"
    assert opts.effective_author() == "Example Author"
