from fastapi import FastAPI, HTTPException, Depends
from datetime import datetime, timezone 
from typing import Callable
from libs.security import require_scopes
from prometheus_client import make_asgi_app
from pipeline_iphone import iphone_json_pipeline
from pipeline_manual import manual_json_pipeline
from pipeline_spirometer import spirometer_json_pipeline
from pipeline_strength import strength_json_pipeline
from pipeline_medication import medication_json_pipeline
from pipeline_logs import transfert_logs_pipeline

app = FastAPI(title="Health Worker Controller")
app.mount("/metrics", make_asgi_app())

def now_iso(): 
    return datetime.now(timezone.utc).isoformat()


def run_pipeline_endpoint(name: str, pipeline_func: Callable[[], bool]) -> dict[str, str]:
    print(f"Lancement du worker {name} pour {now_iso()}")
    try:
        success = pipeline_func()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"{name} pipeline failed or no object processed",
        )

    return {
        "status": "success",
        "output": f"{name} pipeline completed",
    }

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
    return run_pipeline_endpoint("iphone", iphone_json_pipeline)

# Endpoint running manual pipeline    
@app.get("/run/manual")
def run_worker_manual(
    device: dict = Depends(require_scopes(["airflow:manual"])),
):
    return run_pipeline_endpoint("manual", manual_json_pipeline)

# Endpoint running spirometer pipeline    
@app.get("/run/spirometer")
def run_worker_spirometer(
    device: dict = Depends(require_scopes(["airflow:spirometer"])),
):
    return run_pipeline_endpoint("spirometer", spirometer_json_pipeline)

# Endpoint running strength pipeline    
@app.get("/run/strength")
def run_worker_strength(
    device: dict = Depends(require_scopes(["airflow:strength"])),
):
    return run_pipeline_endpoint("strength", strength_json_pipeline)

# Endpoint running logs transfert    
@app.get("/run/logs")
def run_logs_transfert(
    device: dict = Depends(require_scopes(["fhir:logs"])),
):
    return run_pipeline_endpoint("logs", transfert_logs_pipeline)
    
# Endpoint running medication pipeline    
@app.get("/run/medication")
def run_worker_medication(
    device: dict = Depends(require_scopes(["airflow:medication"])),
):
    return run_pipeline_endpoint("medication", medication_json_pipeline)
    
