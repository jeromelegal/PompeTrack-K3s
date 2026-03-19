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

def build_bundle_fhir(observations: List[Observation]) -> Bundle:
    bundle = Bundle(
        resourceType="Bundle", 
        type="transaction", 
        entry=[]
        )

    for obs in observations:
        obs_id = getattr(obs, "id", None) or str(uuid.uuid4())

        entry = BundleEntry(
            fullUrl=f"urn:uuid:{obs_id}",
            resource=obs,
            request={"method": "POST", "url": "Observation"}
        )
        bundle.entry.append(entry)

    return bundle

def upload_bundle(bundle: Dict[str, Any]) -> bool:
    """
    Upload bundle FHIR to Medplum.
    """
    try:
        token = get_token()
        headers = {
            "Content-Type": "application/fhir+json",
            "Authorization": f"Bearer {token}"
        }
        response = requests.post(
            FHIR_BASE,
            data=bundle,
            headers=headers,
            timeout=30
        )
        if response.status_code in [200, 201]:
            logger.info("Bundle uploadé avec succès")
            return True
        else:
            logger.error(f"Erreur d'upload : {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Erreur lors de l'upload : {str(e)}")
        return False

def build_transaction_bundle(
    observations: List[Dict[str, Any]],
    parent_index: int | None = None,
    children_indices: List[int] | None = None,
) -> Bundle:
    """
    Construit un Bundle FHIR de type transaction pour des Observations.

    - ajoute les références hasMember du parent vers les enfants
    - crée des fullUrl internes en URN pour les références intra-bundle
    - transforme chaque dict en ressource FHIR Observation
    - évite les doublons dans Medplum avec ifNoneExist basé sur l'identifier hash
    """

    bundle = Bundle(type="transaction", entry=[])
    urns = [f"urn:uuid:{uuid.uuid4()}" for _ in observations]

    children_set = set(children_indices or [])

    # Ajoute les références hasMember sur l'observation parent
    if parent_index is not None and children_indices:
        observations[parent_index]["hasMember"] = [
            {"reference": urns[i]} for i in children_indices
        ]

    # Contexte parent gardé en fallback de sécurité
    parent_context = observations[parent_index] if parent_index is not None else None

    for idx, (obs_dict, urn) in enumerate(zip(observations, urns)):
        # Fallback parent uniquement pour les enfants
        ctx = parent_context if idx in children_set else None

        obs_resource = to_fhir_observation(obs_dict, parent_context=ctx)

        # Récupère le hash stocké dans identifier
        obs_hash = None
        for ident in (obs_resource.identifier or []):
            ident_system = getattr(ident, "system", None)
            ident_value = getattr(ident, "value", None)

            if ident_system == HASH_SYSTEM and ident_value:
                obs_hash = ident_value
                break

        request = BundleEntryRequest(
            method="POST",
            url="Observation",
        )

        # Conditional create Medplum :
        # crée seulement si aucune Observation avec ce couple system|value n'existe déjà
        if obs_hash:
            request.ifNoneExist = f"identifier={HASH_SYSTEM}|{obs_hash}"

        entry = BundleEntry(
            fullUrl=urn,
            resource=obs_resource,
            request=request,
        )

        bundle.entry.append(entry)

    return bundle

def upload_transaction_bundle(bundle: Bundle) -> bool:
    try:
        token = get_token()
        headers = {
            "Content-Type": "application/fhir+json",
            "Authorization": f"Bearer {token}"
        }

        payload = bundle.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True
        )

        response = requests.post(
            FHIR_BASE,
            json=payload,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()
        logger.info("Bundle uploadé avec succès")
        return True

    except Exception:
        logger.exception("Erreur lors de l'upload du Bundle")
        return False