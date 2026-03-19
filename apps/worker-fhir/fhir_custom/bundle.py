import os
import uuid
import json
import logging
from typing import Any, Dict, List

import requests
from fhir.resources.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhir.resources.observation import Observation

from libs.get_medplum_token import get_token
from fhir_custom.observation import to_fhir_observation

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

FHIR_BASE = os.getenv(
    "FHIR_BASE",
    "http://medplum-mesh.medplum.svc.cluster.local:8103/fhir/R4/",
)

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


def _clean_observation_for_create(obs: Observation) -> Observation:
    """
    Nettoie une Observation avant create :
    - supprime id pour laisser Medplum le générer
    - supprime versionId / lastUpdated si présents
    - conserve les données métier utiles
    """
    payload = obs.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )

    payload.pop("id", None)

    meta = payload.get("meta")
    if isinstance(meta, dict):
        meta.pop("versionId", None)
        meta.pop("lastUpdated", None)
        if not meta:
            payload.pop("meta", None)

    return Observation(**payload)


def build_bundle_fhir(observations: List[Observation]) -> Bundle:
    """
    Construit un Bundle FHIR de type transaction à partir d'objets Observation.
    Utilisé pour les bundles simples sans relation parent/enfants.
    """
    bundle = Bundle(
        resourceType="Bundle",
        type="transaction",
        entry=[],
    )

    for obs in observations:
        clean_obs = _clean_observation_for_create(obs)
        obs_hash = _extract_hash_from_identifier(clean_obs.identifier)

        entry = BundleEntry(
            fullUrl=f"urn:uuid:{uuid.uuid4()}",
            resource=clean_obs,
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
    Construit un Bundle FHIR transaction à partir d'observations brutes.

    - ajoute hasMember sur le parent si parent_index et children_indices sont fournis
    - convertit les dicts en ressources FHIR Observation
    - applique le conditional create via ifNoneExist
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
        clean_obs = _clean_observation_for_create(obs_resource)
        obs_hash = _extract_hash_from_identifier(clean_obs.identifier)

        entry = BundleEntry(
            fullUrl=urn,
            resource=clean_obs,
            request=_build_observation_request(obs_hash),
        )
        bundle.entry.append(entry)

    return bundle


def _normalize_payload(bundle: Bundle | Dict[str, Any] | str) -> Dict[str, Any]:
    """
    Normalise tout type d'entrée en dict JSON FHIR.

    Accepte :
    - Bundle Pydantic
    - dict
    - string JSON
    """
    if isinstance(bundle, Bundle):
        payload = bundle.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        )
    elif isinstance(bundle, dict):
        payload = bundle
    elif isinstance(bundle, str):
        try:
            payload = json.loads(bundle)
        except json.JSONDecodeError as exc:
            raise ValueError("Le bundle string n'est pas un JSON valide.") from exc
    else:
        raise TypeError(
            f"Type de bundle non supporté: {type(bundle).__name__}. "
            "Attendu: Bundle, dict ou str JSON."
        )

    if not isinstance(payload, dict):
        raise TypeError(
            f"Payload normalisé invalide: {type(payload).__name__}. "
            "Un objet JSON (dict) était attendu."
        )

    return payload


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
        try:
            logger.error(
                "Payload envoyé à Medplum:\n%s",
                json.dumps(payload, indent=2, ensure_ascii=False),
            )
        except Exception:
            logger.error("Impossible de sérialiser le payload pour debug.")
        return False


def upload_bundle(bundle: Bundle | Dict[str, Any] | str) -> bool:
    """
    Upload générique robuste.
    Accepte Bundle, dict ou string JSON.
    """
    try:
        payload = _normalize_payload(bundle)
    except Exception:
        logger.exception("Impossible de normaliser le bundle avant upload")
        return False

    return _post_bundle(payload)


def upload_transaction_bundle(bundle: Bundle | Dict[str, Any] | str) -> bool:
    """
    Upload transaction bundle.
    Même comportement que upload_bundle, gardé pour compatibilité.
    """
    try:
        payload = _normalize_payload(bundle)
    except Exception:
        logger.exception("Impossible de normaliser le transaction bundle avant upload")
        return False

    return _post_bundle(payload)