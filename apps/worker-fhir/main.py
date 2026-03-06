import os, subprocess
from fastapi import FastAPI, HTTPException, Depends
from datetime import datetime, timezone 
from libs.security import require_scopes

app = FastAPI(title="Health Worker Controller")

def now_iso(): return datetime.now(timezone.utc).isoformat()

@app.get("/")
def root():
    return {"message": "Worker API ready."}

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "time": now_iso()}
 
@app.get("/run/iphone")
def run_worker_iphone(
    device: dict = Depends(require_scopes(["airflow:iphone"])),
):
    try:
        print(f"Lancement du worker pour {now_iso()}")
        result = subprocess.run(["python", "/app/pipeline_iphone.py"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return {"status": "success", "output": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
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
    