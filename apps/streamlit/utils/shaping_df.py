import pandas as pd

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

    # Fallback si pas de valueQuantity : calcul depuis effectivePeriod
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

    # Optionnel : ne garder que les lignes avec un vrai nom de workout
    df = df[df["parameter"].notna()]

    # Tri décroissant
    df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)

    return df