from __future__ import annotations
import json
from typing import Dict, Any, Mapping, List, Iterable
import os, copy
from dateutil import parser
import logging
import re, unicodedata
from pathlib import Path
from fhir_codes.severity_levels_code import SEVERITY_LEVELS
from fhir_codes.symptoms_code import SYMPTOMS_CODE

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_NUMERIC_STR_RE = re.compile(r'[+\-]?(\d+(\.\d*)?|\.\d+)([eE][+\-]?\d+)?')
TEMPLATE_PATH = "templates"
METADATA_PATH = "metadatas"
FHIR_BASE = os.getenv("FHIR_BASE", "http://medplum-mesh.medplum.svc.cluster.local:8103/fhir/R4")
MEDPLUM_PATIENT_ID = os.getenv("MEDPLUM_PATIENT_ID")
MEDPLUM_DEVICE_ID_IPHONE_GARTH = os.getenv("MEDPLUM_DEVICE_ID_IPHONE_GARTH")
MEDPLUM_DEVICE_ID_SPRIROMETER = os.getenv("MEDPLUM_DEVICE_ID_SPRIROMETER")
MEDPLUM_DEVICE_ID_STREAMLIT = os.getenv("MEDPLUM_DEVICE_ID_STREAMLIT")

# Workouts specifics
raw = os.getenv("NEED_SUBOBSERVATIONS", "Yoga")
NEED_SUBOBSERVATIONS = [x.strip() for x in raw.split(",")]
workouts_keywords = os.getenv("TRAINING", "entraînement")
TRAINING = [x.strip() for x in workouts_keywords.split(",")]

# Replacing keywords
WORKOUT_NAME_MAP = {
    "Yoga": "yoga",
    "Entraînement de Force Fonctionnelle": "workouts",
    "Musculation": "strength_training",
}

# Function to normalize 
def normalize_name(raw_name: str) -> str:
    """
    Convert a human-readable workout name into a safe technical identifier.
    """
    name = raw_name.strip()

    # mapping explicite prioritaire
    if name in WORKOUT_NAME_MAP:
        return WORKOUT_NAME_MAP[name]

    # fallback générique
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")

    return name

# Function to fill the template
class FillResource:
    """
    Replace every string value in a template that matches a key in
    'sources' with the corresponding value
    """

    def __init__(self, *sources: Mapping[str, Any]):
        self.sources = sources  # tuple of dicts
        
    @staticmethod
    def _get_by_path(data: Mapping[str, Any], path: str) -> Any | None:
        current = data
        for part in path.split("."):
            if not isinstance(current, Mapping):
                return None
            if part not in current:
                return None
            current = current[part]
        return current

    def _resolve(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._resolve(v) for v in obj]
        if isinstance(obj, tuple):
            return tuple(self._resolve(v) for v in obj)
        if isinstance(obj, set):
            return {self._resolve(v) for v in obj}
        if isinstance(obj, str):
            return self._lookup(obj)
        return obj
    
    def _lookup(self, key: str) -> Any:
        for src in self.sources:
            # Try path:  "a.b.c"
            if "." in key:
                value = self._get_by_path(src, key)
                if value is not None:
                    return value

            # Else simple dict
            result = self._search_in_dict(src, key)
            if result is not None:
                return result

        return key

    @staticmethod
    def _search_in_dict(d: Mapping[str, Any], key: str) -> Any | None:
        if key in d:
            return d[key]
        for v in d.values():
            if isinstance(v, Mapping):
                r = FillResource._search_in_dict(v, key)
                if r is not None:
                    return r
        return None
    
    def update_codeable(
        self,
        *,
        codeable_dict: Mapping[str, Mapping[str, Any]],
        keyword: str | None,
        prefix: str,
        fields: Iterable[str] = ("system", "code", "display", "text"),
        default: Mapping[str, Any] | None = None,
    ) -> None:
        """
        Add :
          {f"{prefix}_system": "...", f"{prefix}_code": "...", ...}
        """
        if not keyword:
            return

        payload = codeable_dict.get(keyword) or default
        if not payload:
            return

        extra: dict[str, Any] = {}
        for f in fields:
            if f in payload and payload[f] is not None:
                extra[f"{prefix}_{f}"] = payload[f]

        if extra:
            self.update_sources(extra)
    
    def build(self, template: Mapping[str, Any]) -> Mapping[str, Any]:
        clone = copy.deepcopy(template)
        return self._resolve(clone)

    def update_sources(self, *extra: Mapping[str, Any]) -> None:
        self.sources += extra

