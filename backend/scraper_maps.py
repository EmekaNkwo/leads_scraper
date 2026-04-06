from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from scraper_models import LeadRecord
from scraper_utils import NA_VALUE, canonicalize_url, lead_identity_aliases, lead_identity_key, normalize_lead, slugify

try:
    from playwright.sync_api import Page, TimeoutError, sync_playwright
except ModuleNotFoundError:
    Page = object  # type: ignore[assignment]
    TimeoutError = Exception  # type: ignore[assignment]
    sync_playwright = None


EMAIL_REGEX = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
SCROLL_RENDER_WAIT_MS = 2500
STALE_SCROLL_WAIT_MS = 2000
MAX_STALE_SCROLLS = 7
CHECKPOINT_LEAD_INTERVAL = 10
CHECKPOINT_TIME_INTERVAL_SECONDS = 20
DEBUG_CARD_SAMPLE_LIMIT = 3
DEBUG_TEXT_LIMIT = 240


def _safe_text(locator: object, timeout_ms: int = 1000) -> str:
    try:
        value = locator.first.text_content(timeout=timeout_ms) or ""
        return value.strip()
    except Exception:
        return ""


def _truncate(value: str, limit: int = DEBUG_TEXT_LIMIT) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _artifact_dir_from_logger(logger: logging.Logger | None) -> Path | None:
    if logger is None:
        return None
    for handler in logger.handlers:
        base_filename = getattr(handler, "baseFilename", None)
        if base_filename:
            return Path(base_filename).resolve().parent
    return None


def _safe_page_title(page: Page) -> str:
    try:
        return page.title()
    except Exception:
        return "(title unavailable)"


def _capture_card_sample(card: object, reason: str, error: Exception | None = None) -> dict[str, object]:
    sample = {
        "reason": reason,
        "name_hint": _get_card_name(card) or None,
        "card_key_hint": _get_card_key(card) or None,
        "anchor_count": card.locator("a.hfpxzc").count(),
        "href_hint": None,
        "text_excerpt": _truncate(_get_card_fallback_text(card)),
    }
    try:
        sample["href_hint"] = card.locator("a.hfpxzc").first.get_attribute("href", timeout=1000)
    except Exception:
        sample["href_hint"] = None
    if error is not None:
        sample["error"] = str(error)
    return sample


def _dump_zero_collection_diagnostics(
    page: Page,
    query: str,
    logger: logging.Logger | None,
    *,
    end_reason: str,
    max_visible_cards: int,
    scrolls_used: int,
    skip_counts: dict[str, int],
    card_samples: list[dict[str, object]],
) -> None:
    artifact_dir = _artifact_dir_from_logger(logger)
    if artifact_dir is None:
        return

    artifact_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    prefix = artifact_dir / f"scrape_debug_{slugify(query)}_{timestamp}"

    html_path = prefix.with_suffix(".html")
    screenshot_path = prefix.with_suffix(".png")
    summary_path = prefix.with_suffix(".txt")

    try:
        html_path.write_text(page.content(), encoding="utf-8")
    except Exception as exc:
        if logger:
            logger.warning("query=%s debug_artifact_write_failed target=%s error=%s", query, html_path.name, exc)

    try:
        page.screenshot(path=str(screenshot_path), full_page=True, timeout=10_000)
    except Exception as exc:
        if logger:
            logger.warning("query=%s debug_artifact_write_failed target=%s error=%s", query, screenshot_path.name, exc)

    page_title = _safe_page_title(page)
    summary_lines = [
        f"query={query}",
        f"url={page.url}",
        f"title={page_title}",
        f"end_reason={end_reason}",
        f"max_visible_cards={max_visible_cards}",
        f"scrolls_used={scrolls_used}",
        f"skip_counts={skip_counts}",
        "card_samples=",
    ]
    summary_lines.extend(f"- {sample}" for sample in card_samples)
    try:
        summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    except Exception as exc:
        if logger:
            logger.warning("query=%s debug_artifact_write_failed target=%s error=%s", query, summary_path.name, exc)

    if logger:
        logger.warning(
            "query=%s zero_collection_debug end_reason=%s max_visible_cards=%s scrolls_used=%s skip_counts=%s samples=%s html=%s screenshot=%s summary=%s title=%s url=%s",
            query,
            end_reason,
            max_visible_cards,
            scrolls_used,
            skip_counts,
            card_samples,
            html_path.name,
            screenshot_path.name,
            summary_path.name,
            _truncate(page_title, 120),
            page.url,
        )


