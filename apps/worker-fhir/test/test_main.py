from fastapi.testclient import TestClient
from main import app
import pytest
from unittest.mock import Mock, patch
import responses
import requests
import json

client = TestClient(app)

    
@responses.activate
def test_external_call():
    responses.add(
        responses.GET,
        "https://api.com/endpoint",
        json={"ok": True},
        status=200
    )
    
def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "Worker API ready."}


@pytest.mark.asyncio
async def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    js = r.json()
    assert js["status"] == "ok"

    assert isinstance(js["time"], str)
    
def test_run_worker_success(mocker):
    mock_run = mocker.patch("main.subprocess.run")
    mock_run.return_value = mocker.MagicMock(returncode=0, stdout="PIPELINE OK", stderr="")

    r = client.post("/run/iphone")
    assert r.status_code == 200
    assert r.json() == {"status": "success", "output": "PIPELINE OK"}
    mock_run.assert_called_once_with(
        ["python", "/app/pipeline_iphone.py"],
        capture_output=True,
        text=True,
    )
    
def test_run_worker_failure(mocker):
    mock_run = mocker.patch("main.subprocess.run")
    mock_run.return_value = mocker.MagicMock(returncode=1, stdout="", stderr="Error\n")
    r = client.post("/run/iphone")
    assert r.status_code == 500
    assert "Error" in r.json()["detail"]
    
def test_run_worker_exception(mocker):
    mock_run = mocker.patch("app.main.subprocess.run", side_effect=Exception("Boom!"))
    r = client.post("/run/iphone")
    assert r.status_code == 500
    assert "Boom!" in r.json()["detail"]
    
def test_external_call_requests(monkeypatch):
    def fake_get(url):
        assert url == "https://api.example.com/v1/data"
        class Resp:
            status_code = 200
            json = lambda self: {"ok": True}
        return Resp()
    monkeypatch.setattr(requests, "get", fake_get)