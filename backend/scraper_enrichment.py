from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scraper_models import LeadRecord


EMAIL_REGEX = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
OWNER_PATTERNS = (
    re.compile(r"(?:owner|founder|ceo|director|manager)\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})"),
    re.compile(r"(?:owned by|founded by|managed by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})", re.IGNORECASE),
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
PRIORITY_SEGMENTS = ("contact", "about", "team", "staff", "leadership")


def _is_valid_email(email: str) -> bool:
    if not EMAIL_REGEX.fullmatch(email):
        return False
    local, _, domain = email.partition("@")
    return bool(local) and "." in domain


def _candidate_urls(website: str) -> list[str]:
    if not website or website == "N/A":
        return []
    parsed = urlparse(website)
    base = website if parsed.scheme else f"https://{website}"
    seeds = ["", "/contact", "/contact-us", "/about", "/about-us", "/team"]
    return [urljoin(base.rstrip("/") + "/", s.lstrip("/")) for s in seeds]


def _extract_owner(text: str) -> str:
    for pattern in OWNER_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return "N/A"


def enrich_from_websites(leads: list[LeadRecord], max_pages_per_site: int = 4, should_cancel=None) -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    cancelled = False
    for lead in leads:
        if should_cancel and should_cancel():
            cancelled = True
            break
        if lead.website == "N/A":
            continue
        if lead.email != "N/A" and lead.owner_name != "N/A":
            continue

        visited: set[str] = set()
        queue = _candidate_urls(lead.website)
        while queue and len(visited) < max_pages_per_site:
            if should_cancel and should_cancel():
                cancelled = True
                break
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                response = session.get(url, timeout=10)
                if response.status_code >= 400:
                    continue
            except requests.RequestException:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            text = " ".join(soup.stripped_strings)
            if lead.email == "N/A":
                mailto = soup.select_one("a[href^='mailto:']")
                if mailto and mailto.get("href"):
                    candidate = mailto["href"].replace("mailto:", "").strip()
                    if _is_valid_email(candidate):
                        lead.email = candidate
                if lead.email == "N/A":
                    found = EMAIL_REGEX.search(text)
                    if found and _is_valid_email(found.group(0)):
                        lead.email = found.group(0)

            if lead.owner_name == "N/A":
                lead.owner_name = _extract_owner(text)

            for anchor in soup.select("a[href]"):
                href = anchor.get("href") or ""
                full = urljoin(url, href)
                lowered = full.lower()
                if any(segment in lowered for segment in PRIORITY_SEGMENTS):
                    queue.append(full)
                if any(site in lowered for site in ("instagram.com", "facebook.com", "linkedin.com")):
                    lead.social_links.append(full)

            lead.social_links = list(dict.fromkeys(lead.social_links))
            if lead.email != "N/A" and lead.owner_name != "N/A":
                break
        if cancelled:
            break

