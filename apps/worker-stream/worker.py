import os
import logging
from typing import Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from libs.get_medplum_token import get_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Worker-stream")

FHIR_BASE = os.getenv(
    "FHIR_BASE",
    "http://medplum-mesh.medplum.svc.cluster.local:8103/fhir/R4/"
)
MEDPLUM_PATIENT_ID = os.getenv("MEDPLUM_PATIENT_ID")

DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 120

# Function to build the search URL
def build_search_url(base: str, resource_type: str, params: dict) -> str:
    """
    Build the search URL based on the base URL, resource type, and query parameters.
    """
    query = urlencode(
        {k: v for k, v in params.items() if v is not None},
        doseq=True
    )
    return f"{base.rstrip('/')}/{resource_type}?{query}"

# Function to create a requests session
def create_session() -> requests.Session:
    """
    Create a requests session with retry logic.
    """
    retry = Retry(
        total=6,
        connect=6,
        read=6,
        status=6,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=10,
        pool_maxsize=10,
    )

    session = requests.Session()
    session.trust_env = False
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Function to get the resource base URL
def get_resource_base_url(internal_base: str, resource_type: str) -> str:
    return f"{internal_base.rstrip('/')}/{resource_type}"

# Function to rewrite the 'next' URL
def rewrite_next_to_internal_resource_base(
    next_url: Optional[str],
    internal_base: str,
    resource_type: str,
) -> Optional[str]:
    """
    Keep the 'next' URL.
    If it contains a query string, 
    rewrite it to the internal resource base URL with the query string.
      {FHIR_BASE}/{resource_type}?...
    """
    if not next_url:
        return None

    parsed_next = urlparse(next_url)

    if not parsed_next.query:
        logger.warning("URL 'next' sans query string: %s", next_url)
        return None

    resource_base = get_resource_base_url(internal_base, resource_type)
    rewritten = f"{resource_base}?{parsed_next.query}"

    if rewritten != next_url:
        logger.warning(
            "Réécriture de l'URL de pagination : %s -> %s",
            next_url,
            rewritten,
        )

    return rewritten

# Function to get a bundle page
def get_bundle_page(
    session: requests.Session,
    url: str,
    headers: dict,
    timeout: tuple[int, int] = (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT),
) -> dict:
    """
    Get a bundle page.
    """
    try:
        r = session.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise RuntimeError(f"Erreur réseau lors du GET {url}: {e}") from e

    if r.status_code >= 400:
        body = r.text[:1000] if r.text else ""
        raise RuntimeError(
            f"Erreur HTTP {r.status_code} sur {url}. "
            f"Réponse partielle: {body}"
        )

    try:
        return r.json()
    except ValueError as e:
        raise RuntimeError(
            f"Réponse non JSON sur {url}. "
            f"Content-Type={r.headers.get('Content-Type')} "
            f"Body(partiel)={r.text[:500] if r.text else ''}"
        ) from e

# Function to fetch FHIR observations
def fetch_fhir_observation(
    patient: str,
    payload: Optional[dict] = None
) -> list[dict]:
    """
    Fetch FHIR observations.
    """
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/fhir+json",
    }

    session = create_session()

    patient_full = f"Patient/{patient}"
    payload = payload or {}

    category = payload.get("category")
    start_date = payload.get("startDate")
    end_date = payload.get("endDate")
    code = payload.get("code")
    device = payload.get("device")
    tag = payload.get("tag")

    max_records = payload.get("max_records", 1000)
    page_count = int(payload.get("page_count", 100))
    max_pages = int(payload.get("max_pages", 1000))

    if page_count <= 0:
        page_count = 100

    elements = ",".join([
        "id",
        "category",
        "code",
        "effectiveDateTime",
        "effectivePeriod",
        "performer",
        "valueQuantity",
        "device",
        "hasMember",
        "component",
        "interpretation",
    ])

    params = {
        "patient": patient_full,
        "_count": page_count,
        "_elements": elements,
    }

    if category:
        params["category"] = category
    if code:
        params["code"] = code
    if device:
        params["device"] = device
    if tag:
        params["_tag"] = tag
    if start_date or end_date:
        dates = []
        if start_date:
            dates.append(f"ge{start_date}")
        if end_date:
            dates.append(f"le{end_date}")
        params["date"] = dates if len(dates) > 1 else dates[0]

    all_observations: list[dict] = []
    seen_obs_refs: set[str] = set()
    visited_urls: set[str] = set()

    resource_type = "Observation"
    url = build_search_url(FHIR_BASE, resource_type, params)

    page_number = 0

    while url and (max_records is None or len(all_observations) < max_records):
        page_number += 1

        if page_number > max_pages:
            raise RuntimeError(
                f"Pagination interrompue : plus de {max_pages} pages parcourues."
            )

        if url in visited_urls:
            raise RuntimeError(f"Boucle de pagination détectée sur l'URL : {url}")
        visited_urls.add(url)

        logger.info("GET page %s: %s", page_number, url)
        bundle = get_bundle_page(session, url, headers=headers)

        page_obs_count = 0
        for entry in bundle.get("entry", []):
            resource = entry.get("resource")
            if not resource or resource.get("resourceType") != "Observation":
                continue

            obs_id = resource.get("id")
            obs_ref = f"Observation/{obs_id}" if obs_id else None

            if obs_ref and obs_ref in seen_obs_refs:
                continue

            if obs_ref:
                seen_obs_refs.add(obs_ref)

            all_observations.append(resource)
            page_obs_count += 1

            if max_records is not None and len(all_observations) >= max_records:
                break

        logger.info(
            "Page %s récupérée: %s observations (cumul=%s)",
            page_number,
            page_obs_count,
            len(all_observations),
        )

        if max_records is not None and len(all_observations) >= max_records:
            break

        raw_next_url = next(
            (l.get("url") for l in bundle.get("link", []) if l.get("relation") == "next"),
            None,
        )

        url = rewrite_next_to_internal_resource_base(
            raw_next_url,
            FHIR_BASE,
            resource_type,
        )

    if max_records is not None:
        all_observations = all_observations[:max_records]

    obs_index = {
        f"Observation/{obs['id']}": obs
        for obs in all_observations
        if "id" in obs
    }

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
                "valueQuantity": member_obs.get("valueQuantity"),
            })

        if resolved_members:
            obs["resolvedHasMember"] = resolved_members

        results.append(obs)

    return results

