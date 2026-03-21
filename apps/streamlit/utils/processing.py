from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from utils.pain_body_site import PAIN_BODY_SITE_MAP

def process_weekly_data(
    weight: Optional[float] = None,
    heart_rate: Optional[int] = None,
    oxymetry: Optional[int] = None,
    systolic: Optional[int] = None,
    diastolic: Optional[int] = None,
    symptoms: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return JSON-like dict for weekly metrics.
    """
    now = datetime.now(timezone.utc).isoformat()
    metrics: List[Dict[str, Any]] = []

    def add(name: str, datas: List[dict], units: Optional[str] = None):
        if units:
            for data in datas:
                data["units"] = units
        entry: Dict[str, Any] = {"name": name, "type": "weekly", "data": datas}
        metrics.append(entry)

    if weight is not None:
        add("manual_weight", [{"qty": weight, "date": now}], "kg")
    if heart_rate is not None:
        add("manual_heart_rate", [{"qty": heart_rate, "date": now}], "bpm")
    if oxymetry is not None:
        add("manual_oxymetry", [{"qty": oxymetry, "date": now}], "bpm")

    if systolic is not None and diastolic is not None:
        add(
            "manual_bp",
            [
                {
                    "systolic": systolic, 
                    "diastolic": diastolic, 
                    "date": now
                }
            ], 
            "mmHg" 
        )

    if symptoms is not None and symptoms != "":
        add("manual_symptoms", [{"note": symptoms, "date": now}])

    return {"metrics": metrics}

def process_monthly_data(
    calf_left: Optional[float] = None,
    calf_right: Optional[float] = None,
    thigh_left: Optional[float] = None,
    thigh_right: Optional[float] = None,
    waist: Optional[float] = None,
    hips: Optional[float] = None,
    neck: Optional[float] = None,
    comments: Optional[str] = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    metrics: List[Dict[str, Any]] = []

    def add(name: str, datas: List[dict], units: Optional[str] = None):
        if units:
            for data in datas:
                data["units"] = units
        entry: Dict[str, Any] = {"name": name, "type": "monthly", "data": datas}
        metrics.append(entry)

    if calf_left is not None:
        add("manual_calf_left", [{"qty": calf_left, "date": now}], "cm")
    if calf_right is not None:
        add("manual_calf_right", [{"qty": calf_right, "date": now}], "cm")
    if thigh_left is not None:
        add("manual_thigh_left", [{"qty": thigh_left, "date": now}], "cm")
    if thigh_right is not None:
        add("manual_thigh_right", [{"qty": thigh_right, "date": now}], "cm")
    if waist is not None:
        add("manual_waist", [{"qty": waist, "date": now}], "cm")
    if hips is not None:
        add("manual_hips", [{"qty": hips, "date": now}], "cm")   
    if neck is not None:
        add("manual_neck", [{"qty": neck, "date": now}], "cm")   
    if comments is not None:
        add("manual_comments", [{"note": comments, "date": now}])

    return {"metrics": metrics}


def process_force_data(
    quadriceps_left: Optional[float] = None,
    quadriceps_right: Optional[float] = None,
    grip_right: Optional[float] = None,
    grip_left: Optional[float] = None,
    rpe: Optional[int] = None,
    strength_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Return JSON-like dict for force metrics."""
    now = datetime.now(timezone.utc).isoformat()
    metrics: List[Dict[str, Any]] = []

    def add(name: str, datas: List[dict], units: Optional[str] = None):
        if units:
            for data in datas:
                data["units"] = units
        entry: Dict[str, Any] = {"name": name, "type": "force", "data": datas}
        metrics.append(entry)

    if quadriceps_left is not None:
        add("manual_quadriceps_left", [{"qty": quadriceps_left, "date": now}], "N")
    if quadriceps_right is not None:
        add("manual_quadriceps_right", [{"qty": quadriceps_right, "date": now}], "N")
    if grip_right is not None:
        add("manual_grip_right", [{"qty": grip_right, "date": now}], "N")
    if grip_left is not None:
        add("manual_grip_left", [{"qty": grip_left, "date": now}], "N")
    if rpe is not None:
        add("manual_rpe", [{"qty": rpe, "date": now}])
    if strength_notes is not None:
        add("manual_strength_notes", [{"note": strength_notes, "date": now}])

    return {"metrics": metrics}

def _sitebody_code(site) -> dict:
    site_code = PAIN_BODY_SITE_MAP[site]
    return site_code

def process_pain_map(pains: list) -> Dict[str, Any]:
    """
    Return JSON-like dict for pain map.
    """
    metrics: List[Dict[str, Any]] = []

    def add(name: str, datas: List[dict], units: Optional[str] = None):
        for data in datas:
            payload = {}
            site_body = _sitebody_code(data["zone"])
            payload["body_system"] = site_body.get("system")
            payload["body_code"] = site_body.get("code")
            payload["body_display"] = site_body.get("display")
            payload["body_text"] = site_body.get("text")
            payload["value_value"] = data.get("intensity")
            payload["note_text"] = [data.get("note")]
            payload["date"] = data.get("date")
        
            entry: Dict[str, Any] = {"name": name, "data": payload}
            metrics.append(entry)
        
    for pain in pains:
        add("manual_pain", [pain])
            
    return {"metrics": metrics}