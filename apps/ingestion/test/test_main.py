import json
import io
import pytest
from fastapi.testclient import TestClient
from fastapi.responses import StreamingResponse
import pathlib
import sys
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
import main

client = TestClient(main.app)

@pytest.fixture(autouse=True)
def override_security():
    def fake_dependency():
        return {"device": "test-device"}

    main.app.dependency_overrides = {}

    # Override global : toute dépendance qui appelle require_api_key(...)
    for route in main.app.routes:
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                if dep.call.__name__ == "require_api_key":
                    main.app.dependency_overrides[dep.call] = fake_dependency

    yield
    main.app.dependency_overrides = {}

# @pytest.fixture(autouse=True)
# def override_api_key():
#     main.app.dependency_overrides[main.api_key_dep] = lambda: {
#         "client_id": "test-client",
#         "scopes": ["ingest:manual"]
#     }
#     yield
#     main.app.dependency_overrides.clear()

@pytest.fixture
def client():
    return TestClient(main.app)

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "API-Ingestion ready."}

def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "time" in r.json()

@pytest.mark.parametrize("endpoint,bucket", [
    ("/ingest/iphone", main.BUCKET_RAW_IPHONE),
    ("/ingest/manual", main.BUCKET_RAW_MANUAL),
    ("/ingest/spirometer", main.BUCKET_RAW_SPIROMETER),
    ("/ingest/fhir", main.BUCKET_PROCESSED_FHIR),
])
def test_ingest_json_ok(client, mocker, endpoint, bucket):
    upload = mocker.patch("main.upload_file", return_value={"ok": True})

    payload = {"a": 1}
    r = client.post(endpoint, json=payload)

    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    upload.assert_called_once()

def test_ingest_json_upload_error(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": False, "error": "fail"})

    r = client.post("/ingest/iphone", json={"a": 1})
    assert r.status_code == 500

def test_ingest_generic_ok(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": True})

    files = {"file": ("test.txt", b"abc")}
    data = {"metadata": json.dumps({"k": "v"})}

    r = client.post("/ingest/generic/test-bucket", files=files, data=data)

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["metadata"] == {"k": "v"}

def test_ingest_generic_invalid_metadata(client):
    files = {"file": ("x.txt", b"abc")}
    r = client.post(
        "/ingest/generic/bucket",
        files=files,
        data={"metadata": "not-json"}
    )

    assert r.status_code == 400


def test_ingest_generic_upload_error(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": False})

    files = {"file": ("x.txt", b"abc")}
    r = client.post("/ingest/generic/bucket", files=files)

    assert r.status_code == 500


def test_ingest_dataframe_ok(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": True})

    files = {"file": ("df.csv", b"a,b\n1,2")}
    r = client.post("/ingest/dataframe", files=files)

    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ingest_dataframe_upload_error(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": False})

    files = {"file": ("df.csv", b"x")}
    r = client.post("/ingest/dataframe", files=files)

    assert r.status_code == 500


def test_get_json_object_ok(client, mocker):
    mocker.patch("main.get_object_json", return_value={"a": 1})

    r = client.get("/object/json/bucket/file")
    assert r.status_code == 200
    assert r.json() == {"a": 1}


def test_get_json_object_error(client, mocker):
    mocker.patch(
        "main.get_object_json",
        side_effect=RuntimeError("fail")
    )

    r = client.get("/object/json/bucket/file")
    assert r.status_code == 500


def test_bucket_create_ok(client, mocker):
    mocker.patch("main.bucket_create", return_value=True)

    r = client.post("/bucket/create/test-bucket")
    assert r.status_code == 200


def test_bucket_create_fail(client, mocker):
    mocker.patch("main.bucket_create", return_value=False)

    r = client.post("/bucket/create/test-bucket")
    assert r.status_code == 500


def test_bucket_list_objects_ok(client, mocker):
    mocker.patch("main.bucket_list_objects", return_value=["a", "b"])

    r = client.get("/bucket/object-list/test")
    assert r.status_code == 200
    assert r.json() == ["a", "b"]


def test_move_object_ok(client, mocker):
    mocker.patch("main.move_object", return_value=True)

    r = client.post(
        "/object/move/x/a/b",
    )

    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_move_object_fail(client, mocker):
    mocker.patch("main.move_object", return_value=False)

    r = client.post(
        "/object/move/x/a/b",
    )

    assert r.status_code == 500


