from pathlib import Path

from fastapi.testclient import TestClient

import api


def test_get_config_no_json_flag(monkeypatch):
    class FakeConfig:
        queries = ["electronics store lagos"]
        max_results_per_query = 50
        max_scrolls_per_query = 15
        max_runtime_seconds = 0
        output_dir = "csv_exports"
        logs_dir = "logs"
        checkpoint_dir = "checkpoints"
        archive_after_days = 14
        headless = True
        enrich_websites = True

    monkeypatch.setattr(api.AppConfig, "from_file", classmethod(lambda cls, _path: FakeConfig()))

    client = TestClient(api.app)
    response = client.get("/config")

    assert response.status_code == 200
    data = response.json()
    assert "export_json" not in data
    assert data["enrich_websites"] is True


def test_list_exports_only_returns_csv(tmp_path: Path, monkeypatch):
    export_dir = tmp_path / "csv_exports"
    export_dir.mkdir()
    (export_dir / "leads_sample.csv").write_text("query,name\nq,shop\n", encoding="utf-8")
    (export_dir / "leads_sample.json").write_text("[]", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    client = TestClient(api.app)
    response = client.get("/exports")

    assert response.status_code == 200
    data = response.json()
    assert [item["filename"] for item in data] == ["leads_sample.csv"]
