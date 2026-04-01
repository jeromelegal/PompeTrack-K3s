import pandas as pd

# Function to shape metrics
def shaping_metrics(list_metrics):
    rows = []

    for metric in list_metrics:
        # Common field
        category = None
        if metric.get("category"):
            coding = metric["category"][0].get("coding")
            if coding:
                category = coding[0].get("display")
        timestamp = (
            metric.get("effectiveDateTime")
            or metric.get("effectivePeriod", {}).get("start")
        )
        performer = None
        if metric.get("performer"):
            performer = metric["performer"][0].get("display")
        device = None
        if metric.get("device"):
            device = metric["device"].get("display")

        # Observation with 'component'
        if "component" in metric and metric["component"]:
            for comp in metric["component"]:
                parameter = None
                coding = comp.get("code", {}).get("coding")
                if coding:
                    parameter = coding[0].get("display")
                value = None
                unit = None
                if comp.get("valueQuantity"):
                    value = comp["valueQuantity"].get("value")
                    unit = comp["valueQuantity"].get("unit")
                rows.append({
                    "category": category,
                    "parameter": parameter,
                    "timestamp": timestamp,
                    "performer": performer,
                    "value": value,
                    "unit": unit,
                    "device": device
                })

        # Simple observation
        else:
            parameter = None
            coding = metric.get("code", {}).get("coding")
            if coding:
                parameter = coding[0].get("display")

            value = None
            unit = None
            if metric.get("valueQuantity"):
                value = metric["valueQuantity"].get("value")
                unit = metric["valueQuantity"].get("unit")

            rows.append({
                "category": category,
                "parameter": parameter,
                "timestamp": timestamp,
                "performer": performer,
                "value": value,
                "unit": unit,
                "device": device
            })

    return pd.DataFrame(rows)

full_metric = {'category': [{'coding': [{'display': 'Vitals'}]}], 'code': {'coding': [{'display': 'Heart rate'}]}, 'device': {'display': 'Polar H10'}, 'effectiveDateTime': '2025-01-01T10:00:00Z'}


# Workouts 
def _first_coding(block):
    codings = (block or {}).get("coding") or []
    return codings[0] if codings else {}


def _get_category(obs):
    categories = obs.get("category") or []
    if not categories:
        return None
    coding = _first_coding(categories[0])
    return coding.get("display") or coding.get("code")


def _get_parameter(obs):
    code = obs.get("code") or {}
    if code.get("text"):
        return code["text"]
    coding = _first_coding(code)
    return coding.get("display") or coding.get("code")


def _get_timestamp(obs):
    if obs.get("effectiveDateTime"):
        return obs["effectiveDateTime"]

    period = obs.get("effectivePeriod") or {}
    return period.get("start")


def _get_performer(obs):
    performers = obs.get("performer") or []
    values = [
        p.get("display") or p.get("reference")
        for p in performers
        if p.get("display") or p.get("reference")
    ]
    return ", ".join(values) if values else None


def _get_device(obs):
    device = obs.get("device") or {}
    return device.get("display") or device.get("reference")


def _get_value_and_unit(obs):
    vq = obs.get("valueQuantity") or {}
    return vq.get("value"), vq.get("unit")


def _get_duration_min(obs):
    vq = obs.get("valueQuantity") or {}
    value = vq.get("value")
    unit = (vq.get("unit") or "").strip().lower()

    if value is not None:
        if unit in ("seconds", "second", "sec", "s"):
            return round(float(value) / 60, 1)
        if unit in ("minutes", "minute", "min"):
            return round(float(value), 1)

    period = obs.get("effectivePeriod") or {}
    start = period.get("start")
    end = period.get("end")

    if start and end:
        start_ts = pd.to_datetime(start, utc=True, errors="coerce")
        end_ts = pd.to_datetime(end, utc=True, errors="coerce")
        if pd.notna(start_ts) and pd.notna(end_ts):
            return round((end_ts - start_ts).total_seconds() / 60, 1)

    return None


