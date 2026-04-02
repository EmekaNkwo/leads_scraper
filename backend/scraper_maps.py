from __future__ import annotations

import re
import time
from datetime import datetime
from urllib.parse import quote_plus

from scraper_models import LeadRecord

try:
    from playwright.sync_api import Page, TimeoutError, sync_playwright
except ModuleNotFoundError:
    Page = object  # type: ignore[assignment]
    TimeoutError = Exception  # type: ignore[assignment]
    sync_playwright = None


EMAIL_REGEX = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")


def _safe_text(locator: object, timeout_ms: int = 1000) -> str:
    try:
        value = locator.first.text_content(timeout=timeout_ms) or ""
        return value.strip()
    except Exception:
        return ""


def _extract_phone(text: str) -> str:
    match = re.search(r"(\+?\d[\d\-\s\(\)]{6,}\d)", text)
    return match.group(1).strip() if match else "N/A"


def _extract_owner_name(text: str) -> str:
    match = re.search(r"(?:owner|founder|director|manager)\s*[:\-]\s*([^\n|]+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else "N/A"


def _open_maps_search(page: Page, query: str) -> None:
    page.goto(
        f"https://www.google.com/maps/search/{quote_plus(query)}",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    for selector in (
        "button:has-text('Accept all')",
        "button:has-text('I agree')",
        "button:has-text('Accept')",
    ):
        button = page.locator(selector).first
        if button.count() > 0:
            button.click(timeout=5_000)
            page.wait_for_timeout(1_000)
            break
    page.wait_for_selector("div[role='feed'], div.Nv2PK, div[role='article']", timeout=45_000)


def _scroll_once(page: Page) -> tuple[int, int]:
    """Perform a single scroll and return (before_count, after_count)."""
    feed = page.locator("div[role='feed']").first
    has_feed = feed.count() > 0
    before = page.locator("div.Nv2PK, div[role='article']").count()
    if has_feed:
        feed.evaluate("(node) => node.scrollBy(0, node.scrollHeight)")
    else:
        page.mouse.wheel(0, 3000)
    page.wait_for_timeout(1500)
    after = page.locator("div.Nv2PK, div[role='article']").count()
    return before, after


def _scroll_until(page: Page, max_scrolls: int, target: int) -> None:
    """Scroll until target card count is visible or max_scrolls exhausted."""
    stale_runs = 0
    scrolls_used = 0
    while scrolls_used < max_scrolls and stale_runs < 3:
        current = page.locator("div.Nv2PK, div[role='article']").count()
        if current >= target:
            break
        before, after = _scroll_once(page)
        scrolls_used += 1
        if after <= before:
            stale_runs += 1
            page.wait_for_timeout(800)
        else:
            stale_runs = 0


def _extract_details_from_panel(page: Page) -> tuple[str, str, str, str, str, str, list[str]]:
    panel = page.locator("div[role='main']").first
    panel_text = _safe_text(panel, timeout_ms=2000)
    address = _safe_text(
        page.locator("button[data-item-id='address'] .Io6YTe, button[data-item-id='address'] .fontBodyMedium")
    ) or "N/A"
    phone = _safe_text(
        page.locator(
            "button[data-item-id^='phone:tel:'] .Io6YTe, "
            "button[data-item-id^='phone:tel:'] .fontBodyMedium"
        )
    ) or _extract_phone(panel_text)
    email_match = EMAIL_REGEX.search(panel_text)
    email = email_match.group(0) if email_match else "N/A"
    owner_name = _extract_owner_name(panel_text)
    try:
        website = page.locator("a[data-item-id='authority']").first.get_attribute("href", timeout=1000) or "N/A"
    except Exception:
        website = "N/A"
    category = _safe_text(page.locator("button[jsaction*='pane.rating.category'] .DkEaL"), timeout_ms=500)
    if not category:
        category = "N/A"

    social_links: list[str] = []
    for href in page.locator("a[href*='instagram.com'],a[href*='facebook.com'],a[href*='linkedin.com']").all():
        try:
            link = href.get_attribute("href")
        except Exception:
            link = None
        if link:
            social_links.append(link)
    return phone, address, email, owner_name, website, category, list(dict.fromkeys(social_links))


def scrape_query(
    query: str,
    max_results: int,
    max_scrolls: int,
    max_runtime_seconds: int | None,
    headless: bool = True,
) -> list[LeadRecord]:
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed. Run pip install -r requirements.txt then playwright install.")

    SECONDS_PER_LEAD = 10
    MIN_TIMEOUT = 120
    MAX_TIMEOUT = 1800
    auto_timeout = min(MAX_TIMEOUT, max(MIN_TIMEOUT, max_results * SECONDS_PER_LEAD))
    effective_timeout = max_runtime_seconds if max_runtime_seconds else auto_timeout

    started = time.time()
    results: list[LeadRecord] = []
    seen: set[str] = set()
    scrolls_remaining = max_scrolls
    processed_idx = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            _open_maps_search(page, query)

            while len(results) < max_results:
                if time.time() - started >= effective_timeout:
                    break

                _scroll_until(page, scrolls_remaining, max_results + 5)

                cards = page.locator("div.Nv2PK, div[role='article']")
                total_visible = cards.count()

                if processed_idx >= total_visible:
                    break

                made_progress = False
                while processed_idx < total_visible:
                    if time.time() - started >= effective_timeout:
                        break
                    if len(results) >= max_results:
                        break

                    card = cards.nth(processed_idx)
                    processed_idx += 1
                    made_progress = True

                    name = ""
                    try:
                        name = (card.locator("a.hfpxzc").first.get_attribute("aria-label", timeout=1000) or "").strip()
                    except Exception:
                        pass
                    if not name:
                        name = _safe_text(card.locator("div.qBF1Pd, div.fontHeadlineSmall, h3"), timeout_ms=1000)
                    if not name:
                        continue

                    try:
                        card.locator("a.hfpxzc").first.click(timeout=1500)
                        page.wait_for_timeout(600)
                    except Exception:
                        pass

                    phone, address, email, owner_name, website, category, social_links = _extract_details_from_panel(page)
                    phone_digits = re.sub(r"\D+", "", phone)
                    key = f"{name.lower()}|{address.lower()}|{phone_digits}"
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(
                        LeadRecord(
                            query=query,
                            name=name,
                            phone=phone or "N/A",
                            address=address or "N/A",
                            email=email or "N/A",
                            owner_name=owner_name or "N/A",
                            website=website or "N/A",
                            category=category or "N/A",
                            social_links=social_links,
                            scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        )
                    )

                if not made_progress or len(results) >= max_results:
                    break

                scrolls_remaining = max(scrolls_remaining - 2, 2)
        finally:
            browser.close()
    return results

