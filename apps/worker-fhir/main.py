import os, subprocess
from fastapi import FastAPI, HTTPException, Depends
from datetime import datetime, timezone 
from libs.security import require_scopes
from prometheus_client import make_asgi_app
from pipeline_iphone import iphone_json_pipeline
from pipeline_manual import manual_json_pipeline
from pipeline_spirometer import spirometer_json_pipeline
from pipeline_strength import strength_json_pipeline
from pipeline_medication import medication_json_pipeline


app = FastAPI(title="Health Worker Controller")
app.mount("/metrics", make_asgi_app())

def now_iso(): 
    return datetime.now(timezone.utc).isoformat()

@app.get("/")
def root():
    return {"message": "Worker API ready."}

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "time": now_iso()}
 
# Endpoint running iphone pipeline
@app.get("/run/iphone")
def run_worker_iphone(
    device: dict = Depends(require_scopes(["airflow:iphone"])),
):
    try:
        print(f"Lancement du worker pour {now_iso()}")
        result = iphone_json_pipeline()
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return {"status": "success", "output": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint running manual pipeline    
@app.get("/run/manual")
def run_worker_manual(
    device: dict = Depends(require_scopes(["airflow:manual"])),
):
    try:
        print(f"Lancement du worker pour {now_iso()}")
        result = subprocess.run(["python", "/app/pipeline_manual.py"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return {"status": "success", "output": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint running spirometer pipeline    
@app.get("/run/spirometer")
def run_worker_spirometer(
    device: dict = Depends(require_scopes(["airflow:spirometer"])),
):
    try:
        print(f"Lancement du worker pour {now_iso()}")
        result = subprocess.run(["python", "/app/pipeline_spirometer.py"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return {"status": "success", "output": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint running strength pipeline    
@app.get("/run/strength")
def run_worker_strength(
    device: dict = Depends(require_scopes(["airflow:strength"])),
):
    try:
        print(f"Lancement du worker pour {now_iso()}")
        result = subprocess.run(["python", "/app/pipeline_strength.py"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return {"status": "success", "output": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint running logs transfert    
@app.get("/run/logs")
def run_logs_transfert(
    device: dict = Depends(require_scopes(["fhir:logs"])),
):
    try:
        print(f"Lancement du transfert de logs {now_iso()}")
        result = subprocess.run(["python", "/app/pipeline_logs.py"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return {"status": "success", "output": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Endpoint running medication pipeline    
@app.get("/run/medication")
def run_worker_medication(
    device: dict = Depends(require_scopes(["airflow:medication"])),
):
    try:
        print(f"Lancement du worker pour {now_iso()}")
        result = subprocess.run(["python", "/app/pipeline_medication.py"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return {"status": "success", "output": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    