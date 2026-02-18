import requests
from urllib.parse import urljoin, urlencode
import os
from typing import Optional
import logging
from libs.get_medplum_token import get_token

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("Worker-stream")

FHIR_BASE = os.getenv("FHIR_BASE", "http://medplum-mesh.medplum.svc.cluster.local:8103/fhir/R4/")
MEDPLUM_PATIENT_ID = os.getenv("MEDPLUM_PATIENT_ID")


def build_search_url(base: str, resource_type: str, params: dict) -> str:
    query = urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
    return urljoin(base, resource_type) + "?" + query


def fetch_fhir_observation(
    patient: str,
    payload: Optional[dict] = None
) -> list:
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/fhir+json"
    }

    patient_full = f"Patient/{patient}"
    payload = payload or {}

    category = payload.get("category")
    startDate = payload.get("startDate")
    endDate = payload.get("endDate")
    code = payload.get("code")
    device = payload.get("device")
    tag = payload.get("tag")
    max_records = payload.get("max_records", 1000)
    page_count = payload.get("page_count", 500)

    elements = ",".join([
        "category",
        "code",
        "effectiveDateTime",
        "effectivePeriod",
        "performer",
        "valueQuantity",
        "device",
        "hasMember",
        "component"
    ])

    params = {
        "patient": patient_full,
        "_count": page_count,
        "_elements": elements,
        #"_include": "Observation:has-member"
    }

    if category:
        params["category"] = category
    if code:
        params["code"] = code
    if device:
        params["device"] = device
    if tag:
        params["_tag"] = tag
    if startDate or endDate:
        dates = []
        if startDate:
            dates.append(f"ge{startDate}")
        if endDate:
            dates.append(f"le{endDate}")
        params["date"] = dates if len(dates) > 1 else dates[0]

    # On récupère TOUTES les observations du Bundle (principales + incluses)
    all_observations = []

    url = build_search_url(FHIR_BASE, "Observation", params)
    print(url)
    while url and (max_records is None or len(all_observations) < max_records):
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        bundle = r.json()

        for entry in bundle.get("entry", []):
            resource = entry.get("resource")
            if resource and resource.get("resourceType") == "Observation":
                all_observations.append(resource)

        url = next(
            (l["url"] for l in bundle.get("link", []) if l.get("relation") == "next"),
            None
        )

    # Index : "Observation/{id}" → Observation
    obs_index = {
        f"Observation/{obs['id']}": obs
        for obs in all_observations
        if "id" in obs
    }

    # Résolution des hasMember
    results = []

    for obs in all_observations:
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



if __name__ == "__main__":
    rows = fetch_fhir_observation(
        patient=MEDPLUM_PATIENT_ID,
        payload={
            "category":None,
            "startDate":None,
            "endDate":None,
            "code":None,
            "device":None,
            "tag":"manual_weekly",
            "max_records":50,
            "page_count":200
            }
    )
    print(f"Récupéré {len(rows)} resources")
    print(f"TYPE: {type(rows)}")
    # df = shaping_metrics(rows)
    # print(df.head(20))
