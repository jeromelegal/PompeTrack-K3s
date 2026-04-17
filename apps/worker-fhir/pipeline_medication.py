import os
import time
from utils.medication_create import pipeline_medication
from libs.minio_requests import get_object_list, get_object_json, move_object
import logging

from metrics.metrics_medication import (
    MEDICATION_PIPELINE_RUN_TOTAL,
    MEDICATION_PIPELINE_RUN_SUCCESS_TOTAL,
    MEDICATION_PIPELINE_RUN_FAILURE_TOTAL,
    MEDICATION_PIPELINE_OBJECT_TOTAL,
    MEDICATION_PIPELINE_OBJECT_SUCCESS_TOTAL,
    MEDICATION_PIPELINE_OBJECT_FAILURE_TOTAL,
    MEDICATION_PIPELINE_DURATION_SECONDS,
    MEDICATION_PIPELINE_LAST_SUCCESS_UNIXTIME
)

logger = logging.getLogger("Worker-fhir")
logging.basicConfig(level=logging.INFO)

BUCKET_MEDICATION = "raw-medication"
BUCKET_PROCESSED = "processed-fhir"

# Function to process medication metrics
@MEDICATION_PIPELINE_DURATION_SECONDS.time()
def medication_json_pipeline():
    """
    Pipeline 'medication' :
    1 - Retrieve file list from 'bucket_medication'
    2 - Transform data in FHIR_file and upload file to Medplum-server
    3 - Move raw_file to bucket_processed
    4 - Upload FHIR_file to bucket_processed with metadata
    """
    MEDICATION_PIPELINE_RUN_TOTAL.inc()
    logger.info("Début du pipeline medication_json")
    objects_list = get_object_list(bucket=BUCKET_MEDICATION)
    logger.info(f"Liste des objets dans le bucket : {objects_list}")

    if not objects_list:
        logger.error(f"[WARN] No file got from bucket {BUCKET_MEDICATION}")
        return False

    success = False

    for obj in objects_list:
        MEDICATION_PIPELINE_OBJECT_TOTAL.inc()
        logger.info(f"Traitement de l'objet : {obj}")

        json_file = get_object_json(bucket=BUCKET_MEDICATION, object_name=obj)
        if not json_file:
            logger.warning(f"[WARN] Nothing to process in object : {obj}")
            raise

        try:
            logger.info(f"Processing file : {obj}")
            result_metrics = pipeline_medication(json_file)

            if result_metrics:
                logger.info(f"Upload status is OK.")
                try:
                    move_object(
                        object_name=obj,
                        source_bucket=BUCKET_MEDICATION,
                        destination_bucket=BUCKET_PROCESSED
                    )
                except Exception as e:
                    logger.error(f"Erreur pendant le déplacement de l'objet dans Minio : {e}")
                    raise
                logger.info(f"Object moved in processed-fhir bucket.")
                MEDICATION_PIPELINE_OBJECT_SUCCESS_TOTAL.inc()
                MEDICATION_PIPELINE_LAST_SUCCESS_UNIXTIME.set_to_current_time()
                success = True
            else:
                logger.error(f"Erreur de pipeline_medication sur {obj}")
        except Exception as e:
            logger.error(f"Fail in process ({obj}): {e}")
            MEDICATION_PIPELINE_OBJECT_FAILURE_TOTAL.inc()
            raise

    if success:
        MEDICATION_PIPELINE_RUN_SUCCESS_TOTAL.inc()
    else:
        MEDICATION_PIPELINE_RUN_FAILURE_TOTAL.inc() 

    return success



if __name__ == "__main__":
    result = medication_json_pipeline()
    logger.info(f"Pipeline is {result}")
