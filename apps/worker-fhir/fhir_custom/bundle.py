import os
import re
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

# FHIR id regex: letters / digits / "-" / "." only, max 64 chars
FHIR_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-.]{1,64}$")


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


def _is_valid_fhir_id(value: str | None) -> bool:
    """
    Vérifie si une valeur est un id FHIR valide.
    """
    return bool(value and FHIR_ID_PATTERN.fullmatch(value))


def _clean_resource_for_create(resource: Observation) -> Observation:
    """
    Nettoie une ressource Observation avant un POST create vers Medplum.

    - retire les ids invalides ou inutiles
    - retire les meta techniques serveur
    - reconstruit un objet Observation propre
    """
    payload = resource.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )

    resource_id = payload.get("id")
    if resource_id and not _is_valid_fhir_id(resource_id):
        logger.warning("Suppression d'un id FHIR invalide avant create: %s", resource_id)
        payload.pop("id", None)

    # Pour un POST create, on laisse le serveur gérer versionId / lastUpdated
    meta = payload.get("meta")
    if isinstance(meta, dict):
        meta.pop("versionId", None)
        meta.pop("lastUpdated", None)
        if not meta:
            payload.pop("meta", None)

    return Observation(**payload)


def _make_entry(resource: Observation, full_url: str | None = None) -> BundleEntry:
    """
    Construit une entrée de Bundle transaction pour une Observation.
    """
    clean_resource = _clean_resource_for_create(resource)
    obs_hash = _extract_hash_from_identifier(clean_resource.identifier)

    # Toujours utiliser un vrai UUID pour un URN interne
    entry_full_url = full_url or f"urn:uuid:{uuid.uuid4()}"

    return BundleEntry(
        fullUrl=entry_full_url,
        resource=clean_resource,
        request=_build_observation_request(obs_hash),
    )


def build_bundle_fhir(observations: List[Observation]) -> Bundle:
    """
    Construit un Bundle transaction à partir d'objets Observation déjà instanciés.

    Version robuste :
    - fullUrl toujours valide
    - ressource nettoyée avant create
    - ifNoneExist appliqué si hash disponible
    """
    bundle = Bundle(
        resourceType="Bundle",
        type="transaction",
        entry=[],
    )

    for obs in observations:
        entry = _make_entry(obs)
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
    - nettoie les ressources avant create
    - applique ifNoneExist sur l'identifier hash
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

        entry = _make_entry(obs_resource, full_url=urn)
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
        try:
            logger.error(
                "Payload envoyé à Medplum:\n%s",
                json.dumps(payload, indent=2, ensure_ascii=False),
            )
        except Exception:
            logger.error("Impossible de sérialiser le payload pour debug.")
        return False


def upload_bundle(bundle: Bundle | Dict[str, Any]) -> bool:
    """
    Upload générique conservé pour compatibilité.
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
    Conservé pour compatibilité, délègue au même uploader central.
    """
    payload = bundle.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )
    return _post_bundle(payload)