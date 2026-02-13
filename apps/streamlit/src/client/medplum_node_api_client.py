import os
import requests
import redis
import time
import json
from typing import Dict, Generator, Optional, List, Any
import pandas as pd
import streamlit as st

def read_secret_file(path: str) -> Optional[str]:
    if path and os.path.isfile(path):
        with open(path, 'r') as f:
            return f.read().strip()
    return None

class MedplumNodeAPIClient:
    def __init__(self,
                 base_url: Optional[str] = None,
                 redis_host: Optional[str] = None,
                 redis_port: Optional[int] = None,
                 redis_password_file: Optional[str] = None,
                 redis_prefix: str = "medplum_client:"):
        self.base_url = base_url or os.getenv("MEDPLUM_NODE_API_URL", "http://medplum-node-api:3001")
        self.session = requests.Session()
        self.redis = None
        self.redis_prefix = redis_prefix
        redis_host = redis_host or os.getenv("REDIS_HOST")
        redis_port = redis_port or os.getenv("REDIS_PORT")
        if redis_host:
            password = None
            if redis_password_file:
                password = read_secret_file(redis_password_file)
            if not redis_password_file:
                redis_password_file = os.getenv("REDIS_MASTER_PASSWORD_FILE")
                password = read_secret_file(redis_password_file)

            try:
                self.redis = redis.Redis(host=redis_host, port=int(redis_port), password=password, decode_responses=True)
                # test connection
                self.redis.ping()
            except Exception as e:
                print("Warning: cannot connect to Redis:", e)
                self.redis = None

    def _cache_key(self, path: str, params: Dict) -> str:
        params_str = json.dumps(params or {}, sort_keys=True, default=str)
        # use a short hash to reduce key length
        h = abs(hash(params_str)) % (10**12)
        return f"{self.redis_prefix}{path}:{h}"

    def get_observations(
        self,
        params: Dict = None,
        page_size: int = 200,
        max_results: Optional[int] = None,
        timeout: int = 30,
        use_cache: bool = True,
        cache_ttl: int = 300,
    ) -> List[Dict]:

        params = params or {}
        params.setdefault("pageSize", str(page_size))

        cache_key = None
        if self.redis and use_cache:
            cache_key = self._cache_key("/observations", params)
            cached = self.redis.get(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    pass  # cache corrompu → fallback réseau

        url = f"{self.base_url.rstrip('/')}/observations"

        try:
            r = self.session.get(
                url,
                params=params,
                headers={"Accept": "application/json"},
                timeout=timeout,
            )
            r.raise_for_status()
            parsed = r.json()

            results: List[Dict] = []

            if isinstance(parsed, list):
                results = parsed

            elif isinstance(parsed, dict):
                if "entry" in parsed and isinstance(parsed["entry"], list):
                    for e in parsed["entry"]:
                        results.append(e.get("resource", e))
                elif "entries" in parsed and isinstance(parsed["entries"], list):
                    results = parsed["entries"]
                elif "observations" in parsed and isinstance(parsed["observations"], list):
                    results = parsed["observations"]
                else:
                    results = [parsed]
            else:
                return []

            if max_results is not None:
                results = results[:max_results]

            if cache_key and self.redis:
                self.redis.setex(cache_key, cache_ttl, json.dumps(results))

            return results

        except requests.exceptions.RequestException:
            return []
        except Exception:
            return []


    # Helper pour aplatir une Observation courante en colonnes pratiques
    def _extract_observation_flat(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        out['id'] = obs.get('id')
        out['resourceType'] = obs.get('resourceType')
        # subject -> patientId
        subject = obs.get('subject') or {}
        if isinstance(subject, dict):
            out['subject_reference'] = subject.get('reference')
        else:
            out['subject_reference'] = subject
        # try to extract a patient id if "Patient/<id>"
        ref = out['subject_reference']
        if isinstance(ref, str) and ref.startswith("Patient/"):
            out['patientId'] = ref.split("/", 1)[1]
        else:
            out['patientId'] = None
        # code -> coding(s)
        code = obs.get('code') or {}
        out['code_text'] = code.get('text')
        # flatten first coding if exists
        coding0 = None
        if 'coding' in code and isinstance(code['coding'], list) and code['coding']:
            coding0 = code['coding'][0]
            out['code_system'] = coding0.get('system')
            out['code_code'] = coding0.get('code')
            out['code_display'] = coding0.get('display')
        else:
            out['code_system'] = None
            out['code_code'] = None
            out['code_display'] = None
        # category (may be list)
        cat = obs.get('category')
        if isinstance(cat, list) and cat:
            # flatten first category
            first_cat = cat[0]
            if isinstance(first_cat, dict):
                out['category_text'] = first_cat.get('text') or (first_cat.get('coding') or [{}])[0].get('display')
            else:
                out['category_text'] = str(first_cat)
        else:
            out['category_text'] = None
        # effective date/time
        out['effectiveDateTime'] = obs.get('effectiveDateTime') or obs.get('effectivePeriod') or None
        # value: numerous shapes in FHIR Observation
        value = None
        unit = None
        # common keys
        if 'valueQuantity' in obs and isinstance(obs['valueQuantity'], dict):
            q = obs['valueQuantity']
            value = q.get('value')
            unit = q.get('unit') or q.get('code')
        elif 'valueString' in obs:
            value = obs.get('valueString')
        elif 'valueCodeableConcept' in obs:
            vcc = obs.get('valueCodeableConcept') or {}
            if isinstance(vcc, dict):
                # try text or first coding
                value = vcc.get('text') or (vcc.get('coding') or [{}])[0].get('display')
        elif 'valueBoolean' in obs:
            value = obs.get('valueBoolean')
        elif 'valueInteger' in obs:
            value = obs.get('valueInteger')
        elif 'valueRange' in obs:
            value = obs.get('valueRange')
        elif 'valueSampledData' in obs:
            value = obs.get('valueSampledData')
        # fallback: check 'value' at top-level
        elif 'value' in obs:
            value = obs.get('value')
        out['value'] = value
        out['unit'] = unit
        # device
        device = obs.get('device')
        if isinstance(device, dict):
            out['device_reference'] = device.get('reference')
        else:
            out['device_reference'] = device
        # issued / performer / interpretation etc.
        out['issued'] = obs.get('issued')
        perf = obs.get('performer')
        if isinstance(perf, list) and perf:
            out['performer'] = perf[0].get('reference') if isinstance(perf[0], dict) else perf[0]
        else:
            out['performer'] = None

        # retain full raw JSON (useful)
        out['raw'] = obs

        return out

    def observations_to_dataframe(self, params: Dict = None, max_results: Optional[int] = None,
                                  use_cache: bool = True, cache_ttl: int = 300, flatten: bool = True) -> pd.DataFrame:
        """
        Récupère les observations et retourne un pandas.DataFrame.
        flatten=True -> colonnes pratiques (id, patientId, code_text, code_code, value, unit, effectiveDateTime, device_reference, ...)
        flatten=False -> pandas.json_normalize(list_of_obs) (brut)
        """
        observations = self.get_observations(params=params, max_results=max_results, use_cache=use_cache, cache_ttl=cache_ttl)
        if not observations:
            # return empty dataframe with no rows
            return pd.DataFrame()

        if not flatten:
            try:
                df = pd.json_normalize(observations)
                return df
            except Exception as e:
                # fallback simple
                return pd.DataFrame(observations)

        # flatten each observation
        flattened = []
        for obs in observations:
            try:
                flattened.append(self._extract_observation_flat(obs))
            except Exception:
                # on erreur, store raw
                flattened.append({'id': obs.get('id'), 'raw': obs})

        # build dataframe
        df = pd.DataFrame(flattened)
        # Expand 'raw' column optionally (user may want full JSON preserved)
        return df

    # convenience wrapper to match user friendly filters
    def search_observations_list(self,
                                 patient: Optional[str] = None,
                                 category: Optional[str] = None,
                                 startDate: Optional[str] = None,
                                 endDate: Optional[str] = None,
                                 code: Optional[str] = None,
                                 device: Optional[str] = None,
                                 max_results: Optional[int] = None,
                                 **kwargs) -> List[Dict]:
        """
        Wrapper pour construire params de recherche plus lisible.
        patient : id patient (ex: '1234') -> envoyé comme patientId
        category / code / device / startDate / endDate : passés tels quels.
        """
        q = {}
        if patient:
            q['patientId'] = patient
        if category:
            q['category'] = category
        if startDate:
            q['startDate'] = startDate
        if endDate:
            q['endDate'] = endDate
        if code:
            q['code'] = code
        if device:
            q['device'] = device
        q.update(kwargs)
        return self.get_observations(params=q, max_results=max_results)

    def observations_to_dataframe_search(self, patient: Optional[str] = None, category: Optional[str] = None,
                                         startDate: Optional[str] = None, endDate: Optional[str] = None,
                                         code: Optional[str] = None, device: Optional[str] = None,
                                         max_results: Optional[int] = None, use_cache: bool = True,
                                         cache_ttl: int = 300, flatten: bool = True) -> pd.DataFrame:
        """
        Combinaison pratique: build search params and return DataFrame directly.
        """
        params = {}
        if patient:
            params['patientId'] = patient
        if category:
            params['category'] = category
        if startDate:
            params['startDate'] = startDate
        if endDate:
            params['endDate'] = endDate
        if code:
            params['code'] = code
        if device:
            params['device'] = device
        return self.observations_to_dataframe(params=params, max_results=max_results, use_cache=use_cache, cache_ttl=cache_ttl, flatten=flatten)
