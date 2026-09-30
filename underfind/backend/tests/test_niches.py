from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from underfind.backend.core.niches import list_niches, load_niche
from underfind.backend.db.pipeline_repo import PipelineRepository
from underfind.backend.dependencies import get_pipeline_repo
from underfind.backend.main import app
from underfind.backend.pipeline.glossary import load_glossary


def test_gta6_preset_loads():
    niche = load_niche("gta6")

    assert "gta6" in list_niches()
    assert "Vice City" in niche.glossary
    assert "#gta6" in niche.hashtags
    assert "gta v" in niche.keywords.exclude


def test_custom_niche_and_unknown(tmp_path: Path):
    (tmp_path / "cars.yaml").write_text("name: cars\nglossary: [Porsche 911]\nhashtags: ['#cars']\n")

    assert load_niche("cars", tmp_path).glossary == ["Porsche 911"]
    assert load_niche(None) is None

    with pytest.raises(KeyError):
        load_niche("nope", tmp_path)


def test_glossary_merges_niche_page_and_file(tmp_path: Path, monkeypatch):
    extra = tmp_path / "g.json"
    extra.write_text('["Trevor", "Vice City"]')
    monkeypatch.setenv("GLOSSARY_FILE", str(extra))

    terms = load_glossary("gta6", ["Brucie"])

    assert terms.count("Vice City") == 1
    assert {"Brucie", "Trevor", "Lucia"} <= set(terms)
    assert load_glossary(None, None) == ["Trevor", "Vice City"]


def test_page_api_validates_niche_and_outputs(tmp_path: Path):
    repo = PipelineRepository(db_path=tmp_path / "p.sqlite3")
    app.dependency_overrides[get_pipeline_repo] = lambda: repo
    client = TestClient(app)

    try:
        ok = client.post("/api/pages", json={
            "display_name": "Carros BR", "handle": "carrosbr", "niche": "gta6",
            "brand_tag": "CARROSBR", "glossary": ["Porsche"], "outputs": ["reel", "post", "carousel"],
        })
        assert ok.status_code == 200
        body = ok.json()
        assert body["brand_tag"] == "CARROSBR" and body["outputs"] == ["reel", "post", "carousel"]
        assert body["glossary"] == ["Porsche"]

        assert client.post("/api/pages", json={"display_name": "x", "handle": "x1", "niche": "nope"}).status_code == 404
        assert client.post("/api/pages", json={"display_name": "x", "handle": "x2", "outputs": ["story"]}).status_code == 422
        assert "gta6" in [n["name"] for n in client.get("/api/niches").json()]
    finally:
        app.dependency_overrides.clear()
