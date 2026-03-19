import uuid
import os
from libs.get_medplum_token import get_token
from fhir.resources.bundle import Bundle, BundleEntry
from fhir.resources.bundle import BundleEntryRequest
from fhir.resources.observation import Observation
from fhir_custom.observation import to_fhir_observation
from typing import Dict, Any, List
import requests
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

FHIR_BASE = os.getenv("FHIR_BASE", "http://medplum-mesh.medplum.svc.cluster.local:8103/fhir/R4/")
HASH_SYSTEM = "https://medplum.phylcero.fr/observation-hash"

def _extract_hash_from_identifier(identifier_list: Any) -> str | None:
    """
    Extrait la valeur du hash depuis identifier[*] si le system correspond à HASH_SYSTEM.
    Compatible avec des objets FHIR Pydantic ou des dicts.
    """
    if not identifier_list:
        return None

    for ident in identifier_list:
        if isinstance(ident, dict):
            ident_system = ident.get("system")
            ident_value = ident.get("value")
        else:
            ident_system = getattr(ident, "system", None)
            ident_value = getattr(ident, "value", None)

        if ident_system == HASH_SYSTEM and ident_value:
            return ident_value

    return None

def _build_observation_request(obs_hash: str | None) -> BundleEntryRequest:
    """
    Construit la requête FHIR pour une Observation.
    Ajoute ifNoneExist si un hash est disponible pour éviter les doublons.
    """
    request = BundleEntryRequest(
        method="POST",
        url="Observation",
    )

    if obs_hash:
        request.ifNoneExist = f"identifier={HASH_SYSTEM}|{obs_hash}"

    return request

def build_bundle_fhir(observations: List[Observation]) -> Bundle:
    """
    Construit un Bundle transaction à partir d'objets Observation déjà instanciés.

    Cette fonction est conservée pour compatibilité avec l'ancien pipeline,
    mais elle applique maintenant aussi la déduplication via ifNoneExist.
    """
    bundle = Bundle(
        resourceType="Bundle",
        type="transaction",
        entry=[],
    )

    for obs in observations:
        obs_id = getattr(obs, "id", None) or str(uuid.uuid4())
        obs_hash = _extract_hash_from_identifier(getattr(obs, "identifier", None))

        entry = BundleEntry(
            fullUrl=f"urn:uuid:{obs_id}",
            resource=obs,
            request=_build_observation_request(obs_hash),
        )
        bundle.entry.append(entry)

    return bundle

def build_transaction_bundle(
    observations: List[Dict[str, Any]],
    parent_index: int | None = None,
    children_indices: List[int] | None = None,
) -> Bundle:
    """
    Construit un Bundle transaction à partir d'observations brutes (dict).

    - ajoute hasMember sur le parent si demandé
    - transforme chaque dict en ressource FHIR Observation
    - applique ifNoneExist sur l'identifier hash pour éviter les doublons Medplum
    """
    bundle = Bundle(type="transaction", entry=[])
    urns = [f"urn:uuid:{uuid.uuid4()}" for _ in observations]

    children_set = set(children_indices or [])

    if parent_index is not None and children_indices:
        observations[parent_index]["hasMember"] = [
            {"reference": urns[i]} for i in children_indices
        ]

    parent_context = observations[parent_index] if parent_index is not None else None

    for idx, (obs_dict, urn) in enumerate(zip(observations, urns)):
        ctx = parent_context if idx in children_set else None
        obs_resource = to_fhir_observation(obs_dict, parent_context=ctx)

        obs_hash = _extract_hash_from_identifier(obs_resource.identifier)

        entry = BundleEntry(
            fullUrl=urn,
            resource=obs_resource,
            request=_build_observation_request(obs_hash),
        )
        bundle.entry.append(entry)

    return bundle

def _post_bundle(payload: Dict[str, Any]) -> bool:
    """
    Point unique d'upload vers Medplum.
    """
    try:
        token = get_token()
        headers = {
            "Content-Type": "application/fhir+json",
            "Authorization": f"Bearer {token}",
        }

        response = requests.post(
            FHIR_BASE,
            json=payload,
            headers=headers,
            timeout=30,
        )

        logger.info("Medplum response status: %s", response.status_code)
        logger.info("Medplum response body: %s", response.text)

        response.raise_for_status()
        logger.info("Bundle uploadé avec succès")
        return True

    except Exception:
        logger.exception("Erreur lors de l'upload du Bundle")
        return False


def upload_bundle(bundle: Dict[str, Any] | Bundle) -> bool:
    """
    Upload générique conservé pour compatibilité avec l'ancien pipeline.

    Accepte soit :
    - un objet Bundle FHIR
    - un dict JSON déjà sérialisé
    """
    if isinstance(bundle, Bundle):
        payload = bundle.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        )
    else:
        payload = bundle

    return _post_bundle(payload)




def upload_transaction_bundle(bundle: Bundle) -> bool:
    """
    Upload d'un Bundle transaction.
    Conservé pour compatibilité, mais délègue au même uploader central.
    """
    payload = bundle.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )
    return _post_bundle(payload)