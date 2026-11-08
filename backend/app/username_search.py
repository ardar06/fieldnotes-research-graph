import asyncio
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx


SITES_FILE = Path(__file__).parent / "resources" / "sherlock_sites.json"
USER_AGENT = "Fieldnotes/0.3 (user-initiated public profile URL check)"
MAX_SITES_PER_SEARCH = 25
MAX_CONCURRENT_REQUESTS = 3


def load_sites() -> dict[str, dict]:
    data = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    return {
        name: details
        for name, details in data.items()
        if isinstance(details, dict)
        and isinstance(details.get("url"), str)
        and details["url"].count("{}") == 1
        and urlsplit(details["url"].replace("{}", "username")).scheme == "https"
        and urlsplit(details["url_main"]).scheme == "https"
    }


def list_sites() -> list[dict[str, str]]:
    return [
        {"name": name, "home_url": details["url_main"]}
        for name, details in sorted(load_sites().items())
    ]


def _site_status(http_status: int, error_codes: int | list[int] | None) -> str:
    unavailable_codes = {error_codes} if isinstance(error_codes, int) else set(error_codes or [])
    if http_status in unavailable_codes or http_status in {404, 410}:
        return "not_found"
    if 200 <= http_status < 400:
        return "candidate"
    return "inconclusive"


async def run_username_checks(username: str, site_names: list[str]) -> list[dict]:
    """Probe selected public profile URLs with bounded HTTPS HEAD requests only."""
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", username):
        raise ValueError("Username must be 1-64 letters, numbers, dots, underscores, or hyphens")
    sites = load_sites()
    if not 1 <= len(site_names) <= MAX_SITES_PER_SEARCH:
        raise ValueError(f"Choose between 1 and {MAX_SITES_PER_SEARCH} sites")
    unknown = [name for name in site_names if name not in sites]
    if unknown:
        raise ValueError("One or more selected sites are not in the supported public-site catalog")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    timeout = httpx.Timeout(5.0, connect=2.0)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    async with httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        async def check(site_name: str) -> dict:
            site = sites[site_name]
            profile_url = site["url"].replace("{}", quote(username, safe=""))
            regex_check = site.get("regex_check")
            if regex_check and re.search(regex_check, username) is None:
                return {"site_name": site_name, "profile_url": profile_url, "status": "unsupported", "http_status": None}
            async with semaphore:
                try:
                    response = await client.head(profile_url)
                    status = _site_status(response.status_code, site.get("error_codes"))
                    return {
                        "site_name": site_name,
                        "profile_url": profile_url,
                        "status": status,
                        "http_status": response.status_code,
                    }
                except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError):
                    return {"site_name": site_name, "profile_url": profile_url, "status": "inconclusive", "http_status": None}
                except httpx.HTTPError:
                    return {"site_name": site_name, "profile_url": profile_url, "status": "inconclusive", "http_status": None}

        return await asyncio.gather(*(check(name) for name in site_names))
