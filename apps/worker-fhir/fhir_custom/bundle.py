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

FHIR_BASE = os.getenv("FHIR_BASE", "http://medplum:8103/fhir/R4/")

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
    Build a FHIR transaction bundle with internal URN references.
    """

    bundle = Bundle(
        type="transaction",
        entry=[]
    )

    urns = [f"urn:uuid:{uuid.uuid4()}" for _ in observations]

    # Attach hasMember references if requested
    if parent_index is not None and children_indices:
        observations[parent_index]["hasMember"] = [
            {"reference": urns[i]} for i in children_indices
        ]

    for obs_dict, urn in zip(observations, urns):
        obs_resource = to_fhir_observation(obs_dict)

        entry = BundleEntry(
            fullUrl=urn,
            resource=obs_resource,
            request=BundleEntryRequest(
                method="POST",
                url="Observation"
            )
        )

        bundle.entry.append(entry)

    #logger.info(bundle.model_dump_json(indent=2))
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