def df_workouts(list_metrics):
    rows = []

    for obs in list_metrics:
        if obs.get("resourceType") != "Observation":
            continue

        value, unit = _get_value_and_unit(obs)

        rows.append({
            "category": _get_category(obs),
            "parameter": _get_parameter(obs),   # ex: Yoga / Entraînement de Force Fonctionnelle
            "timestamp": _get_timestamp(obs),
            "performer": _get_performer(obs),
            "value": value,                     # valeur du parent, ex: 1153
            "unit": unit,                       # ex: seconds
            "device": _get_device(obs),
            "duration_min": _get_duration_min(obs),
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dt.tz_localize(None)
    df = df[df["parameter"].notna()]
    df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)

    return df

# Stateofminds
def _read_codeable(block):
    if not isinstance(block, dict):
        return None

    if block.get("text"):
        return block["text"]

    coding = _first_coding(block)
    return coding.get("display") or coding.get("code")

def _read_category(obs):
    categories = obs.get("category") or []
    if not categories:
        return None

    return _read_codeable(categories[0])

def _read_timestamp(obs):
    if obs.get("effectiveDateTime"):
        return obs["effectiveDateTime"]

    period = obs.get("effectivePeriod") or {}
    return period.get("start")


def _read_device(obs):
    device = obs.get("device") or {}
    return device.get("display") or device.get("reference")


def _read_performer(obs):
    performers = obs.get("performer") or []
    values = [
        p.get("display") or p.get("reference")
        for p in performers
        if p.get("display") or p.get("reference")
    ]
    return ", ".join(values) if values else None


def _read_quantity(obs):
    vq = obs.get("valueQuantity") or {}
    return vq.get("value"), vq.get("unit")


def _read_interpretation(node):
    """
    Try different representations
    """
    interpretations = node.get("interpretation") or []
    values = []

    for item in interpretations:
        val = _read_codeable(item)
        if val:
            values.append(val)

    return ", ".join(values) if values else None


def _read_component_value(component):
    """
    Try different representations.
    """
    interp = _read_interpretation(component)
    if interp:
        return interp

    if "valueString" in component:
        return component.get("valueString")

    if "valueCodeableConcept" in component:
        return _read_codeable(component.get("valueCodeableConcept"))

    if "valueQuantity" in component:
        return (component.get("valueQuantity") or {}).get("value")

    if "valueInteger" in component:
        return component.get("valueInteger")

    if "valueBoolean" in component:
        return component.get("valueBoolean")

    return None


def _read_components(obs):
    """
    Try different representations
    """
    out = {}

    for comp in obs.get("component", []) or []:
        comp_name = _read_codeable(comp.get("code"))
        if not comp_name:
            continue

        key = comp_name.strip().lower().replace(" ", "_")
        out[key] = _read_component_value(comp)

    return out


def _normalize_text(value):
    if value is None:
        return None
    return str(value).replace("_", " ").strip()


def _split_csv_tokens(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []

    items = [x.strip() for x in str(value).split(",")]
    return [x for x in items if x]


def df_stateofminds(list_metrics):
    rows = []

    for obs in list_metrics:
        if obs.get("resourceType") != "Observation":
            continue

        parameter = _read_codeable(obs.get("code"))
        score, unit = _read_quantity(obs)
        interpretation = _read_interpretation(obs)
        components = _read_components(obs)

        rows.append({
            "id": obs.get("id"),
            "category": _read_category(obs),
            "parameter": parameter,                         # daily_mood / momentary_emotion
            "timestamp": _read_timestamp(obs),
            "performer": _read_performer(obs),
            "score": score,
            "unit": unit,
            "interpretation": _normalize_text(interpretation),
            "associations": components.get("associations"),
            "labels": components.get("labels"),
            "device": _read_device(obs),
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dt.tz_localize(None)
    df["score"] = pd.to_numeric(df["score"], errors="coerce")

    df["parameter"] = df["parameter"].apply(_normalize_text)
    df["interpretation"] = df["interpretation"].apply(_normalize_text)

    df["association_list"] = df["associations"].apply(_split_csv_tokens)
    df["label_list"] = df["labels"].apply(_split_csv_tokens)

    df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)
    return df