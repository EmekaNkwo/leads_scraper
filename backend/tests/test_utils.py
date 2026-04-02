from scraper_models import LeadRecord
from scraper_utils import compute_confidence, slugify


def test_slugify():
    assert slugify("Electronics Store Lagos") == "electronics-store-lagos"


def test_confidence_score():
    lead = LeadRecord(
        query="q",
        name="Shop",
        phone="0800 000 0000",
        address="Somewhere",
        email="x@example.com",
        website="https://example.com",
        owner_name="John Doe",
    )
    assert compute_confidence(lead) == 1.0
