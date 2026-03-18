from fhir.resources.observation import Observation
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from typing import Optional, List, Union, Any
from datetime import datetime, timezone
from dateutil import parser
from fhir_custom.range import build_range_validated
from fhir_custom.component import build_components_validated
from fhir_custom.valuequantity import value_quantity
from pydantic_core import from_json
from pathlib import Path
import uuid
import logging
import hashlib

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)  

def build_observation_hash(
    patient_id: str,
    measurement_type: str,
    timestamp: str | datetime,
    value: Optional[str | float | int],
) -> str:
    """
    Makes hash for observation identifier
    """
    patient_id = patient_id.strip().lower()
    print(f"\nType_patient: {type(patient_id)}\n")
    measurement_type = measurement_type.strip().lower()
    print(f"\nType_patient: {type(measurement_type)}\n")
    value_norm = str(value).strip().lower()
    print(f"\nType_patient: {type(value_norm)}\n")
    print(f"\nType_patient: {type(timestamp)}\n")
    
    canonical_string = f"{patient_id}|{measurement_type}|{timestamp}|{value_norm}"
    return hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()

def to_fhir_datetime(value):
    """
    Convert a string or datetime into a FHIR conforming datetime string.
    Returns a string like '2025-09-22T00:00:00+02:00' (or with 'Z' for UTC).
    """
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace(' ', 'T'))
        except ValueError:
            dt = parser.parse(value)
    else:
        dt = value
        
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    iso_str = dt.isoformat(timespec='seconds')
    if iso_str.endswith('+00:00'):
        iso_str = iso_str[:-6] + 'Z'
        
    return iso_str

def _codeable(
    system: Optional[str]=None, 
    code: Optional[str]=None, 
    display: Optional[str]=None, 
    text: Optional[str]=None
) -> dict:
    """
    Create CodeableConcept format to avoid ValidationError
    """
    # CodeableConcept class from fhir.resources
    output = CodeableConcept(
        coding=[
            Coding(
                system=system,
                code=code,
                display=display
            )
        ],
        text=text
    )
    return output

def iso_to_dt(iso: str) -> datetime:
    return parser.isoparse(iso)   

def _coding_list(
    codings: Optional[List]=None,
) -> dict:
    """
    Create Coding format to avoid ValidationError
    Return dict
    """
    coding = []
    if codings:
        for code in codings:
            coding.append({"code": code, "display": code})
    return {"coding": coding}

def _coding_bodysite(
    data: Optional[dict]=None,
) -> dict:
    """
    Create Coding format to avoid ValidationError
    Return dict
    """
    coding = []
    coding.append({
        "system": data.get("system"),
        "code": data.get("code", data.get("display")), 
        "display": data.get("display", data.get("code"))
        })
    return {"coding": coding, "text": data.get("text")}


