import os
import uuid
import json
import logging
from typing import Any, Dict, List
import time

import requests
from fhir.resources.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhir.resources.observation import Observation
from fhir.resources.medication import Medication
from fhir.resources.medicationadministration import MedicationAdministration

from libs.get_medplum_token import get_token
from fhir_custom.observation import to_fhir_observation

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

FHIR_BASE = os.getenv(
    "FHIR_BASE",
    "http://medplum-mesh.medplum.svc.cluster.local:8103/fhir/R4/",
)

HASH_SYSTEM = "https://medplum.phylcero.fr/observation-hash"

# Function to split a list into chunks
def chunk_list(items, chunk_size: int):
    """
    Split a list into chunks.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size doit être > 0")

    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]

# Function to upload a bundle
def upload_bundles_in_chunks(
    items, 
    chunk_size: int = 10, 
    delay_seconds: float = 1
) -> bool:
    """
    Upload a list of items in chunks.
    """
    overall_success = True

    for idx, items_chunk in enumerate(chunk_list(items, chunk_size), start=1):
        bundle = build_bundle_fhir(items_chunk)
        success = upload_bundle(bundle)

        if success:
            logger.info(
                "Sous-bundle %s uploadé avec succès (%s items)",
                idx,
                len(items_chunk),
            )
        else:
            logger.warning(
                "Sous-bundle %s en échec (%s items)",
                idx,
                len(items_chunk),
            )
            overall_success = False

        time.sleep(delay_seconds)

    return overall_success

# Function to upload a bundle
def upload_medicationadministration_bundles_in_chunks(
    items, 
    chunk_size: int = 10, 
    delay_seconds: float = 1
) -> bool:
    """
    Upload a list of items in chunks.
    """
    overall_success = True

    for idx, items_chunk in enumerate(chunk_list(items, chunk_size), start=1):
        bundle = build_bundle_medicationadministration(items_chunk)
        success = upload_bundle(bundle)

        if success:
            logger.info(
                "Sous-bundle %s uploadé avec succès (%s items)",
                idx,
                len(items_chunk),
            )
        else:
            logger.warning(
                "Sous-bundle %s en échec (%s items)",
                idx,
                len(items_chunk),
            )
            overall_success = False

        time.sleep(delay_seconds)

    return overall_success

# Function to extract hash from identifier
def _extract_hash_from_identifier(identifier_list: Any) -> str | None:
    """
    Extracts the hash from an identifier list.
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

# Function to build observation request
def _build_observation_request(obs_hash: str | None) -> BundleEntryRequest:
    """
    Builds a BundleEntryRequest for an Observation.
    """
    request = BundleEntryRequest(
        method="POST",
        url="Observation",
    )

    if obs_hash:
        request.ifNoneExist = f"identifier={HASH_SYSTEM}|{obs_hash}"

    return request

# Function to build medication request
def _build_medication_request(med_hash: str | None) -> BundleEntryRequest:
    """
    Builds a BundleEntryRequest for a Medication.
    """
    request = BundleEntryRequest(
        method="POST",
        url="Medication",
    )

    if med_hash:
        request.ifNoneExist = f"identifier={HASH_SYSTEM}|{med_hash}"

    return request

# Function to build medication request
def _build_medicationadministration_request(med_hash: str | None) -> BundleEntryRequest:
    """
    Builds a BundleEntryRequest for a MedicationAdministration.
    """
    request = BundleEntryRequest(
        method="POST",
        url="MedicationAdministration",
    )

    if med_hash:
        request.ifNoneExist = f"identifier={HASH_SYSTEM}|{med_hash}"

    return request

# Function to clean observation
def _clean_observation_for_create(obs: Observation) -> Observation:
    """
    Clean an Observation for creation.
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

# Function to build bundle
def build_bundle_fhir(observations: List[Observation]) -> Bundle:
    """
    Build a Bundle FHIR transaction from a list of observations.
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

# Function to build bundle
def build_bundle_medication(medication: Medication) -> Bundle:
    """
    Build a Bundle FHIR transaction from a medication.
    """
    bundle = Bundle(
        resourceType="Bundle",
        type="transaction",
        entry=[],
    )

    med_resource = medication[0][0]
    med_hash = _extract_hash_from_identifier(med_resource.identifier)

    entry = BundleEntry(
        fullUrl=f"urn:uuid:{uuid.uuid4()}",
        resource=med_resource,
        request=_build_medication_request(med_hash),
    )
    bundle.entry.append(entry)

    return bundle

# Function to build bundle
def build_bundle_medicationadministration(medicationadministration: MedicationAdministration) -> Bundle:
    """
    Build a Bundle FHIR transaction from a medicationAdministration.
    """
    bundle = Bundle(
        resourceType="Bundle",
        type="transaction",
        entry=[],
    )

    med_resource = medicationadministration[0]
    med_hash = _extract_hash_from_identifier(med_resource.identifier)

    entry = BundleEntry(
        fullUrl=f"urn:uuid:{uuid.uuid4()}",
        resource=med_resource,
        request=_build_medicationadministration_request(med_hash),
    )
    bundle.entry.append(entry)

    return bundle

# Function to build transaction bundle
def build_transaction_bundle(
    observations: List[Dict[str, Any]],
    parent_index: int | None = None,
    children_indices: List[int] | None = None,
) -> Bundle:
    """
    Build a Bundle FHIR transaction from a list of observations.
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

# Function to normalize payload
def _normalize_payload(bundle: Bundle | Dict[str, Any] | str) -> Dict[str, Any]:
    """
    Normalize bundle payload.
    Accept Bundle, dict or string JSON.
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

# Function to summarize transaction response
def _summarize_transaction_response(response_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Summarize transaction response.
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

# Function to log response summary
def _log_response_summary(response_json: Dict[str, Any], http_status: int) -> None:
    """
    Compute and log response summary.
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

# Function to post bundle
def _post_bundle(payload: Dict[str, Any]) -> bool:
    """
    Post bundle to Medplum.
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

# Function to upload bundle
def upload_bundle(bundle: Bundle | Dict[str, Any] | str) -> bool:
    """
    Upload bundle.
    """
    try:
        payload = _normalize_payload(bundle)
    except Exception:
        logger.exception("Impossible de normaliser le bundle avant upload")
        return False

    return _post_bundle(payload)

# Function to upload transaction bundle
def upload_transaction_bundle(bundle: Bundle | Dict[str, Any] | str) -> bool:
    """
    Upload transaction bundle.
    """
    try:
        payload = _normalize_payload(bundle)
    except Exception:
        logger.exception("Impossible de normaliser le transaction bundle avant upload")
        return False

    return _post_bundle(payload)