def _extract_phone(text: str) -> str:
    match = re.search(r"(\+?\d[\d\-\s\(\)]{6,}\d)", text)
    return match.group(1).strip() if match else NA_VALUE


def _extract_owner_name(text: str) -> str:
    match = re.search(r"(?:owner|founder|director|manager)\s*[:\-]\s*([^\n|]+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else NA_VALUE


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


def _get_card_name(card: object) -> str:
    name = ""
    try:
        name = (card.locator("a.hfpxzc").first.get_attribute("aria-label", timeout=1000) or "").strip()
    except Exception:
        pass
    if not name:
        name = _safe_text(card.locator("div.qBF1Pd, div.fontHeadlineSmall, h3"), timeout_ms=1000)
    return name


def _get_card_fallback_text(card: object) -> str:
    try:
        text = (card.first.text_content(timeout=1000) or "").strip()
    except Exception:
        return ""
    return " ".join(text.split())


def _get_card_key(card: object) -> str:
    try:
        href = canonicalize_url(card.locator("a.hfpxzc").first.get_attribute("href", timeout=1000) or "")
    except Exception:
        href = ""
    if href and href != NA_VALUE:
        return f"href:{href}"
    name = _get_card_name(card)
    if name:
        fallback_text = _get_card_fallback_text(card)
        if fallback_text:
            return f"text:{name.casefold()}|{fallback_text.casefold()}"
        return f"name:{name.casefold()}"
    fallback_text = _get_card_fallback_text(card)
    if fallback_text:
        return f"text:{fallback_text.casefold()}"
    return ""


def _count_unseen_visible_cards(page: Page, seen_card_keys: set[str]) -> int:
    cards = page.locator("div.Nv2PK, div[role='article']")
    unseen = 0
    for index in range(cards.count()):
        card_key = _get_card_key(cards.nth(index))
        if card_key and card_key not in seen_card_keys:
            unseen += 1
    return unseen


def _scroll_once(page: Page) -> None:
    """Perform a single scroll and allow Maps time to render the next batch."""
    feed = page.locator("div[role='feed']").first
    has_feed = feed.count() > 0
    if has_feed:
        feed.evaluate("(node) => node.scrollBy(0, node.scrollHeight)")
    else:
        page.mouse.wheel(0, 3000)
    page.wait_for_timeout(SCROLL_RENDER_WAIT_MS)


def _extract_details_from_panel(page: Page) -> tuple[str, str, str, str, str, str, str, list[str]]:
    panel = page.locator("div[role='main']").first
    panel_text = _safe_text(panel, timeout_ms=2000)
    address = _safe_text(
        page.locator("button[data-item-id='address'] .Io6YTe, button[data-item-id='address'] .fontBodyMedium")
    ) or NA_VALUE
    phone = _safe_text(
        page.locator(
            "button[data-item-id^='phone:tel:'] .Io6YTe, "
            "button[data-item-id^='phone:tel:'] .fontBodyMedium"
        )
    ) or _extract_phone(panel_text)
    email_match = EMAIL_REGEX.search(panel_text)
    email = email_match.group(0) if email_match else NA_VALUE
    owner_name = _extract_owner_name(panel_text)
    try:
        website = page.locator("a[data-item-id='authority']").first.get_attribute("href", timeout=1000) or NA_VALUE
    except Exception:
        website = NA_VALUE
    maps_url = canonicalize_url(page.url)
    category = _safe_text(page.locator("button[jsaction*='pane.rating.category'] .DkEaL"), timeout_ms=500)
    if not category:
        category = NA_VALUE

    social_links: list[str] = []
    for href in page.locator("a[href*='instagram.com'],a[href*='facebook.com'],a[href*='linkedin.com']").all():
        try:
            link = href.get_attribute("href")
        except Exception:
            link = None
        if link:
            social_links.append(link)
    return phone, address, email, owner_name, website, maps_url, category, list(dict.fromkeys(social_links))


def scrape_query(
    query: str,
    max_results: int,
    max_scrolls: int,
    max_runtime_seconds: int | None,
    headless: bool = True,
    logger: logging.Logger | None = None,
    seen_lead_keys: set[str] | None = None,
    seen_card_keys: set[str] | None = None,
    checkpoint_callback: Callable[[list[LeadRecord], set[str], set[str]], None] | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> list[LeadRecord]:
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed. Run pip install -r requirements.txt then playwright install.")

    seconds_per_lead = 10
    min_timeout = 120
    max_timeout = 1800
    auto_timeout = min(max_timeout, max(min_timeout, max_results * seconds_per_lead))
    effective_timeout = max_runtime_seconds if max_runtime_seconds else auto_timeout

    started = time.time()
    results: list[LeadRecord] = []
    seen_lead_keys = set(seen_lead_keys or set())
    seen_card_keys = set(seen_card_keys or set())
    stale_scrolls = 0
    scrolls_used = 0
    loop_count = 0
    last_checkpoint_at = started
    last_checkpoint_count = 0
    end_reason = "completed"
    max_visible_cards = 0
    skip_counts = {
        "missing_key": 0,
        "missing_name": 0,
        "click_failed": 0,
        "duplicate": 0,
    }
    card_samples: list[dict[str, object]] = []

    def emit_progress(**payload: object) -> None:
        if progress_callback:
            progress_callback(payload)

    if logger:
        logger.info(
            "query=%s scrape_started target_results=%s max_scrolls=%s timeout_seconds=%s headless=%s resumed_leads=%s resumed_cards=%s",
            query,
            max_results,
            max_scrolls,
            effective_timeout,
            headless,
            len(seen_lead_keys),
            len(seen_card_keys),
        )
    emit_progress(
        query=query,
        phase="scrape_started",
        leads_collected=0,
        leads_target=max_results,
        visible_cards=0,
        scrolls_used=0,
        max_scrolls=max_scrolls,
        stale_scrolls=0,
        message=f"Started scraping '{query}'",
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            if should_cancel and should_cancel():
                end_reason = "cancel_requested"
                return results
            _open_maps_search(page, query)

            while len(results) < max_results:
                loop_count += 1
                if should_cancel and should_cancel():
                    end_reason = "cancel_requested"
                    break
                if time.time() - started >= effective_timeout:
                    end_reason = "runtime_limit"
                    break

                cards = page.locator("div.Nv2PK, div[role='article']")
                total_visible = cards.count()
                max_visible_cards = max(max_visible_cards, total_visible)
                if logger:
                    logger.info(
                        "query=%s pass=%s collected=%s/%s visible_cards=%s scrolls_used=%s/%s stale_scrolls=%s seen_cards=%s",
                        query,
                        loop_count,
                        len(results),
                        max_results,
                        total_visible,
                        scrolls_used,
                        max_scrolls,
                        stale_scrolls,
                        len(seen_card_keys),
                    )
                emit_progress(
                    query=query,
                    phase="scraping",
                    leads_collected=len(results),
                    leads_target=max_results,
                    visible_cards=total_visible,
                    scrolls_used=scrolls_used,
                    max_scrolls=max_scrolls,
                    stale_scrolls=stale_scrolls,
                    message=f"Scanning pass {loop_count} with {total_visible} visible cards",
                )
                discovered_this_pass = 0
                while discovered_this_pass < total_visible:
                    if should_cancel and should_cancel():
                        end_reason = "cancel_requested"
                        break
                    if time.time() - started >= effective_timeout:
                        end_reason = "runtime_limit"
                        break
                    if len(results) >= max_results:
                        end_reason = "max_results_reached"
                        break

                    card = cards.nth(discovered_this_pass)
                    discovered_this_pass += 1
                    card_key = _get_card_key(card)
                    if not card_key:
                        skip_counts["missing_key"] += 1
                        if len(card_samples) < DEBUG_CARD_SAMPLE_LIMIT:
                            card_samples.append(_capture_card_sample(card, "missing_key"))
                        if logger and logger.isEnabledFor(logging.DEBUG):
                            logger.debug("query=%s skip_card reason=missing_key", query)
                        continue
                    if card_key in seen_card_keys:
                        if logger and logger.isEnabledFor(logging.DEBUG):
                            logger.debug("query=%s skip_card card_key=%s reason=seen_or_missing", query, card_key)
                        continue

                    name = _get_card_name(card)
                    if not name:
                        skip_counts["missing_name"] += 1
                        if len(card_samples) < DEBUG_CARD_SAMPLE_LIMIT:
                            card_samples.append(_capture_card_sample(card, "missing_name"))
                        if logger and logger.isEnabledFor(logging.DEBUG):
                            logger.debug("query=%s skip_card card_key=%s reason=missing_name", query, card_key)
                        continue

                    try:
                        card.locator("a.hfpxzc").first.click(timeout=1500)
                        page.wait_for_timeout(600)
                    except Exception as exc:
                        skip_counts["click_failed"] += 1
                        if len(card_samples) < DEBUG_CARD_SAMPLE_LIMIT:
                            card_samples.append(_capture_card_sample(card, "click_failed", exc))
                        if logger and logger.isEnabledFor(logging.DEBUG):
                            logger.debug("query=%s skip_card card_key=%s reason=click_failed error=%s", query, card_key, exc)
                        continue

                    seen_card_keys.add(card_key)
                    phone, address, email, owner_name, website, maps_url, category, social_links = _extract_details_from_panel(page)
                    lead = normalize_lead(
                        LeadRecord(
                            query=query,
                            name=name,
                            phone=phone or NA_VALUE,
                            address=address or NA_VALUE,
                            email=email or NA_VALUE,
                            owner_name=owner_name or NA_VALUE,
                            website=website or NA_VALUE,
                            maps_url=maps_url or NA_VALUE,
                            category=category or NA_VALUE,
                            social_links=social_links,
                            scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        )
                    )
                    lead_key = lead_identity_key(lead)
                    lead_aliases = lead_identity_aliases(lead)
                    if seen_lead_keys.intersection(lead_aliases):
                        skip_counts["duplicate"] += 1
                        if len(card_samples) < DEBUG_CARD_SAMPLE_LIMIT:
                            card_samples.append(_capture_card_sample(card, "duplicate"))
                        if logger and logger.isEnabledFor(logging.DEBUG):
                            logger.debug("query=%s skip_lead lead_key=%s reason=duplicate", query, lead_key)
                        continue
                    seen_lead_keys.update(lead_aliases)
                    results.append(lead)

                    if logger and len(results) % 10 == 0:
                        logger.info(
                            "query=%s progress leads=%s/%s scrolls_used=%s/%s unique_cards=%s",
                            query,
                            len(results),
                            max_results,
                            scrolls_used,
                            max_scrolls,
                            len(seen_card_keys),
                        )
                    if len(results) % 5 == 0:
                        emit_progress(
                            query=query,
                            phase="scraping",
                            leads_collected=len(results),
                            leads_target=max_results,
                            visible_cards=total_visible,
                            scrolls_used=scrolls_used,
                            max_scrolls=max_scrolls,
                            stale_scrolls=stale_scrolls,
                            message=f"Collected {len(results)} of {max_results} leads",
                        )
                    if checkpoint_callback and (
                        len(results) - last_checkpoint_count >= CHECKPOINT_LEAD_INTERVAL
                        or time.time() - last_checkpoint_at >= CHECKPOINT_TIME_INTERVAL_SECONDS
                    ):
                        checkpoint_callback(results, seen_lead_keys, seen_card_keys)
                        last_checkpoint_at = time.time()
                        last_checkpoint_count = len(results)
                        if logger:
                            logger.info(
                                "query=%s checkpoint_saved partial_leads=%s total_known_cards=%s",
                                query,
                                len(results),
                                len(seen_card_keys),
                            )

                if len(results) >= max_results:
                    end_reason = "max_results_reached"
                    break
                if should_cancel and should_cancel():
                    end_reason = "cancel_requested"
                    break
                if time.time() - started >= effective_timeout:
                    end_reason = "runtime_limit"
                    break
                if scrolls_used >= max_scrolls:
                    end_reason = "max_scrolls_reached"
                    break

                _scroll_once(page)
                scrolls_used += 1
                if _count_unseen_visible_cards(page, seen_card_keys) == 0:
                    stale_scrolls += 1
                    page.wait_for_timeout(STALE_SCROLL_WAIT_MS)
                else:
                    stale_scrolls = 0
                if stale_scrolls >= MAX_STALE_SCROLLS:
                    end_reason = "stale_scroll_limit"
                    break

            if not results and max_visible_cards > 0:
                _dump_zero_collection_diagnostics(
                    page,
                    query,
                    logger,
                    end_reason=end_reason,
                    max_visible_cards=max_visible_cards,
                    scrolls_used=scrolls_used,
                    skip_counts=skip_counts,
                    card_samples=card_samples,
                )
        finally:
            if checkpoint_callback and results:
                checkpoint_callback(results, seen_lead_keys, seen_card_keys)
            browser.close()
    if logger:
        logger.info(
            "query=%s scrape_finished leads=%s duration_seconds=%.1f scrolls_used=%s end_reason=%s",
            query,
            len(results),
            time.time() - started,
            scrolls_used,
            end_reason,
        )
    emit_progress(
        query=query,
        phase="scrape_finished",
        leads_collected=len(results),
        leads_target=max_results,
        visible_cards=0,
        scrolls_used=scrolls_used,
        max_scrolls=max_scrolls,
        stale_scrolls=stale_scrolls,
        end_reason=end_reason,
        message=f"Scrape finished with {len(results)} leads",
    )
    return results