def _build_obs_args(raw: dict) -> dict:
    """
    Retrieve raw data to build correct Observation request input
    """
    # Mandatory inputs : status, code
    obs_kwargs = {"status": raw.get("status", "final")}
    
    # Add formated datetime if present
    if raw.get("effectiveDateTime") is not None:
        # logger.debug("Making 'effectiveDateTime'")
        obs_kwargs["effectiveDateTime"] = to_fhir_datetime(raw.get("effectiveDateTime"))
        # logger.debug("Making 'effectiveDateTime' ==> OK")
    # Add period time (formated)
    if raw.get("periodstart") is not None and raw.get("periodend") is not None:
        # logger.debug("Making 'effectivePeriod'")
        obs_kwargs["effectivePeriod"] = {"start": to_fhir_datetime(raw.get("periodstart")), "end": to_fhir_datetime(raw.get("periodend"))}
        end = to_fhir_datetime(raw.get("periodend"))
        start = to_fhir_datetime(raw.get("periodstart"))
        delta = iso_to_dt(end) - iso_to_dt(start)
        if raw.get("code_code") == "sleep_analysis":
            raw["value_value"] = delta.total_seconds() / 3600
        # logger.debug(f"Making 'effectivePeriod' ==> OK {obs_kwargs['effectivePeriod']}")
    # Add category if one category args is present    
    if raw.get("cat_system") is not None or raw.get("cat_code") is not None or raw.get("cat_display") is not None or raw.get("cat_text") is not None :
        # logger.debug("Making 'category'")
        obs_kwargs["category"] = [_codeable(system=raw.get("cat_system"), code=raw.get("cat_code"), display=raw.get("cat_display"), text=raw.get("cat_text"))]
        # logger.debug("Making 'category' ==> OK")
    # Add code if one code args in present (mandatory data)    
    if raw.get("code_system") is not None or raw.get("code_code") is not None or raw.get("code_display") is not None or raw.get("code_text") is not None:
        # logger.debug("Making 'code'")
        obs_kwargs["code"] = _codeable(system=raw.get("code_system"), code=raw.get("code_code"), display=raw.get("code_display"), text=raw.get("code_text"))
        # logger.debug("Making 'code' ==> OK")
    # Add valueCodeableConcept if one code args in present (mandatory data)    
    if raw.get("vcc_system") is not None or raw.get("vcc_code") is not None or raw.get("vcc_display") is not None or raw.get("vcc_text") is not None:
        # logger.debug("Making 'code'")
        obs_kwargs["valueCodeableConcept"] = _codeable(system=raw.get("vcc_system"), code=raw.get("vcc_code"), display=raw.get("vcc_display"), text=raw.get("vcc_text"))
        # logger.debug("Making 'valueCodeableConcept' ==> OK")
    # Add subject with mandatory prefix
    if raw.get("patient_id") is not None:
        # logger.debug("Making 'subject'")
        obs_kwargs["subject"] = {"reference": f"Patient/{raw.get('patient_id')}"}
        # logger.debug("Making 'subject' ==> OK")
    # Add performer ID with mandatory prefix    
    if raw.get("performer_id") is not None:
        # logger.debug("Making 'performer'")
        obs_kwargs["performer"] = [{"reference": f"Patient/{raw.get('performer_id')}"}]
        # logger.debug("Making 'performer' ==> OK")
    # Add interpretation if one interpret args is present  
    if raw.get("interpret_system") is not None or raw.get("interpret_code") is not None or raw.get("interpret_display") is not None or raw.get("interpret_text") is not None:
        # logger.debug("Making 'interpretation'")
        obs_kwargs["interpretation"] = [_codeable(system=raw.get("interpret_system"), code=raw.get("interpret_code"), display=raw.get("interpret_display"), text=raw.get("interpret_text"))]
        # logger.debug("Making 'interpretation' ==> OK")
    # Add note if note_text is present (note is a list)    
    if raw.get("note_text") is not None:
        # logger.debug("Making 'note'")
        notes = []
        for note in raw.get("note_text"):
            notes.append({"text": note})
        obs_kwargs["note"] = notes
        # logger.debug("Making 'note' ==> OK")
    # Add bodySite if present (list)    
    if raw.get("bodysite") is not None:
        # logger.debug("Making 'bodySite'")
        obs_kwargs["bodySite"] = _coding_bodysite(data=raw.get("bodysite"))
        # logger.debug("Making 'bodySite' ==> OK")
    # Add valueString if present
    if raw.get("value_string") is not None:
        # logger.debug("Making 'value_string'")
        obs_kwargs["valueString"] = raw.get("value_string") 
        # logger.debug("Making 'value_string' ==> OK")
    # Add method if present     
    if raw.get("method") is not None:
        # logger.debug("Making 'method'")
        obs_kwargs["method"] = _coding_list(codings=raw.get("method"))
        # logger.debug("Making 'method' ==> OK")
    # Add device IF with mandatory prefix if present    
    if raw.get("device_id") is not None:
        # logger.debug("Making 'device'")
        obs_kwargs["device"] = {"reference": f"Device/{raw.get('device_id')}"}
        # logger.debug("Making 'device' ==> OK")
    # Add referenceRange if one args is present    
    if raw.get("range_low") is not None or raw.get("range_high") is not None or raw.get("range_text") is not None:
        # logger.debug("Making 'referenceRange'")
        obs_kwargs["referenceRange"] = build_range_validated(range_low=raw.get("range_low"), range_high=raw.get("range_high"), range_text=raw.get("range_text"))
        # logger.debug("Making 'referenceRange' ==> OK")
    # Add component if present (list)
    if raw.get("component") is not None :
        # logger.debug("Making 'component'")
        obs_kwargs["component"] = build_components_validated(raw=raw.get("component"))
        # logger.debug("Making 'component' ==> OK")
    # Add valueQuantity (main value and unit)    
    if raw.get("value_value") is not None or raw.get("value_unit") is not None :
        # logger.debug("Making 'valueQuantity'")
        obs_kwargs["valueQuantity"] = value_quantity(value=raw.get("value_value"), unit=raw.get("value_unit"))
        # logger.debug("Making 'valueQuantity' ==> OK")  
    # Add tag ==> must be present to filter data for Streamlit tabs
    if raw.get("tag_system") is not None or raw.get("tag_code") is not None :
        # logger.debug("Making 'tag'") 
        obs_kwargs["meta"] = {"tag":[{"system": raw.get("tag_system"), "code": raw.get("tag_code")}]}
        # logger.debug("Making 'tag' ==> OK") 
    # Add original hasMember (maked in class : ) 
    if raw.get("hasMember") is not None:
        obs_kwargs["hasMember"] = raw.get("hasMember")
        
    # Makes hash
    if obs_kwargs["effectiveDateTime"]:
        hash_timestamp = to_fhir_datetime(raw.get("effectiveDateTime"))
    else:
        hash_timestamp = to_fhir_datetime(raw.get("periodstart"))
    obs_hash = build_observation_hash(
            patient_id=raw.get('patient_id'),
            measurement_type=raw.get("code_code"),
            timestamp=hash_timestamp,
            value=raw.get("value_value"),
            )
    
    obs_kwargs["identifier"] = {[{"system": "https://medplum.phylcero.fr/observation-hash", "value": obs_hash}]}
        
    return obs_kwargs
        
