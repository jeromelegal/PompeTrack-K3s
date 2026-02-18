import pytest
import main
from fastapi.testclient import TestClient

client = TestClient(main.app)

@pytest.fixture(autouse=True)
def override_api_key():
    main.app.dependency_overrides[main.api_key_dep] = lambda: {
        "client_id": "test-client",
        "scopes": ["stream:fhir"]
    }
    yield
    main.app.dependency_overrides.clear()

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "Worker API ready."}

def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    js = r.json()
    assert js["status"] == "ok"
    assert js["time"]
    
# Tests for `fetch_observation`
def test_fetch_observation_success(mocker):
    mocker.patch("main.fetch_fhir_observation",
                return_value={"mood": "good"})
    r = client.post("/data/observation/12345", json={"foo": "bar"})
    assert r.status_code == 200
    assert r.json() == {"data": {"mood": "good"}}

def test_fetch_observation_runtime_error(mocker):
    mocker.patch("main.fetch_fhir_observation",
                 side_effect=RuntimeError("boom!"))
    r = client.post("/data/observation/6789", json={})
    assert r.status_code == 500
    js = r.json()
    assert js["status"] == "error"
    assert "boom!" in js["message"]

def test_fetch_observation_value_error(mocker):
    mocker.patch("main.fetch_fhir_observation",
                 side_effect=ValueError("bad payload"))
    r = client.post("/data/observation/abc", json={})
    assert r.status_code == 500
    js = r.json()
    assert js["status"] == "error"
    assert "bad payload" in js["message"]

def test_fetch_observation_no_body():
    r = client.post("/data/observation/userid")
    assert r.status_code == 422

def test_fetch_observation_with_dependency_override():
    def fake_fetch(patient, payload):
        return {"ok": True}
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(main, "fetch_fhir_observation", fake_fetch)
    r = client.post("/data/observation/any", json={})
    assert r.status_code == 200
    assert r.json() == {"data": {"ok": True}}
    monkeypatch.undo()