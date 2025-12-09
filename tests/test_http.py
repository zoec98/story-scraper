from __future__ import annotations

from http import cookiejar

from storyscraper import http


class _DummyResponse:
    def __init__(self) -> None:
        self.content = b"payload"

    def raise_for_status(self) -> None:
        pass


class _DummySession:
    def __init__(self, response: _DummyResponse | None = None) -> None:
        self.response = response or _DummyResponse()
        self.last_headers = None
        self.cookies = cookiejar.CookieJar()

    def request(self, method, url, headers, timeout, **kwargs):
        self.last_headers = headers
        return self.response


def test_request_sets_default_user_agent(monkeypatch) -> None:
    response = _DummyResponse()
    session = _DummySession(response)
    monkeypatch.setattr(http, "_SESSION", session)

    result = http.request("GET", "https://example.com", delay=False)

    assert result is response
    assert session.last_headers["User-Agent"].startswith("Mozilla/5.0 (Macintosh")


def test_request_merges_headers(monkeypatch) -> None:
    session = _DummySession()
    monkeypatch.setattr(http, "_SESSION", session)

    http.request(
        "GET",
        "https://example.com",
        headers={"Accept": "text/html"},
        delay=False,
    )

    assert session.last_headers["Accept"] == "text/html"
    assert session.last_headers["User-Agent"].startswith("Mozilla/5.0 (Macintosh")


def test_request_sleeps_with_jitter(monkeypatch) -> None:
    calls = []

    def fake_sleep() -> None:
        calls.append(True)

    monkeypatch.setattr(http, "_sleep_with_jitter", fake_sleep)
    session = _DummySession()
    monkeypatch.setattr(http, "_SESSION", session)

    http.request("GET", "https://example.com")

    assert calls == [True]


def test_fetch_bytes_returns_content(monkeypatch) -> None:
    response = _DummyResponse()
    session = _DummySession(response)
    monkeypatch.setattr(http, "_SESSION", session)

    data = http.fetch_bytes("https://example.com", delay=False)

    assert data == response.content


def test_configure_session_loads_cookies(monkeypatch) -> None:
    dummy_session = _DummySession()

    monkeypatch.setattr(http.requests, "Session", lambda: dummy_session)

    jar = cookiejar.CookieJar()
    cookie = cookiejar.Cookie(
        version=0,
        name="session",
        value="abc",
        port=None,
        port_specified=False,
        domain=".example.com",
        domain_specified=True,
        domain_initial_dot=True,
        path="/",
        path_specified=True,
        secure=False,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )
    jar.set_cookie(cookie)

    http.configure_session(cookies=jar)

    data = http.fetch_bytes("https://example.com", delay=False)

    assert data == b"payload"
    assert any(cookie.name == "session" for cookie in dummy_session.cookies)
    assert dummy_session.last_headers["User-Agent"].startswith("Mozilla/5.0")