# Basic class for metrics
class CreatePreFHIR:
    def __init__(
        self,
        payload: Dict[str, Any],
        device_id: int = MEDPLUM_DEVICE_ID_IPHONE_GARTH,
        round_digits: int = 2,
        round_only_value_paths: bool = True,
        round_strings: bool = False
    ):
        raw_name = payload.get("name")
        technical_name = normalize_name(raw_name)
        self.device_id = device_id
        self.raw_name = raw_name 
        self.name = technical_name 
        self.metadata_file = f"meta_{self.name}.json"
        self.metadata = self._load_metadata(self.metadata_file )
        self.data = self._retrieve_data(payload)
        # self.name = self._retrieve_name(payload)
        self.units = self._retrieve_units(payload)
        self.template = self._load_template(self.metadata)
        self.constants = self._load_constants(self.metadata)
        self.error_report = []

        self.round_digits = round_digits
        self.round_only_value_paths = bool(round_only_value_paths)
        self.round_strings = bool(round_strings)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"CreatePreFHIR instance created for '{self.name}'")

    @staticmethod
    def _load_metadata(metadata_file) -> Dict[str, Any]:
        # metadata_file = f"meta_{payload.get('name')}.json"
        with open(os.path.join("/app", METADATA_PATH, metadata_file), "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _retrieve_name(self, payload: Dict[str, Any]) -> str:
        """ Return `name`  from payload """
        return payload.get("name")
    
    def _retrieve_units(self, payload: Dict[str, Any]) -> str:
        """ Return `units`  from payload """
        return payload.get("units")
        
    def _load_template(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """ Retrieve template file name in *metadata* and open it """
        template_file = metadata["template"]
        # template_path = TEMPLATE_PATH + template_file
        with open(os.path.join("/app", TEMPLATE_PATH, template_file), "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_constants(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """ Return 'constants' dict from *metadata* """
        const = metadata.get("constants", {})
        if not isinstance(const, dict):
            self.logger.error(
                f"'constants' section is not a dict: {type(const).__name__}"
            )
            return {}
        return const
    
    @staticmethod
    def _retrieve_data(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ Return `data`  from metadata """
        try:
            return metadata["data"]
        except: 
            return metadata
                  
    def _looks_like_date(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        if re.match(r"^\d{4}-\d{2}-\d{2}", value):
            return True
        return bool(
            re.search(r"[T ]\d{2}:\d{2}(:\d{2})?", value)
            and re.search(r"([+*-]\d{2}:?\d{2}|Z)$", value)
        )

    def _format_datetime(self, date_str: str):
        try:
            dt = parser.parse(date_str)
            return dt.isoformat()
        except Exception:
            try:
                if isinstance(date_str, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                    dt = parser.parse(date_str + "T00:00:00")
                    return dt.isoformat()
            except Exception:
                pass
            self.logger.error(f"Date format error : {date_str} - invalid format")
            self.error_report.append({
                "type": "date",
                "message": f"Not a valid format : {date_str}",
                "data": date_str
            })
            return None

    # Rounding helpers
    def _is_numeric_string(self, s: str) -> bool:
        return bool(_NUMERIC_STR_RE.fullmatch(s.strip()))

    def _should_round_for_path(self, target_path: str) -> bool:
        if self.round_digits is None:
            return False
        if not self.round_only_value_paths:
            return True
        # round only when path points to a numeric value field (heuristic)
        lower = target_path.lower()
        return ('qty' in lower) or ('value' in lower) or ('valuequantity' in lower)

    def _normalize_numeric(self, value: Any, target_path: str = "") -> Any:
        """ Round value if necessary """
        if not self._should_round_for_path(target_path):
            return value

        # int -> nothing to do
        if isinstance(value, int):
            return value

        # float -> round
        if isinstance(value, float):
            rounded = round(value, self.round_digits)
            if float(rounded).is_integer():
                return int(rounded)
            return rounded

        # numeric strings
        if self.round_strings and isinstance(value, str) and self._is_numeric_string(value):
            try:
                f = float(value)
            except Exception:
                return value
            rounded = round(f, self.round_digits)
            if float(rounded).is_integer():
                return int(rounded)
            return rounded

        return value
    
    def _normalize(self, value: Any, key: str = "") -> Any:
        """
        Recursively normalise `value`, applying:
        - date formatting
        - numeric normalisation
        """
        try:
            if isinstance(value, str) and self._looks_like_date(value):
                return self._format_datetime(value)

            value = self._normalize_numeric(value, key)

        except Exception as exc:
            raise

        if isinstance(value, dict):
            return {k: self._normalize(v, k) for k, v in value.items()}

        if isinstance(value, list):
            return [self._normalize(v, key) for v in value]

        return value
    
    # Render
    def render(self) -> List[Dict[str, Any]]:
        """
        Normalise self.data, fill template for “resource”
        """
        rendered: List[Dict[str, Any]] = []

        try:
            normalized_data = self._normalize(self.data)

            if isinstance(normalized_data, dict):
                entries = [normalized_data]
            else:                              
                entries = normalized_data

            for entry in entries:
                try:
                    resource = copy.deepcopy(self.template)
                except Exception as exc:
                    try:
                        resource = json.loads(json.dumps(self.template))
                    except Exception:
                        raise RuntimeError("Unable to deep copy template object") from exc

                try:
                    filler = FillResource(
                        self.constants,
                        entry,
                        {
                            "patient_id": MEDPLUM_PATIENT_ID,
                            "device_id": self.device_id,
                        },
                        {"units": self.units}
                    )
                    resource = filler.build(resource)
                except Exception as exc:
                    msg = f"Error in filling template for key={entry.get('data_key','unknown')}."
                    self.logger.error(msg + " " + str(exc))
                    self.error_report.append({"type": "write", "message": msg + " " + str(exc)})

                rendered.append(resource)

        except Exception as master_exc:

            self.logger.exception("Erreur générale lors de la normalisation et du rendu : %s",
                                    master_exc)
            self.error_report.append(
                {"type": "general", "message": str(master_exc), "data": self.data}
            )

        return rendered
 
    
# Class for workouts
class CreatePreFHIR_workouts():

    def process(
    self,
    payload: Dict[str, Any]
) -> Dict[str, Any]:

        observations: List[Dict[str, Any]] = []
        children_indices: List[int] = []

        parent_creator = CreatePreFHIR(payload=payload)

        parent_obs = parent_creator.render()[0]
        observations.append(parent_obs)
        parent_index = 0

        # Contexte parent réutilisable pour les sous-observations
        parent_context = {
            "patient_id": MEDPLUM_PATIENT_ID,
            "device_id": MEDPLUM_DEVICE_ID_IPHONE_GARTH,
            "parent_start": payload.get("start"),
            "parent_end": payload.get("end"),
            "workout_id": payload.get("id"),
            "workout_name": payload.get("name"),
        }

        if payload.get("heartRateData"):
            for subobs in payload["heartRateData"]:
                sub_payload = {
                    "name": "heartratedata",
                    "units": subobs.get("units") or payload.get("units"),
                    "data": [{
                        "Avg": subobs.get("Avg"),
                        "date": subobs.get("date") or payload.get("start"),
                        "patient_id": parent_context["patient_id"],
                        "device_id": parent_context["device_id"],
                        "parent_start": parent_context["parent_start"],
                        "parent_end": parent_context["parent_end"],
                        "workout_id": parent_context["workout_id"],
                        "workout_name": parent_context["workout_name"],
                    }]
                }

                creator = CreatePreFHIR(sub_payload, round_digits=1)
                sub_obs = creator.render()[0]
                children_indices.append(len(observations))
                observations.append(sub_obs)

        return observations, parent_index, children_indices

# Class with name for template name
class CreatePreFHIR_name(CreatePreFHIR):
    def __init__(
        self,
        payload: Dict[str, Any],
        name: str,
        round_digits: int = 2,
        round_only_value_paths: bool = True,
        round_strings: bool = False
    ):
        if not isinstance(payload, dict):
            raise TypeError("payload doit être un dictionnaire")

        if not isinstance(name, str) or not name.strip():
            raise ValueError("name doit être une chaîne non vide")

        # Copie défensive
        payload = payload.copy()
        
        if "name" in payload:
            raise ValueError("Le champ 'name' ne doit pas être présent dans le payload")

        # Injection contrôlée du name
        payload["name"] = name

        # Lancement du workflow standard
        super().__init__(
            payload=payload,
            round_digits=round_digits,
            round_only_value_paths=round_only_value_paths,
            round_strings=round_strings
        )

class CreatePreFHIR_symptoms:
    """
    Class for symptoms
    """
    TEMPLATE_NAME = "iphone_symptom"

    def process(self, symptom: Dict[str, Any]):
        payload = copy.deepcopy(symptom)
        creator = CreatePreFHIR_name(payload=payload, name=self.TEMPLATE_NAME)
        rendered = []

        normalized_data = creator._normalize(creator.data)
        entries = [normalized_data] if isinstance(normalized_data, dict) else normalized_data

        for entry in entries:
            resource = copy.deepcopy(creator.template)

            filler = FillResource(
                creator.constants,
                entry,
                MEDPLUM_IDS,
                {"units": creator.units},
            )
            filler.update_codeable(
                codeable_dict=SYMPTOMS_CODE,
                keyword=entry.get("symptom"),
                prefix="code",
            )
            filler.update_codeable(
                codeable_dict=SEVERITY_LEVELS,
                keyword=entry.get("severity"),
                prefix="vcc",
            )

            rendered.append(filler.build(resource))

        observations = rendered
        parent_index = 0
        children_indices = []
        return observations, parent_index, children_indices
    
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO) 
    
    with open("symptoms.json", "r") as f:
        payload = json.load(f)

    creator = CreatePreFHIR_workouts()
    resource = creator.process(payload)

    
    
    