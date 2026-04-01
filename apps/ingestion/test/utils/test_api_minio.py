import io
import json
import tempfile
import pytest
from botocore.exceptions import ClientError, BotoCoreError
from fastapi.responses import StreamingResponse

import utils.api_minio as api

# Fixtures
@pytest.fixture
def mock_s3(mocker):
    return mocker.Mock()

# Tests making object names
def test_make_object_name_given():
    name = api._make_object_name("bucket", "obj")
    assert name == "obj"

# Tests making object names
def test_make_object_name_generated():
    name = api._make_object_name("bucket", None)
    assert name.startswith("bucket/")

# Tests upload file OK
def test_upload_file_path_ok(tmp_path, mocker):
    file = tmp_path / "a.txt"
    file.write_text("hello")

    mocker.patch.object(api.s3_client, "upload_file")

    res = api.upload_file(str(file), "bucket")

    assert res["ok"] is True
    assert res["method"] == "upload_file"

# Tests upload file not found
def test_upload_file_path_not_found():
    res = api.upload_file("/no/file", "bucket")
    assert res["ok"] is False

# Tests upload bytes
def test_upload_bytes(mocker):
    mocker.patch.object(api.s3_client, "upload_fileobj")

    res = api.upload_file(b"abc", "bucket")

    assert res["ok"] is True
    assert res["method"] == "upload_fileobj"
    assert res["size"] == 3

# Tests upload BytesIO
def test_upload_bytesio(mocker):
    mocker.patch.object(api.s3_client, "upload_fileobj")

    bio = io.BytesIO(b"1234")
    res = api.upload_file(bio, "bucket")

    assert res["ok"] is True
    assert res["size"] == 4

# Tests upload fallback
def test_upload_fallback_put_object(mocker):
    mocker.patch.object(api.s3_client, "put_object")

    res = api.upload_file({"x": 1}, "bucket")

    assert res["ok"] is True
    assert res["method"] == "put_object"

# Tests upload boto error
def test_upload_boto_error(mocker):
    mocker.patch.object(
        api.s3_client,
        "upload_fileobj",
        side_effect=ClientError({"Error": {}}, "Upload")
    )

    res = api.upload_file(b"abc", "bucket")
    assert res["ok"] is False

# TEsts bucket list
def test_bucket_list_objects(mock_s3):
    paginator = mock_s3.get_paginator.return_value
    paginator.paginate.return_value = [
        {"Contents": [{"Key": "a"}, {"Key": "b"}]}
    ]

    keys = api.bucket_list_objects("bucket", s3_client=mock_s3)
    assert keys == ["a", "b"]

# Tests bucket list error
def test_bucket_list_objects_error(mock_s3):
    mock_s3.get_paginator.side_effect = ClientError({"Error": {}}, "List")

    with pytest.raises(RuntimeError):
        api.bucket_list_objects("bucket", s3_client=mock_s3)

# Tests download file
def test_download_file_success(mocker, mock_s3):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()

    mocker.patch("tempfile.NamedTemporaryFile", return_value=tmp)

    path = api.download_file("bucket", "key", s3_client=mock_s3)

    assert path == tmp.name
    mock_s3.download_file.assert_called_once()

# Tests download file error
def test_download_file_error(mock_s3):
    mock_s3.download_file.side_effect = ClientError({"Error": {}}, "Download")

    with pytest.raises(RuntimeError):
        api.download_file("bucket", "key", s3_client=mock_s3)

# Tests get object json
def test_get_object_json_ok(mock_s3):
    mock_s3.get_object.return_value = {
        "Body": io.BytesIO(json.dumps({"a": 1}).encode())
    }

    data = api.get_object_json("b", "o", s3_client=mock_s3)
    assert data == {"a": 1}

# Tests get object json error
def test_get_object_json_invalid_json(mock_s3):
    mock_s3.get_object.return_value = {
        "Body": io.BytesIO(b"no-json")
    }

    with pytest.raises(ValueError):
        api.get_object_json("b", "o", s3_client=mock_s3)

# Tests get object json
def test_move_object_ok(mock_s3):
    assert api.move_object("obj", "src", "dst", s3_client=mock_s3) is True

# Tests get object json error
def test_move_object_fail(mock_s3):
    mock_s3.copy_object.side_effect = ClientError({"Error": {}}, "Copy")
    assert api.move_object("obj", "src", "dst", s3_client=mock_s3) is False

# Tests bucket create
def test_bucket_create_ok(mock_s3):
    assert api.bucket_create("b", s3_client=mock_s3) is True

# Tests bucket create error
def test_bucket_create_error(mock_s3):
    mock_s3.create_bucket.side_effect = ClientError({"Error": {}}, "Create")
    assert api.bucket_create("b", s3_client=mock_s3) is False

# Tests buckets list
def test_buckets_list(mock_s3):
    mock_s3.list_buckets.return_value = {
        "Buckets": [{"Name": "a"}, {"Name": "b"}]
    }

    resp = api.buckets_list(s3_client=mock_s3)
    assert len(resp["Buckets"]) == 2

# TEsts get object stream
def test_get_object_stream_ok(mock_s3):
    body = io.BytesIO(b"hello world")
    mock_s3.get_object.return_value = {"Body": body}

    resp = api.get_object_stream("b", "k", s3_client=mock_s3)

    assert isinstance(resp, StreamingResponse)

# Tests get object stream error
def test_get_object_stream_no_body(mock_s3):
    mock_s3.get_object.return_value = {}

    with pytest.raises(RuntimeError):
        api.get_object_stream("b", "k", s3_client=mock_s3)

# Tests get object stream error
def test_get_object_stream_error(mock_s3):
    mock_s3.get_object.side_effect = ClientError({"Error": {}}, "Get")

    with pytest.raises(RuntimeError):
        api.get_object_stream("b", "k", s3_client=mock_s3)