def to_fhir_observation(raw: Union[dict, str]) -> Observation:
    """
    Build fhir file from raw dict inputs
    Input : dict or json file
    Return : fhir instance
    """
    # If dict :
    if isinstance(raw, dict):
        data = raw
    
    # If json file name
    elif isinstance(raw, str):
        file_path = Path(raw)
        if not file_path.is_file():
            raise FileNotFoundError(f"Fichier non trouvé : {file_path!s}")

        json_bytes = file_path.read_bytes()         
        try:
            data = from_json(json_bytes)
        except Exception as exc:                     
            raise ValueError(f"Erreur de décodage JSON dans {file_path!s} : {exc}") #from exc

    else:
        raise TypeError("raw doit être un dict ou le chemin d’un fichier JSON.")

    obs_kwargs = _build_obs_args(data)
    return Observation(**obs_kwargs)


def list_to_fhir_observation(raw: List[dict[str, Any]], total_created: int) -> List[Observation]:
    """
    Build fhir file from a list of dict inputs
    Input : list of dict
    Return : list of fhir instance
    """
    if not total_created:
        total_created = 0
    obs_list = []
    
    if isinstance(raw, list):
        for data in raw:
            obs_kwargs = _build_obs_args(data)
            obs_kwargs['id'] = str(uuid.uuid4())
            # logger.debug(f"Added ID on FHIR {total_created}")
            #print(obs_kwargs)
            try:
                obs_list.append(Observation(**obs_kwargs))
            except Exception as e:
                print(f"Validation error : {e}")
            # logger.debug(f"Validation FHIR {total_created} OK !!")
            total_created += 1
        # logger.debug(print(obs_list))        
    else:
        raise TypeError("Raw must be a List.")
    
    return obs_list, total_created