# requirements: pip install requests
import requests
from urllib.parse import urljoin, urlencode
from datetime import datetime
import os
from typing import Optional

API_BASE = "https://medplum.phylcero.fr/fhir/R4/"  # base FHIR endpoint (self-hosted change accordingly)
OAUTH_TOKEN_URL = "https://medplum.phylcero.fr/oauth2/token"  # change si self-hosted
#CLIENT_ID = os.getenv("STREAMLIT_ID", "")
#CLIENT_SECRET = os.getenv("STREAMLIT_SECRET", "")
PATIENT_ID = "c9dea642-a030-4484-8b17-3cc0d0fdb9b0"

def get_token(client_id: str, client_secret: str, token_url: str=OAUTH_TOKEN_URL) -> str:
    data = {"grant_type": "client_credentials"}
    resp = requests.post(token_url, data=data, auth=(client_id, client_secret))
    resp.raise_for_status()
    return resp.json()["access_token"]

def build_search_url(base: str, resource_type: str, params: dict) -> str:
    # params already contain FHIR search keys (patient, category, code, date, device, _count, etc.)
    query = urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
    return urljoin(base, resource_type) + "?" + query

def fetch_fhir_search(resource_type: str,
                      token: str,
                      patient: str = None,
                      category: Optional[str] = None,
                      startDate: Optional[str] = None,
                      endDate: Optional[str] = None,
                      code: Optional[str] = None,
                      device: Optional[str] = None,
                      max_records: Optional[int] = 10000,
                      page_count: int = 500) -> list:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"}
    results = []
    # Build initial search params: FHIR date uses e.g. date=geYYYY-MM-DD
    params = {
        "patient": patient,
        "category": category,
        "code": code,
        "device": device,
        "_count": page_count
    }
    if startDate:
        params["date"] = f"ge{startDate}"
    if endDate:
        # If date already set, we should combine: FHIR allows multiple date params; add second as 'date=le...'
        # We'll add a second param by making the 'date' value a list; urlencode with doseq=True handles it.
        if "date" in params:
            params["date"] = [params["date"], f"le{endDate}"]
        else:
            params["date"] = f"le{endDate}"

    url = build_search_url(API_BASE, resource_type, params)
    while url and len(results) < max_records:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        bundle = r.json()
        entries = bundle.get("entry", [])
        for e in entries:
            results.append(e.get("resource"))
            if len(results) >= max_records:
                break
        # find next link
        url = None
        for l in bundle.get("link", []):
            if l.get("relation") == "next":
                url = l.get("url")
                break
    return results

# EXEMPLE D'UTILISATION
if __name__ == "__main__":
    token = get_token(CLIENT_ID, CLIENT_SECRET)
    # Exemple : requêter Observations pour patient id 'Patient/123', category 'laboratory', période 2025-01-01..2025-11-30
    rows = fetch_fhir_search(
        resource_type="Observation",
        token=token,
        patient=PATIENT_ID,
        category="activity",   # dépend du resourceType : 'category' existe sur Observation
        startDate="2025-01-01",
        endDate="2025-11-30",
        code=None,  # exemple LOINC code (system|code) ou juste code
        device=None,
        max_records=5000,
        page_count=200
    )
    print(f"Récupéré {len(rows)} resources")
