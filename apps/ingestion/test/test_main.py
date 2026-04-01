import json
import io
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

import libs.security as _sec

# Mock security
def _fake_require_scopes(scopes):
    def _dep():
        return {"device": "test-device"}
    return _dep

_sec.require_scopes = _fake_require_scopes

import main

# Fixtures
@pytest.fixture
def client():
    return TestClient(main.app)

# Tests access
def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "API-Ingestion ready."}

# Tests health
def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "time" in r.json()

# Tests ingest
@pytest.mark.parametrize("endpoint,bucket", [
    ("/ingest/iphone",    main.BUCKET_RAW_IPHONE),
    ("/ingest/manual",    main.BUCKET_RAW_MANUAL),
    ("/ingest/spirometer",main.BUCKET_RAW_SPIROMETER),
    ("/ingest/fhir",      main.BUCKET_PROCESSED_FHIR),
])
def test_ingest_json_ok(client, mocker, endpoint, bucket):
    mocker.patch("main.upload_file", return_value={"ok": True})
    r = client.post(endpoint, json={"a": 1})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

# Tests ingest upload error
@pytest.mark.parametrize("endpoint", [
    "/ingest/iphone",
    "/ingest/manual",
    "/ingest/spirometer",
    "/ingest/fhir",
])
def test_ingest_json_upload_error(client, mocker, endpoint):
    mocker.patch("main.upload_file", return_value={"ok": False, "error": "fail"})
    r = client.post(endpoint, json={"a": 1})
    assert r.status_code == 500


SQLITE_HEADER = b"SQLite format 3\x00" + b"\x00" * 84  # 100 bytes min

# Tests ingest sqlite
def test_ingest_sqlite_ok(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": True})
    files = {"file": ("data.db", SQLITE_HEADER)}
    r = client.post("/ingest/sqlite", files=files)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

# Tests ingest sqlite bad extension
def test_ingest_sqlite_bad_extension(client, mocker):
    files = {"file": ("data.txt", SQLITE_HEADER)}
    r = client.post("/ingest/sqlite", files=files)
    assert r.status_code == 400

# Tests ingest sqlite bad header
def test_ingest_sqlite_bad_header(client, mocker):
    files = {"file": ("data.db", b"not a sqlite file")}
    r = client.post("/ingest/sqlite", files=files)
    assert r.status_code == 400

# Tests ingest sqlite upload error
def test_ingest_sqlite_upload_error(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": False, "error": "fail"})
    files = {"file": ("data.db", SQLITE_HEADER)}
    r = client.post("/ingest/sqlite", files=files)
    assert r.status_code == 500

# Tests ingest generic
def test_ingest_generic_ok(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": True})
    files = {"file": ("test.txt", b"abc")}
    data  = {"metadata": json.dumps({"k": "v"})}
    r = client.post("/ingest/generic/test-bucket", files=files, data=data)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["metadata"] == {"k": "v"}

# Tests ingest generic invalid metadata
def test_ingest_generic_invalid_metadata(client):
    files = {"file": ("x.txt", b"abc")}
    r = client.post("/ingest/generic/bucket", files=files, data={"metadata": "not-json"})
    assert r.status_code == 400

# Tests ingest generic upload error
def test_ingest_generic_upload_error(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": False})
    files = {"file": ("x.txt", b"abc")}
    r = client.post("/ingest/generic/bucket", files=files)
    assert r.status_code == 500

# Tests ingest dataframe
def test_ingest_dataframe_ok(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": True})
    files = {"file": ("df.csv", b"a,b\n1,2")}
    r = client.post("/ingest/dataframe", files=files)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

# Tests ingest dataframe upload error
def test_ingest_dataframe_upload_error(client, mocker):
    mocker.patch("main.upload_file", return_value={"ok": False})
    files = {"file": ("df.csv", b"x")}
    r = client.post("/ingest/dataframe", files=files)
    assert r.status_code == 500

# Tests download object
def test_download_object_ok(client, mocker):
    from fastapi.responses import StreamingResponse
    mocker.patch("main.get_raw_object", return_value=StreamingResponse(iter([b"data"])))
    r = client.get("/download/bucket/file.txt")
    assert r.status_code == 200

# Tests download object error
def test_download_object_error(client, mocker):
    mocker.patch("main.get_raw_object", side_effect=RuntimeError("fail"))
    r = client.get("/download/bucket/file.txt")
    assert r.status_code == 500

# Tests get json object
def test_get_json_object_ok(client, mocker):
    mocker.patch("main.get_object_json", return_value={"a": 1})
    r = client.get("/object/json/bucket/file")
    assert r.status_code == 200
    assert r.json() == {"a": 1}

# Tests get json object error
def test_get_json_object_error(client, mocker):
    mocker.patch("main.get_object_json", side_effect=RuntimeError("fail"))
    r = client.get("/object/json/bucket/file")
    assert r.status_code == 500

# Tests bucket create
def test_bucket_create_ok(client, mocker):
    mocker.patch("main.bucket_create", return_value=True)
    r = client.post("/bucket/create/test-bucket")
    assert r.status_code == 200

# Tests bucket create error
def test_bucket_create_fail(client, mocker):
    mocker.patch("main.bucket_create", return_value=False)
    r = client.post("/bucket/create/test-bucket")
    assert r.status_code == 500

# Tests bucket list objects
def test_bucket_list_objects_ok(client, mocker):
    mocker.patch("main.bucket_list_objects", return_value=["a", "b"])
    r = client.get("/bucket/object-list/test")
    assert r.status_code == 200
    assert r.json() == ["a", "b"]

# Tests move object
def test_move_object_ok(client, mocker):
    mocker.patch("main.move_object", return_value=True)
    r = client.post("/object/move/x/a/b")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

# Tests move object error
def test_move_object_fail(client, mocker):
    mocker.patch("main.move_object", return_value=False)
    r = client.post("/object/move/x/a/b")
    assert r.status_code == 500

# Tests delete object
def test_delete_object_ok(client, mocker):
    mocker.patch("main.object_delete", return_value=True)
    r = client.post("/object/delete/bucket/file.txt")
    assert r.status_code == 200

# Tests delete object error
def test_delete_object_fail(client, mocker):
    mocker.patch("main.object_delete", return_value=False)
    r = client.post("/object/delete/bucket/file.txt")
    assert r.status_code == 500
