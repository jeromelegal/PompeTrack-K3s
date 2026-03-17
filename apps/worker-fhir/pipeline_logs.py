import os
from libs.minio_requests import upload_object_into_bucket
import logging
import json

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
        
    if not error_json:
        logger.warning(f"[WARN] Nothing to process in object : error_report.json")
        raise

    file_path = os.path.join("app", "error_report.json")

    try:
        logger.info(f"Upload file :")
        result = upload_object_into_bucket(file_path=file_path,
                                           bucket=BUCKET_LOGS,
                                           scope="fhir:logs")
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
