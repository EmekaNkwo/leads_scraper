from pathlib import Path

import scraper_maps
from scraper_maps import _artifact_dir_from_logger, _dump_zero_collection_diagnostics
from scraper_utils import setup_logger


class FakePage:
    def __init__(self) -> None:
        self.url = "https://www.google.com/maps/search/electronics+store+lagos"
        self.screenshot_calls = 0

    def content(self) -> str:
        return "<html><body><div role='article'>Card</div></body></html>"

    def screenshot(self, path: str, full_page: bool, timeout: int) -> None:
        self.screenshot_calls += 1
        Path(path).write_bytes(b"fake-image")

    def title(self) -> str:
        return "Google Maps"


def test_dump_zero_collection_diagnostics_writes_artifacts(tmp_path):
    logger = setup_logger(tmp_path / "logs", "maps_debug")
    page = FakePage()

    _dump_zero_collection_diagnostics(
        page,
        "electronics store lagos",
        logger,
        end_reason="runtime_limit",
        max_visible_cards=26,
        scrolls_used=4,
        skip_counts={"missing_key": 3, "missing_name": 1, "click_failed": 2, "duplicate": 0},
        card_samples=[{"reason": "missing_key", "text_excerpt": "sample card"}],
    )

    artifact_dir = _artifact_dir_from_logger(logger)
    assert artifact_dir is not None
    assert len(list(artifact_dir.glob("scrape_debug_electronics-store-lagos_*.html"))) == 1
    assert len(list(artifact_dir.glob("scrape_debug_electronics-store-lagos_*.png"))) == 1
    summary_files = list(artifact_dir.glob("scrape_debug_electronics-store-lagos_*.txt"))
    assert len(summary_files) == 1
    assert "runtime_limit" in summary_files[0].read_text(encoding="utf-8")
    assert page.screenshot_calls == 1


class FakeCardsLocator:
    def count(self) -> int:
        return 0


class FakeGenericLocator:
    def count(self) -> int:
        return 0

    @property
    def first(self):
        return self


class FakeScrapePage:
    def locator(self, selector: str):
        if selector == "div.Nv2PK, div[role='article']":
            return FakeCardsLocator()
        return FakeGenericLocator()

    def wait_for_timeout(self, _timeout_ms: int) -> None:
        return None


class FakeBrowser:
    def __init__(self) -> None:
        self.page = FakeScrapePage()

    def new_page(self) -> FakeScrapePage:
        return self.page

    def close(self) -> None:
        return None


class FakePlaywrightContext:
    def __enter__(self):
        chromium = type("Chromium", (), {"launch": lambda self, headless=True: FakeBrowser()})()
        return type("Playwright", (), {"chromium": chromium})()

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_scrape_query_persists_scrolls_when_no_new_leads(monkeypatch):
    checkpoint_calls = []

    monkeypatch.setattr(scraper_maps, "sync_playwright", lambda: FakePlaywrightContext())
    monkeypatch.setattr(scraper_maps, "_open_maps_search", lambda page, query: None)
    monkeypatch.setattr(scraper_maps, "_scroll_once", lambda page: None)
    monkeypatch.setattr(scraper_maps, "_count_unseen_visible_cards", lambda page, seen_card_keys: 0)

    scraper_maps.scrape_query(
        query="electronics store lagos",
        max_results=5,
        max_scrolls=5,
        max_runtime_seconds=30,
        initial_scrolls_used=4,
        checkpoint_callback=lambda results, lead_keys, card_keys, scrolls_used: checkpoint_calls.append(scrolls_used),
    )

    assert checkpoint_calls[-1] == 5
