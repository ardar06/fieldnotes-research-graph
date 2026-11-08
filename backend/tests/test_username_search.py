import asyncio
from types import SimpleNamespace

import pytest

from app import username_search


def test_username_search_is_bounded_head_only_and_uses_no_proxy(monkeypatch):
    calls = {}

    class FakeClient:
        def __init__(self, **kwargs):
            calls["options"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def head(self, url):
            calls.setdefault("urls", []).append(url)
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(username_search.httpx, "AsyncClient", FakeClient)
    results = asyncio.run(username_search.run_username_checks("safename", ["GitHub"]))

    assert calls["urls"] == ["https://www.github.com/safename"]
    assert calls["options"]["trust_env"] is False
    assert calls["options"]["follow_redirects"] is False
    assert calls["options"]["headers"]["User-Agent"] == username_search.USER_AGENT
    assert "proxies" not in calls["options"]
    assert results == [{
        "site_name": "GitHub",
        "profile_url": "https://www.github.com/safename",
        "status": "candidate",
        "http_status": 200,
    }]


def test_username_check_does_not_send_invalid_site_or_expand_patterns():
    with pytest.raises(ValueError):
        asyncio.run(username_search.run_username_checks("someone{?}", ["GitHub"]))
