from fastapi import FastAPI, Depends, Body
from datetime import datetime, timezone
from typing import Optional
from worker import fetch_fhir_observation, fetch_fhir_medication
from fastapi.responses import JSONResponse
import json
from libs.security import require_scopes

app = FastAPI(title="Health Worker Controller")

def now_iso(): return datetime.now(timezone.utc).isoformat()

@app.get("/")
def root():
    return {"message": "Worker API ready."}

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "time": now_iso()}

# Endpoint to fetch observation 
@app.post("/data/observation/{patient_id}")
def fetch_observation(
    patient_id: str,
    payload: Optional[dict] = Body(...),
    device: dict = Depends(require_scopes(["stream:fhir"])),
):
    try:
        results = fetch_fhir_observation(patient_id, payload)
        data = {"data": results}
        return data
    except (RuntimeError, ValueError) as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    
# Endpoint to fetch medication
@app.post("/data/medication")
def fetch_medication(
    payload: Optional[dict] = Body(...),
    device: dict = Depends(require_scopes(["stream:fhir"])),
):
    try:
        results = fetch_fhir_medication(payload)
        data = {"data": results}
        return data
    except (RuntimeError, ValueError) as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)