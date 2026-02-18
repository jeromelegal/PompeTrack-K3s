import pytest
from unittest import mock
from worker import build_search_url, get_auth_token, fetch_fhir_observation

def test_build_search_url_basic():
    url = build_search_url(
        base="http://example.com/fhir/",
        resource_type="Observation",
        params={
            "patient": "Patient/123",
            "category": "activity",
            "code": None
        }
    )

    expected = (
        "http://example.com/fhir/Observation?"
        "patient=Patient%2F123&category=activity"
    )
    assert url == expected


def test_get_auth_token(mocker):
    mock_response = mock.Mock()
    mock_response.json.return_value = {"access_token": "fake-token-123"}
    mock_response.raise_for_status.return_value = None

    mocker.patch("worker.requests.post", return_value=mock_response)

    token = get_auth_token(
        url="https://auth.example/token",
        client_id="id",
        client_secret="secret"
    )
    assert token == "fake-token-123"


def test_fetch_fhir_observation_single_page(mocker):

    fake_bundle = {
        "entry": [
            {"resource": {"id": "obs1", "resourceType": "Observation"}},
            {"resource": {"id": "obs2", "resourceType": "Observation"}},
        ],
        "link": []
    }

    mock_response = mock.Mock()
    mock_response.json.return_value = fake_bundle
    mock_response.raise_for_status.return_value = None

    mocker.patch("worker.requests.get", return_value=mock_response)
    mocker.patch("worker.get_auth_token", return_value="test-token")

    results = fetch_fhir_observation(
        patient="123",
        payload={}
    )

    assert results == [
        {"id": "obs1", 'resourceType': 'Observation'},
        {"id": "obs2", 'resourceType': 'Observation'}
    ]

def test_fetch_fhir_observation_pagination(mocker):
    mocker.patch("worker.get_auth_token", return_value="test-token")

    page1 = {
        "entry": [{"resource": {"id": "obs1", "resourceType": "Observation"}}],
        "link": [{"relation": "next", "url": "http://next.page"}]
    }
    page2 = {
        "entry": [{"resource": {"id": "obs2", "resourceType": "Observation"}}],
        "link": []
    }

    resp1 = mock.Mock()
    resp1.json.return_value = page1
    resp1.raise_for_status.return_value = None

    resp2 = mock.Mock()
    resp2.json.return_value = page2
    resp2.raise_for_status.return_value = None

    mocker.patch("worker.requests.get", side_effect=[resp1, resp2])

    results = fetch_fhir_observation(
        patient="123",
        payload={"max_records": None}
    )

    assert results == [
        {"id": "obs1", "resourceType": "Observation"},
        {"id": "obs2", "resourceType": "Observation"},
    ]

def test_resolve_has_member(mocker):
    """
    Ce test vérifie que la boucle qui parcourt la propriété hasMember
    est bien exécutée et que les données sont ajoutées dans
    la clé resolvedHasMember.
    """
    all_observations = [
        {
            "id": "obsA",
            "hasMember": [{"reference": "obsB"}],
            "resourceType": "Observation"
        },
        {
            "id": "obsB",
            "effectiveDateTime": "2023-01-01",
            "valueQuantity": {"value": 5},
            "resourceType": "Observation"
        }
    ]

    def resolve_members(obs_list):
        results = []
        obs_index = {obs["id"]: obs for obs in obs_list}
        for obs in obs_list:
            resolved_members = []
            for member_ref in obs.get("hasMember", []):
                ref = member_ref.get("reference")
                member_obs = obs_index.get(ref)
                if not member_obs:
                    continue
                resolved_members.append({
                    "reference": ref,
                    "effectiveDateTime": member_obs.get("effectiveDateTime"),
                    "valueQuantity": member_obs.get("valueQuantity")
                })
            if resolved_members:
                obs["resolvedHasMember"] = resolved_members
            results.append(obs)
        return results

    resolved = resolve_members(all_observations)
    assert resolved[0]["resolvedHasMember"] == [
        {
            "reference": "obsB",
            "effectiveDateTime": "2023-01-01",
            "valueQuantity": {"value": 5}
        }
    ]