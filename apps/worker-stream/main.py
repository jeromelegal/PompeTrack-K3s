from fastapi import FastAPI, Depends, Body
from datetime import datetime, timezone
from typing import Optional
from worker import fetch_fhir_observation
from fastapi.responses import JSONResponse
import json

app = FastAPI(title="Health Worker Controller")

def now_iso(): return datetime.now(timezone.utc).isoformat()

@app.get("/")
def root():
    return {"message": "Worker API ready."}

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "time": now_iso()}
 
@app.post("/data/observation/{patient_id}")
def fetch_obseration(
    patient_id: str,
    payload: Optional[dict] = Body(...),
):
    try:
        results = fetch_fhir_observation(patient_id, payload)
        data = {"data": results}
        return data
    except (RuntimeError, ValueError) as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)