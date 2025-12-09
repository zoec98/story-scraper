import pytest

from storyscraper.options import DEFAULT_AGENT, StoryScraperOptions, parse_cli_args


def test_parse_cli_args_with_all_overrides() -> None:
    url = "https://example.com/story"
    options = parse_cli_args(
        [
            "--name",
            "Custom Story",
            "--slug",
            "custom-story-dir",
            "--fetch-agent",
            "fetcher",
            "--transform-agent",
            "transformer",
            "--packaging-agent",
            "packer",
            url,
        ]
    )

    assert isinstance(options, StoryScraperOptions)
    assert options.name == "Custom Story"
    assert options.slug == "custom-story-dir"
    assert options.effective_name() == "Custom Story"
    assert options.effective_slug() == "custom-story-dir"
    assert options.fetch_agent == "fetcher"
    assert options.transform_agent == "transformer"
    assert options.packaging_agent == "packer"
    assert options.download_url == url
    assert options.site_name is None
    assert options.force_fetch is False
    assert options.verbose is False
    assert options.quiet is False


def test_parse_cli_args_derives_name_and_slug_from_url() -> None:
    url = "https://example.com/fics/the-silver-leash.html"

    options = parse_cli_args([url])

    assert options.name is None
    assert options.slug is None
    assert options.chosen_name == "The Silver Leash"
    assert options.chosen_slug == "the-silver-leash"
    assert options.effective_name() == "The Silver Leash"
    assert options.effective_slug() == "the-silver-leash"
    assert options.fetch_agent == DEFAULT_AGENT
    assert options.transform_agent == DEFAULT_AGENT
    assert options.packaging_agent == DEFAULT_AGENT
    assert options.site_name is None
    assert options.force_fetch is False
    assert options.verbose is False
    assert options.quiet is False


def test_parse_cli_args_allows_slug_override_without_name() -> None:
    url = "https://example.com/story"

    options = parse_cli_args(["--slug", "my-slug", url])

    assert options.name is None
    assert options.slug == "my-slug"
    assert options.chosen_name == "Story"
    assert options.effective_name() == "Story"
    assert options.site_name is None
    assert options.force_fetch is False
    assert options.verbose is False
    assert options.quiet is False


def test_parse_cli_args_handles_root_url_without_path() -> None:
    url = "https://example.com/"

    options = parse_cli_args([url])

    assert options.name is None
    assert options.slug is None
    assert options.chosen_name == "Example"
    assert options.chosen_slug == "example"
    assert options.effective_slug() == "example"
    assert options.site_name is None
    assert options.force_fetch is False
    assert options.verbose is False
    assert options.quiet is False


def test_parse_cli_args_enriches_with_site_specific_defaults() -> None:
    url = "https://mcstories.com/SomeStory/index.html"

    options = parse_cli_args([url])

    assert options.fetch_agent == "mcstories_fetcher"
    assert options.transform_agent == "mcstories_transformer"
    assert options.packaging_agent == DEFAULT_AGENT
    assert options.site_name == "mcstories"
    assert options.force_fetch is False
    assert options.verbose is False
    assert options.quiet is False


def test_parse_cli_args_respects_force_fetch_flag() -> None:
    url = "https://example.com/story"

    options = parse_cli_args(["--force-fetch", url])

    assert options.force_fetch is True
    assert options.verbose is False
    assert options.quiet is False


def test_parse_cli_args_respects_verbose_flag() -> None:
    url = "https://example.com/story"

    options = parse_cli_args(["--verbose", url])

    assert options.verbose is True
    assert options.quiet is False


def test_parse_cli_args_respects_quiet_flag() -> None:
    url = "https://example.com/story"

    options = parse_cli_args(["--quiet", url])

    assert options.quiet is True
    assert options.verbose is False


def test_parse_cli_args_rejects_conflicting_silence_flags() -> None:
    url = "https://example.com/story"

    with pytest.raises(SystemExit):
        parse_cli_args(["--quiet", "--verbose", url])


def test_parse_cli_args_accepts_author_override() -> None:
    url = "https://example.com/story"

    options = parse_cli_args(["--author", "Jane Doe", url])

    assert options.author == "Jane Doe"
    assert options.effective_author() == "Jane Doe"


def test_parse_cli_args_accepts_cookies_option() -> None:
    url = "https://example.com/story"

    options = parse_cli_args(["--cookies-from-browser", "firefox", url])

    assert options.cookies_from_browser == "firefox"
