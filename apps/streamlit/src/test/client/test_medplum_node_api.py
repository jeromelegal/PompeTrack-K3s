import json
import os
import pandas as pd
import pytest
import requests
from unittest.mock import MagicMock, patch

from client.medplum_node_api_client import (
    read_secret_file,
    MedplumNodeAPIClient,
)

# ---------------------------------------------------------------------
# read_secret_file
# ---------------------------------------------------------------------

def test_read_secret_file_existing(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("mypassword")
    assert read_secret_file(str(secret)) == "mypassword"


def test_read_secret_file_missing():
    assert read_secret_file("/non/existent/file") is None


def test_read_secret_file_none():
    assert read_secret_file(None) is None


# ---------------------------------------------------------------------
# MedplumNodeAPIClient initialization
# ---------------------------------------------------------------------

def test_client_init_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_HOST", raising=False)
    client = MedplumNodeAPIClient(base_url="http://example.com")
    assert client.base_url == "http://example.com"
    assert client.redis is None


@patch("redis.Redis")
def test_client_init_with_redis_success(mock_redis, monkeypatch):
    instance = mock_redis.return_value
    instance.ping.return_value = True

    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")

    client = MedplumNodeAPIClient()
    assert client.redis is not None
    instance.ping.assert_called_once()


@patch("redis.Redis")
def test_client_init_with_redis_failure(mock_redis, monkeypatch):
    mock_redis.side_effect = Exception("Redis down")

    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")

    client = MedplumNodeAPIClient()
    assert client.redis is None


# ---------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------

def test_cache_key_is_deterministic():
    client = MedplumNodeAPIClient()
    k1 = client._cache_key("/observations", {"a": 1, "b": 2})
    k2 = client._cache_key("/observations", {"b": 2, "a": 1})
    assert k1 == k2


# ---------------------------------------------------------------------
# get_observations
# ---------------------------------------------------------------------

@patch("requests.Session.get")
def test_get_observations_list_response(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "obs1"}, {"id": "obs2"}]
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    client = MedplumNodeAPIClient(base_url="http://example.com")
    obs = client.get_observations()

    assert len(obs) == 2
    assert obs[0]["id"] == "obs1"


@patch("requests.Session.get")
def test_get_observations_bundle_entry(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "entry": [
            {"resource": {"id": "obs1"}},
            {"resource": {"id": "obs2"}},
        ]
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    client = MedplumNodeAPIClient()
    obs = client.get_observations()

    assert [o["id"] for o in obs] == ["obs1", "obs2"]


@patch("requests.Session.get")
def test_get_observations_request_exception(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException("boom")

    client = MedplumNodeAPIClient()
    obs = client.get_observations()

    assert obs == []


# ---------------------------------------------------------------------
# _extract_observation_flat
# ---------------------------------------------------------------------

def test_extract_observation_flat_minimal():
    client = MedplumNodeAPIClient()
    obs = {
        "id": "123",
        "resourceType": "Observation",
        "subject": {"reference": "Patient/ABC"},
        "valueQuantity": {"value": 42, "unit": "kg"},
    }

    flat = client._extract_observation_flat(obs)

    assert flat["id"] == "123"
    assert flat["patientId"] == "ABC"
    assert flat["value"] == 42
    assert flat["unit"] == "kg"
    assert flat["raw"] == obs


# ---------------------------------------------------------------------
# observations_to_dataframe
# ---------------------------------------------------------------------

def test_observations_to_dataframe_flatten(monkeypatch):
    client = MedplumNodeAPIClient()

    fake_obs = [
        {
            "id": "1",
            "subject": {"reference": "Patient/P1"},
            "valueInteger": 10,
        }
    ]

    monkeypatch.setattr(
        client,
        "get_observations",
        lambda *args, **kwargs: fake_obs,
    )

    df = client.observations_to_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert df.iloc[0]["patientId"] == "P1"
    assert df.iloc[0]["value"] == 10


def test_observations_to_dataframe_no_flatten(monkeypatch):
    client = MedplumNodeAPIClient()

    fake_obs = [{"id": "1", "foo": {"bar": 2}}]

    monkeypatch.setattr(
        client,
        "get_observations",
        lambda *args, **kwargs: fake_obs,
    )

    df = client.observations_to_dataframe(flatten=False)
    assert "foo.bar" in df.columns


def test_observations_to_dataframe_empty(monkeypatch):
    client = MedplumNodeAPIClient()

    monkeypatch.setattr(
        client,
        "get_observations",
        lambda *args, **kwargs: [],
    )

    df = client.observations_to_dataframe()
    assert df.empty


# ---------------------------------------------------------------------
# search_observations_list
# ---------------------------------------------------------------------

def test_search_observations_list_builds_params(monkeypatch):
    client = MedplumNodeAPIClient()

    captured = {}

    def fake_get_observations(params=None, **kwargs):
        captured["params"] = params
        return []

    monkeypatch.setattr(client, "get_observations", fake_get_observations)

    client.search_observations_list(
        patient="P1",
        category="vital-signs",
        code="1234"
    )

    assert captured["params"] == {
        "patientId": "P1",
        "category": "vital-signs",
        "code": "1234",
    }

# ---------------------------------------------------------------------
# get_observations cache
# ---------------------------------------------------------------------

def test_get_observations_cache_hit(monkeypatch):
    client = MedplumNodeAPIClient()
    client.redis = MagicMock()

    cached_data = [{"id": "cached"}]
    client.redis.get.return_value = json.dumps(cached_data)

    result = client.get_observations()
    assert result == cached_data


def test_get_observations_cache_corrupted(monkeypatch):
    client = MedplumNodeAPIClient()
    client.redis = MagicMock()
    client.redis.get.return_value = "{invalid json"

    monkeypatch.setattr(
        client.session,
        "get",
        lambda *a, **k: MagicMock(
            json=lambda: [],
            raise_for_status=lambda: None,
        ),
    )

    assert client.get_observations() == []


def test_get_observations_use_cache_false(monkeypatch):
    client = MedplumNodeAPIClient()
    client.redis = MagicMock()

    monkeypatch.setattr(
        client.session,
        "get",
        lambda *a, **k: MagicMock(
            json=lambda: [{"id": "net"}],
            raise_for_status=lambda: None,
        ),
    )

    result = client.get_observations(use_cache=False)
    assert result == [{"id": "net"}]
    client.redis.get.assert_not_called()


def test_get_observations_single_object(monkeypatch):
    client = MedplumNodeAPIClient()

    monkeypatch.setattr(
        client.session,
        "get",
        lambda *a, **k: MagicMock(
            json=lambda: {"id": "single"},
            raise_for_status=lambda: None,
        ),
    )

    result = client.get_observations()
    assert result == [{"id": "single"}]


def test_get_observations_unexpected_type(monkeypatch):
    client = MedplumNodeAPIClient()

    monkeypatch.setattr(
        client.session,
        "get",
        lambda *a, **k: MagicMock(
            json=lambda: 123,
            raise_for_status=lambda: None,
        ),
    )

    assert client.get_observations() == []
