"""HTTP helpers for StoryScraper."""

from __future__ import annotations

import random
import time
from http.cookiejar import CookieJar
from typing import Any, Mapping

import requests

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:145.0) Gecko/20100101 Firefox/145.0"
_DEFAULT_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    ## Do not offer compression unless we can decompress things (which we can't right now)
    #    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Sec-GPC": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Connection": "keep-alive",
    "Priority": "u=0, i",
}
_DEFAULT_TIMEOUT = 30.0
_MIN_DELAY_SECONDS = 0.2
_MAX_DELAY_SECONDS = 1.2
_SESSION = requests.Session()


def configure_session(*, cookies: CookieJar | None = None) -> None:
    """Configure the default HTTP session."""

    global _SESSION
    _SESSION = requests.Session()
    if hasattr(_SESSION, "headers"):
        _SESSION.headers.update(_DEFAULT_HEADERS)
    if cookies is not None:
        for cookie in cookies:
            _SESSION.cookies.set_cookie(cookie)


def request(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    session: requests.Session | None = None,
    timeout: float | tuple[float, float] | None = _DEFAULT_TIMEOUT,
    delay: bool = True,
    **kwargs: Any,
) -> requests.Response:
    """Perform an HTTP request via requests with our defaults."""

    if delay:
        _sleep_with_jitter()

    final_headers = dict(_DEFAULT_HEADERS)
    if headers:
        final_headers.update(headers)

    requester_session = session or _SESSION
    requester = requester_session.request
    response = requester(
        method,
        url,
        headers=final_headers,
        timeout=timeout,
        **kwargs,
    )
    response.raise_for_status()
    return response


def get(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    session: requests.Session | None = None,
    timeout: float | tuple[float, float] | None = _DEFAULT_TIMEOUT,
    delay: bool = True,
    **kwargs: Any,
) -> requests.Response:
    """Convenience wrapper for GET requests."""

    return request(
        "GET",
        url,
        headers=headers,
        session=session,
        timeout=timeout,
        delay=delay,
        **kwargs,
    )


def fetch_bytes(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    session: requests.Session | None = None,
    timeout: float | tuple[float, float] | None = _DEFAULT_TIMEOUT,
    delay: bool = True,
    **kwargs: Any,
) -> bytes:
    """Fetch the content at URL and return the response bytes."""

    response = get(
        url,
        headers=headers,
        session=session,
        timeout=timeout,
        delay=delay,
        **kwargs,
    )
    return response.content


def _sleep_with_jitter() -> None:
    time.sleep(random.uniform(_MIN_DELAY_SECONDS, _MAX_DELAY_SECONDS))


# Initialize session with default headers on import.
configure_session()
