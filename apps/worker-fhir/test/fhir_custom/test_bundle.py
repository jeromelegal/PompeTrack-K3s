import json
import uuid
from unittest import mock
import pytest

from fhir_custom.bundle import build_bundle_fhir, upload_bundle, FHIR_BASE

from fhir.resources.observation import Observation


@pytest.fixture
def dummy_observations():
    """
    Deux Observations simples (id explicite et sans id).
    """
    obs1 = Observation.model_construct(id="obs-foo", status="final", code={})
    obs2 = Observation.model_construct(code={})
    return [obs1, obs2]



# Tests pour build_bundle_fhir
def test_build_bundle_empty():
    """Bundle vide renvoie un bundle de type « transaction » sans entrées."""
    bundle = build_bundle_fhir([])
    # assert bundle.resourceType == "Bundle"
    assert bundle.type == "transaction"
    assert len(bundle.entry) == 0

def test_build_bundle_single_observation(dummy_observations):
    """Une seule Observation crée une entrée correcte."""
    bundle = build_bundle_fhir([dummy_observations[0]])
    assert len(bundle.entry) == 1
    entry = bundle.entry[0]
    assert entry.fullUrl == f"urn:uuid:{dummy_observations[0].id}"    # id passé
    assert entry.resource == dummy_observations[0]

def test_build_bundle_multiple_observations(dummy_observations):
    """Plusieurs Observations générent plusieurs entrées, UUID généré si nécessaire."""
    with mock.patch.object(uuid, "uuid4", return_value=uuid.UUID("12345678-1234-5678-1234-567812345678")):
        bundle = build_bundle_fhir(dummy_observations)

    # 1ère : id fourni
    entry0 = bundle.entry[0]
    assert entry0.fullUrl == f"urn:uuid:{dummy_observations[0].id}"
    # 2ème : id auto-généré
    entry1 = bundle.entry[1]
    assert entry1.fullUrl == "urn:uuid:12345678-1234-5678-1234-567812345678"


# Tests pour upload_bundle
@pytest.fixture
def dummy_payload():
    """Conversion JSON d'un bundle (seulement pour l'exemple)."""
    obj = dict(
        resourceType="Bundle",
        type="transaction",
        entry=[{"fullUrl": "foo"}],
    )
    return json.dumps(obj).encode("utf-8")

def test_upload_bundle_success(mocker, dummy_payload):
    """Code 200 ou 201 : retourne True."""
    mock_token = "the-token"

    # --- patch du token dans le même module que la fonction ---
    mocker.patch("fhir_custom.bundle.get_token", return_value=mock_token)

    # --- patch de l’appel HTTP vers Medplum, avec le mock de réponse 201 ---
    mock_response = mock.Mock(status_code=201, text="Created")
    mock_post = mocker.patch("fhir_custom.bundle.requests.post", return_value=mock_response)

    # --- exécution du code à tester ---
    result = upload_bundle(dummy_payload)

    # --- assertions de retour ----------
    assert result is True

    # --- vérification du contenu des headers envoyés ----------
    headers_sent = mock_post.call_args.kwargs["headers"]
    assert headers_sent["Authorization"] == f"Bearer {mock_token}"
    assert headers_sent["Content-Type"] == "application/fhir+json"

    # Vous pouvez aussi vérifier le timeout et le champ `data`
    assert mock_post.call_args.kwargs["timeout"] == 30
    assert mock_post.call_args.kwargs["data"] == dummy_payload

def test_upload_bundle_failure_status(mocker, dummy_payload):
    """Code non-200/201 => retourne False."""
    mocker.patch("fhir_custom.bundle.get_token", return_value="tok")
    mock_response = mock.Mock(status_code=500, text="Server error")
    mocker.patch("fhir_custom.bundle.requests.post", return_value=mock_response)

    assert upload_bundle(dummy_payload) is False

def test_upload_bundle_exception(mocker, dummy_payload):
    """Une exception dans requests.post fait remonter False."""
    mocker.patch("fhir_custom.bundle.get_token", return_value="tok")
    mocker.patch("fhir_custom.bundle.requests.post", side_effect=Exception("boom"))
    assert upload_bundle(dummy_payload) is False