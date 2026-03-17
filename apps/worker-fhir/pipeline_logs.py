import os
from libs.minio_requests import upload_object_into_bucket
import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger("Worker-fhir")
logging.basicConfig(level=logging.INFO)

BUCKET_LOGS = "fhir-logs"

def transfert_logs_pipeline():
    """
    Pipeline 'logs' :
    1 - transfert "error_report.json" to minio bucket : 'fhir-logs'
    """
    logger.info("Début du pipeline transfert_logs")

    success = False
        
    file_path = os.path.join("/app", "error_report.json")
    
    now = datetime.now()
    filename = f"logs_fhir_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S_%f')}.log"
    
    try:
        logger.info(f"Upload file :")
        result = upload_object_into_bucket(file_path=file_path,
                                           bucket=BUCKET_LOGS,
                                           filename=filename
                                           )
        success = True

    except Exception as e:
        logger.error(f"Fail in process upload error_report.json to minio.")
        raise
    
    return success


if __name__ == "__main__":
    result = transfert_logs_pipeline()
    logger.info(f"Pipeline is {result}")
    if result is True:
        # Clear json file
        with open('data.json', 'w') as f: 
            json.dump([], f)
