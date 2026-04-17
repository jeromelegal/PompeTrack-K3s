import os
import time
from utils.manual_metrics import pipeline_metrics
from libs.minio_requests import get_object_list, get_object_json, move_object
import logging

from metrics.metrics_manual import (
    MANUAL_PIPELINE_RUN_TOTAL,
    MANUAL_PIPELINE_RUN_SUCCESS_TOTAL,
    MANUAL_PIPELINE_RUN_FAILURE_TOTAL,
    MANUAL_PIPELINE_OBJECT_TOTAL,
    MANUAL_PIPELINE_OBJECT_SUCCESS_TOTAL,
    MANUAL_PIPELINE_OBJECT_FAILURE_TOTAL,
    MANUAL_PIPELINE_DURATION_SECONDS,
    MANUAL_PIPELINE_LAST_SUCCESS_UNIXTIME
)

logger = logging.getLogger("Worker-fhir")
logging.basicConfig(level=logging.INFO)

BUCKET_MANUAL = "raw-manual"
BUCKET_PROCESSED = "processed-fhir"

# Function to process manual metrics
@MANUAL_PIPELINE_DURATION_SECONDS.time()
def manual_json_pipeline():
    """
    Pipeline 'manual' :
    1 - Retrieve file list from 'bucket_manual'
    2 - Transform data in FHIR_file and upload file to Medplum-server
    3 - Move raw_file to bucket_processed
    4 - Upload FHIR_file to bucket_processed with metadata
    """
    MANUAL_PIPELINE_RUN_TOTAL.inc()
    logger.info("Début du pipeline manual_json")
    objects_list = get_object_list(bucket=BUCKET_MANUAL)
    logger.info(f"Liste des objets dans le bucket : {objects_list}")

    if not objects_list:
        logger.error(f"[WARN] No file got from bucket {BUCKET_MANUAL}")
        return False

    success = False

    for obj in objects_list:
        MANUAL_PIPELINE_OBJECT_TOTAL.inc()
        logger.info(f"Traitement de l'objet : {obj}")

        json_file = get_object_json(bucket=BUCKET_MANUAL, object_name=obj)
        if not json_file:
            logger.warning(f"[WARN] Nothing to process in object : {obj}")
            raise

        try:
            logger.info(f"Processing file : {obj}")
            result_metrics = pipeline_metrics(json_file)

            if result_metrics:
                logger.info(f"Upload status is OK.")
                try:
                    move_object(
                        object_name=obj,
                        source_bucket=BUCKET_MANUAL,
                        destination_bucket=BUCKET_PROCESSED
                    )
                except Exception as e:
                    logger.error(f"Erreur pendant le déplacement de l'objet dnas Minio : {e}")
                    raise
                logger.info(f"Object moved in processed-fhir bucket.")
                MANUAL_PIPELINE_OBJECT_SUCCESS_TOTAL.inc()
                MANUAL_PIPELINE_LAST_SUCCESS_UNIXTIME.set_to_current_time()
                success = True
            else:
                logger.error(f"Erreur de pipeline_metrics sur {obj}")
        except Exception as e:
            logger.error(f"Fail in process ({obj}): {e}")
            MANUAL_PIPELINE_OBJECT_FAILURE_TOTAL.inc()
            raise

    if success:
        MANUAL_PIPELINE_RUN_SUCCESS_TOTAL.inc()
    else:
        MANUAL_PIPELINE_RUN_FAILURE_TOTAL.inc() 

    return success



if __name__ == "__main__":
    result = manual_json_pipeline()
    logger.info(f"Pipeline is {result}")