# Function to fetch FHIR medication
def fetch_fhir_medication(
    payload: Optional[dict] = None
) -> list[dict]:
    """
    Fetch FHIR medication.
    """
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/fhir+json",
    }

    session = create_session()

    payload = payload or {}
    code = payload.get("code")

    max_records = payload.get("max_records", 1000)
    page_count = int(payload.get("page_count", 100))
    max_pages = int(payload.get("max_pages", 1000))

    if page_count <= 0:
        page_count = 100

    elements = ",".join([
        "id",
        "code",
    ])

    params = {
        "_count": page_count,
        "_elements": elements,
    }

    if code:
        params["code"] = code

    all_medications: list[dict] = []
    seen_med_refs: set[str] = set()
    visited_urls: set[str] = set()

    resource_type = "Medication"
    url = build_search_url(FHIR_BASE, resource_type, params)

    page_number = 0

    while url and (max_records is None or len(all_medications) < max_records):
        page_number += 1

        if page_number > max_pages:
            raise RuntimeError(
                f"Pagination interrompue : plus de {max_pages} pages parcourues."
            )

        if url in visited_urls:
            raise RuntimeError(f"Boucle de pagination détectée sur l'URL : {url}")
        visited_urls.add(url)

        logger.info("GET page %s: %s", page_number, url)
        bundle = get_bundle_page(session, url, headers=headers)

        page_med_count = 0
        for entry in bundle.get("entry", []):
            resource = entry.get("resource")
            if not resource or resource.get("resourceType") != "Medication":
                continue

            med_id = resource.get("id")
            med_ref = f"Medication/{med_id}" if med_id else None

            if med_ref and med_ref in seen_med_refs:
                continue

            if med_ref:
                seen_med_refs.add(med_ref)

            all_medications.append(resource)
            page_med_count += 1

            if max_records is not None and len(all_medications) >= max_records:
                break

        logger.info(
            "Page %s récupérée: %s Medications (cumul=%s)",
            page_number,
            page_med_count,
            len(all_medications),
        )

        if max_records is not None and len(all_medications) >= max_records:
            break

        raw_next_url = next(
            (l.get("url") for l in bundle.get("link", []) if l.get("relation") == "next"),
            None,
        )

        url = rewrite_next_to_internal_resource_base(
            raw_next_url,
            FHIR_BASE,
            resource_type,
        )

    if max_records is not None:
        all_medications = all_medications[:max_records]

    results = []
    for med in all_medications:
        resolved_members = []
        results.append(med)

    return results

if __name__ == "__main__":
    rows = fetch_fhir_observation(
        patient=MEDPLUM_PATIENT_ID,
        payload={
            "category": None,
            "startDate": "2025-12-21",
            "endDate": "2026-03-21",
            "code": None,
            "device": None,
            "tag": "metrics",
            "max_records": 500,
            "page_count": 50,
            "max_pages": 1000,
        },
    )
    print(f"Récupéré {len(rows)} resources")
    print(f"TYPE: {type(rows)}")