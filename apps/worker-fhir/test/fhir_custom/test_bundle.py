import json
import uuid
from unittest import mock
import pytest

from fhir_custom.bundle import build_bundle_fhir, upload_bundle, FHIR_BASE

from fhir.resources.observation import Observation

# Fixtures
@pytest.fixture
def dummy_observations():
    """
    Deux Observations simples (id explicite et sans id).
    """
    obs1 = Observation.model_construct(id="obs-foo", status="final", code={})
    obs2 = Observation.model_construct(code={})
    return [obs1, obs2]


# Test build_bundle_fhir empty
def test_build_bundle_empty():
    """Bundle vide renvoie un bundle de type « transaction » sans entrées."""
    bundle = build_bundle_fhir([])
    # assert bundle.resourceType == "Bundle"
    assert bundle.type == "transaction"
    assert len(bundle.entry) == 0

# Test build_bundle_fhir single
def test_build_bundle_single_observation(dummy_observations):
    """Une seule Observation crée une entrée correcte."""
    bundle = build_bundle_fhir([dummy_observations[0]])
    assert len(bundle.entry) == 1
    entry = bundle.entry[0]
    assert entry.fullUrl == f"urn:uuid:{dummy_observations[0].id}"    # id passé
    assert entry.resource == dummy_observations[0]

# Test build_bundle_fhir multiple
def test_build_bundle_multiple_observations(dummy_observations):
    """Plusieurs Observations générent plusieurs entrées, UUID généré si nécessaire."""
    with mock.patch.object(uuid, "uuid4", return_value=uuid.UUID("12345678-1234-5678-1234-567812345678")):
        bundle = build_bundle_fhir(dummy_observations)

    entry0 = bundle.entry[0]
    assert entry0.fullUrl == f"urn:uuid:{dummy_observations[0].id}"
    entry1 = bundle.entry[1]
    assert entry1.fullUrl == "urn:uuid:12345678-1234-5678-1234-567812345678"


# Tests upload_bundle
@pytest.fixture
def dummy_payload():
    """Conversion JSON d'un bundle (seulement pour l'exemple)."""
    obj = dict(
        resourceType="Bundle",
        type="transaction",
        entry=[{"fullUrl": "foo"}],
    )
    return json.dumps(obj).encode("utf-8")

# Test upload_bundle
def test_upload_bundle_success(mocker, dummy_payload):
    """Code 200 ou 201 : retourne True."""
    mock_token = "the-token"

    mocker.patch("fhir_custom.bundle.get_token", return_value=mock_token)
    mock_response = mock.Mock(status_code=201, text="Created")
    mock_post = mocker.patch("fhir_custom.bundle.requests.post", return_value=mock_response)

    result = upload_bundle(dummy_payload)

    assert result is True

    headers_sent = mock_post.call_args.kwargs["headers"]
    assert headers_sent["Authorization"] == f"Bearer {mock_token}"
    assert headers_sent["Content-Type"] == "application/fhir+json"

    assert mock_post.call_args.kwargs["timeout"] == 30
    assert mock_post.call_args.kwargs["data"] == dummy_payload

# Test upload_bundle failure
def test_upload_bundle_failure_status(mocker, dummy_payload):
    """Code non-200/201 => retourne False."""
    mocker.patch("fhir_custom.bundle.get_token", return_value="tok")
    mock_response = mock.Mock(status_code=500, text="Server error")
    mocker.patch("fhir_custom.bundle.requests.post", return_value=mock_response)

    assert upload_bundle(dummy_payload) is False

# Test upload_bundle exception
def test_upload_bundle_exception(mocker, dummy_payload):
    """Une exception dans requests.post fait remonter False."""
    mocker.patch("fhir_custom.bundle.get_token", return_value="tok")
    mocker.patch("fhir_custom.bundle.requests.post", side_effect=Exception("boom"))
    assert upload_bundle(dummy_payload) is False