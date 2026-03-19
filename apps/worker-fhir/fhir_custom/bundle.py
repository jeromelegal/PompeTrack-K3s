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

def chunk_list(items, chunk_size: int):
    if chunk_size <= 0:
        raise ValueError("chunk_size doit être > 0")

    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]

def upload_bundles_in_chunks(observations, chunk_size: int = 10) -> bool:
    """
    Découpe une liste d'Observation en petits bundles et les upload un par un.
    """
    overall_success = True

    for idx, obs_chunk in enumerate(chunk_list(observations, chunk_size), start=1):
        bundle = build_bundle_fhir(obs_chunk)
        success = upload_bundle(bundle)

        if success:
            logger.info(
                "Sous-bundle %s uploadé avec succès (%s observations)",
                idx,
                len(obs_chunk),
            )
        else:
            logger.warning(
                "Sous-bundle %s en échec (%s observations)",
                idx,
                len(obs_chunk),
            )
            overall_success = False

    return overall_success

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
    - applique ifNoneExist pour éviter les doublons
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


def _summarize_transaction_response(response_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Résume une réponse transaction-response Medplum.
    """
    summary = {
        "total_entries": 0,
        "success_count": 0,
        "throttled_count": 0,
        "error_count": 0,
        "statuses": {},
        "error_messages": [],
    }

    entries = response_json.get("entry", [])
    summary["total_entries"] = len(entries)

    unique_errors = set()

    for entry in entries:
        response = entry.get("response", {})
        status = str(response.get("status", "unknown"))
        summary["statuses"][status] = summary["statuses"].get(status, 0) + 1

        if status.startswith("20"):
            summary["success_count"] += 1
            continue

        outcome = response.get("outcome", {})
        issues = outcome.get("issue", [])

        is_throttled = False
        for issue in issues:
            code = issue.get("code")
            details = issue.get("details", {}).get("text")

            if code == "throttled" or details == "Too Many Requests":
                is_throttled = True

            if details:
                unique_errors.add(details)

        if is_throttled:
            summary["throttled_count"] += 1
        else:
            summary["error_count"] += 1

    summary["error_messages"] = sorted(unique_errors)[:5]
    return summary


def _log_response_summary(response_json: Dict[str, Any], http_status: int) -> None:
    """
    Log compact et lisible de la réponse Medplum.
    """
    summary = _summarize_transaction_response(response_json)

    logger.info(
        "Medplum HTTP=%s | bundle entries=%s | ok=%s | throttled=%s | errors=%s | statuses=%s",
        http_status,
        summary["total_entries"],
        summary["success_count"],
        summary["throttled_count"],
        summary["error_count"],
        summary["statuses"],
    )

    if summary["error_messages"]:
        logger.warning("Medplum messages: %s", summary["error_messages"])


def _post_bundle(payload: Dict[str, Any]) -> bool:
    """
    Point unique d'upload vers Medplum.
    Version sobre : pas de retry automatique lourd, juste un résumé clair.
    """
    try:
        token = get_token()
        headers = {
            "Content-Type": "application/fhir+json",
            "Authorization": f"Bearer {token}",
        }

        bundle_entries = payload.get("entry", [])
        logger.info("Uploading bundle with %s entries", len(bundle_entries))

        response = requests.post(
            FHIR_BASE,
            json=payload,
            headers=headers,
            timeout=30,
        )

        try:
            response_json = response.json()
        except Exception:
            logger.error("Réponse non JSON de Medplum (HTTP %s)", response.status_code)
            response.raise_for_status()
            return False

        _log_response_summary(response_json, response.status_code)

        if response.status_code >= 400:
            response.raise_for_status()

        summary = _summarize_transaction_response(response_json)

        if summary["throttled_count"] > 0:
            logger.warning(
                "Bundle partiellement refusé par throttling: %s/%s observations en 429",
                summary["throttled_count"],
                summary["total_entries"],
            )

        if summary["error_count"] > 0:
            logger.error(
                "Bundle avec erreurs: %s OK, %s throttled, %s erreurs",
                summary["success_count"],
                summary["throttled_count"],
                summary["error_count"],
            )
            return False

        if summary["throttled_count"] > 0:
            return False

        logger.info(
            "Bundle uploadé avec succès: %s/%s observations OK",
            summary["success_count"],
            summary["total_entries"],
        )
        return True

    except Exception:
        logger.exception("Erreur lors de l'upload du Bundle")
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