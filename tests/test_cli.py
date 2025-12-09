from types import SimpleNamespace

from storyscraper import cli
from storyscraper.cookies import CookieLoadError


def test_configure_http_loads_browser_cookies(monkeypatch):
    class DummyJar:
        def __len__(self) -> int:
            return 2

    jar = DummyJar()

    configured: list[object] = []

    def fake_configure_session(*, cookies):
        configured.append(cookies)

    def fake_extract(browser, logger):
        assert browser == "firefox"
        assert logger is not None
        return jar

    monkeypatch.setattr("storyscraper.http.configure_session", fake_configure_session)
    monkeypatch.setattr(
        "storyscraper.cookies.extract_cookies_from_browser", fake_extract
    )

    log_messages: list[str] = []
    options = SimpleNamespace(cookies_from_browser="firefox")

    cli._configure_http(options, log_messages.append)

    assert configured == [jar]
    assert log_messages[-1] == "Cookies: loaded 2 entries from firefox"


def test_configure_http_logs_cookie_errors(monkeypatch):
    def fake_extract(browser, logger):
        raise CookieLoadError("boom")

    monkeypatch.setattr(
        "storyscraper.cookies.extract_cookies_from_browser", fake_extract
    )

    log_messages: list[str] = []
    options = SimpleNamespace(cookies_from_browser="firefox")

    cli._configure_http(options, log_messages.append)

    assert log_messages[-1].startswith("Cookies: failed to load")


def test_log_warning_records_emits_messages() -> None:
    messages: list[str] = []

    class DummyWarning:
        def __init__(self, message: str) -> None:
            self.message = message

    cli._log_warning_records(
        [DummyWarning("Wattpad: skipped 1 locked chapter")], messages.append
    )

    assert messages == ["Warning: Wattpad: skipped 1 locked chapter"]


def test_main_logs_warnings(monkeypatch):
    messages: list[str] = []

    def fake_build_logger(quiet):
        def _log(msg: str) -> None:
            if not quiet:
                messages.append(msg)

        return _log

    monkeypatch.setattr(cli, "_build_logger", fake_build_logger)
    monkeypatch.setattr(cli, "_configure_http", lambda options, log: None)

    def warn_list(options):
        import warnings

        warnings.warn("List warning")
        return []

    def warn_fetch(options, **kwargs):
        import warnings

        warnings.warn("Fetch warning")
        return []

    def warn_transform(options, **kwargs):
        import warnings

        warnings.warn("Transform warning")
        return []

    monkeypatch.setattr(cli, "run_fetch_list_phase", warn_list)
    monkeypatch.setattr(cli, "run_fetch_phase", warn_fetch)
    monkeypatch.setattr(cli, "run_transform_phase", warn_transform)
    monkeypatch.setattr(cli, "write_makefile", lambda options: None)

    cli.main(["https://example.com/story"])

    assert "Warning: List warning" in messages
    assert "Warning: Fetch warning" in messages
    assert "Warning: Transform warning" in messages


def test_main_suppresses_warning_when_quiet(monkeypatch):
    messages: list[str] = []

    def fake_build_logger(quiet):
        def _log(msg: str) -> None:
            if not quiet:
                messages.append(msg)

        return _log

    monkeypatch.setattr(cli, "_build_logger", fake_build_logger)
    monkeypatch.setattr(cli, "_configure_http", lambda options, log: None)

    def warn_list(options):
        import warnings

        warnings.warn("List warning")
        return []

    def warn_fetch(options, **kwargs):
        import warnings

        warnings.warn("Fetch warning")
        return []

    def warn_transform(options, **kwargs):
        import warnings

        warnings.warn("Transform warning")
        return []

    monkeypatch.setattr(cli, "run_fetch_list_phase", warn_list)
    monkeypatch.setattr(cli, "run_fetch_phase", warn_fetch)
    monkeypatch.setattr(cli, "run_transform_phase", warn_transform)
    monkeypatch.setattr(cli, "write_makefile", lambda options: None)

    cli.main(["--quiet", "https://example.com/story"])

    assert all("Warning:" not in message for message in messages)
