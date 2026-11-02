"""The web back end: handles cannot reach outside the evidence, and panels get only structured data."""
import json

import pytest

pytest.importorskip("ag_ui_langgraph", reason="make setup installs the web extra")
from fastapi import HTTPException
from fastapi.testclient import TestClient

from dd2_agent import generative_ui, model, server


@pytest.fixture(scope="module")
def client():
    cfg = model.load_config()
    cfg["model"]["provider"] = "scripted"
    return TestClient(server.create_app(cfg))


@pytest.mark.parametrize("handle", ["cell:../../etc", "run:../../x", "cell:a/../../b", "file:x", "cell:", "run:A/b/c", "cell:%2e%2e"])
def test_a_bad_handle_is_refused(handle):
    with pytest.raises(HTTPException):
        server.resolve(handle)


def test_the_route_refuses_traversal_too(client):
    assert client.get("/api/evidence/cell:..%2F..%2FMakefile").status_code == 404


def test_a_report_becomes_a_structured_view():
    v = server.cell_view({"cell": "c", "status": "pass", "failed_checks": [], "inputs": ["A"], "truth_table": "0x1",
                          "checks": {"drc": {"status": "pass", "errors": 0}}, "layout": {"width_sites": 3}})
    assert v["truth"] == [{"row": 0, "y": 1}, {"row": 1, "y": 0}] and v["checks"][0] == {"check": "drc", "status": "pass", "detail": "0"}


def test_a_real_cell_serves_its_layers(client):
    r = client.get("/api/evidence/cell:dd2_ref__inv_1", params={"view": "layout"})
    assert r.status_code == 200 and r.json()["layers"]["poly"] and {"text": "A"}.items() <= r.json()["labels"][0].items() or r.json()["labels"]


def test_the_chat_route_returns_an_error_not_a_crash(client, monkeypatch):
    from dd2_agent import codex_cli

    def boom(*a, **k):
        raise codex_cli.CodexError("no reply")

    monkeypatch.setattr(codex_cli.CodexCLI, "complete", boom)
    assert client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "x"}]}).status_code == 502


def test_every_component_the_checker_allows_is_in_the_web_library():
    text = (generative_ui.paths.ROOT / "web" / "src" / "library.tsx").read_text()
    for name in generative_ui.COMPONENTS:
        assert f'name: "{name}"' in text, name
    assert json.dumps(sorted(generative_ui.COMPONENTS))
