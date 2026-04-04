from scraper_models import LeadRecord
from scraper_utils import (
    CheckpointState,
    canonicalize_url,
    compute_confidence,
    lead_identity_key,
    load_checkpoint,
    normalize_phone,
    normalize_whitespace,
    save_checkpoint,
    slugify,
)


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


def test_normalization_helpers():
    assert normalize_whitespace("  Herbert   Macaulay   Way ") == "Herbert Macaulay Way"
    assert normalize_phone("+234 (801) 000-0000") == "2348010000000"
    assert canonicalize_url("https://example.com/path/?utm_source=test&x=1") == "https://example.com/path?x=1"


def test_lead_identity_prefers_business_fields_when_available():
    lead = LeadRecord(
        query="q",
        name="Shop",
        phone="0800 000 0000",
        address="Somewhere",
        maps_url="https://www.google.com/maps/place/foo/?utm_source=test",
    )
    assert lead_identity_key(lead) == "lead-address:shop|somewhere"


def test_lead_identity_falls_back_to_maps_url_for_sparse_records():
    lead = LeadRecord(query="q", name="Shop", maps_url="https://www.google.com/maps/place/foo/?utm_source=test")
    assert lead_identity_key(lead) == "maps:https://www.google.com/maps/place/foo"


def test_checkpoint_round_trip_and_legacy_compatibility(tmp_path):
    path = tmp_path / "checkpoint.json"
    leads = [LeadRecord(query="electronics store lagos", name="Shop", phone="0800 000 0000")]
    save_checkpoint(path, leads, {"lead:1"}, {"card:1"})

    state = load_checkpoint(path, "electronics store lagos")
    assert isinstance(state, CheckpointState)
    assert len(state.leads) == 1
    assert "lead:1" in state.lead_keys
    assert "lead-phone:shop|08000000000" in state.lead_keys
    assert state.card_keys == {"card:1"}

    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(
        '{"index": 1, "leads": [{"query": "electronics store lagos", "name": "Legacy Shop", "phone": "0800 000 0000"}]}',
        encoding="utf-8",
    )
    legacy_state = load_checkpoint(legacy_path, "electronics store lagos")
    assert len(legacy_state.leads) == 1
    assert legacy_state.card_keys == set()
    assert len(legacy_state.lead_keys) == 1
