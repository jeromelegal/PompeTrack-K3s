from fastapi import FastAPI, HTTPException, Depends
import os, subprocess
from datetime import datetime, timezone 
from libs.security import require_scopes

SCOPES = "working:sqlite"

app = FastAPI(title="Sqlite worker")

def now_iso(): return datetime.now(timezone.utc).isoformat()

@app.get("/")
def root():
    return {"message": "Sqlite worker ready."}

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "time": now_iso()}
 
@app.get("/run/spirometer")
def run_worker_sqlite(
    device: dict = Depends(require_scopes(["airflow:spirometer"])),
):
    try:
        print(f"Lancement du worker pour {now_iso()}")
        result = subprocess.run(["python", "extract_spirometry.py"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return {"status": "success", "output": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))