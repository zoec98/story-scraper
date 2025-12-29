from storyscraper.urlclassifier import SiteMatch, classify_url


def test_classify_url_matches_mcstories() -> None:
    url = "https://mcstories.com/MyStory/index.html"

    result = classify_url(url)

    assert isinstance(result, SiteMatch)
    assert result.name == "mcstories"
    assert result.fetch_agent == "mcstories_fetcher"
    assert result.transform_agent == "mcstories_transformer"
    assert result.packaging_agent is None


def test_classify_url_matches_literotica() -> None:
    url = "https://www.literotica.com/s/example-story"

    result = classify_url(url)

    assert isinstance(result, SiteMatch)
    assert result.name == "literotica"
    assert result.fetch_agent == "literotica_fetcher"
    assert result.transform_agent == "literotica_transformer"
    assert result.packaging_agent is None


def test_classify_url_matches_bdsmlibrary() -> None:
    url = "https://www.bdsmlibrary.com/stories/story.php?storyid=123"

    result = classify_url(url)

    assert isinstance(result, SiteMatch)
    assert result.name == "bdsmlibrary"
    assert result.fetch_agent == "bdsmlibrary_fetcher"
    assert result.transform_agent == "bdsmlibrary_transformer"
    assert result.packaging_agent is None


def test_classify_url_matches_eroticstories() -> None:
    url = "https://www.eroticstories.com/my/story.php?id=61794"

    result = classify_url(url)

    assert isinstance(result, SiteMatch)
    assert result.name == "eroticstories"
    assert result.fetch_agent == "eroticstories_fetcher"
    assert result.transform_agent == "eroticstories_transformer"
    assert result.packaging_agent is None


def test_classify_url_matches_inkitt() -> None:
    url = "https://www.inkitt.com/stories/1548300"

    result = classify_url(url)

    assert isinstance(result, SiteMatch)
    assert result.name == "inkitt"
    assert result.fetch_agent == "inkitt_fetcher"
    assert result.transform_agent == "inkitt_transformer"
    assert result.packaging_agent is None


def test_classify_url_matches_patreon_collection() -> None:
    url = "https://www.patreon.com/collection/1374355"

    result = classify_url(url)

    assert isinstance(result, SiteMatch)
    assert result.name == "patreon"
    assert result.fetch_agent == "patreon_fetcher"
    assert result.transform_agent == "patreon_transformer"
    assert result.packaging_agent is None


def test_classify_url_matches_wattpad() -> None:
    url = "https://www.wattpad.com/12345-example"

    result = classify_url(url)

    assert isinstance(result, SiteMatch)
    assert result.name == "wattpad"
    assert result.fetch_agent == "wattpad_fetcher"
    assert result.transform_agent == "wattpad_transformer"
    assert result.packaging_agent is None


def test_classify_url_matches_ao3() -> None:
    url = "https://archiveofourown.org/works/1272487"

    result = classify_url(url)

    assert isinstance(result, SiteMatch)
    assert result.name == "ao3"
    assert result.fetch_agent == "ao3_fetcher"
    assert result.transform_agent == "ao3_transformer"
    assert result.packaging_agent is None


def test_classify_url_matches_fanfiction() -> None:
    url = "https://www.fanfiction.net/s/14308516/2/Title"

    result = classify_url(url)

    assert isinstance(result, SiteMatch)
    assert result.name == "fanfiction"
    assert result.fetch_agent == "fanfiction_fetcher"
    assert result.transform_agent == "fanfiction_transformer"
    assert result.packaging_agent is None


def test_classify_url_returns_none_for_unknown_site() -> None:
    url = "https://unknown-site.example/story"

    result = classify_url(url)

    assert result is None
