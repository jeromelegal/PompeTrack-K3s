import os
from utils.strength_metrics import pipeline_metrics
from libs.minio_requests import get_object_list, get_object_json, move_object
import logging

logger = logging.getLogger("Worker-fhir")
logging.basicConfig(level=logging.INFO)

BUCKET_STRENGTH = "raw-strength"
BUCKET_PROCESSED = "processed-fhir"

def strength_json_pipeline():
    """
    Pipeline 'strength' :
    1 - Retrieve file list from 'bucket_manual'
    2 - Transform data in FHIR_file and upload file to Medplum-server
    3 - Move raw_file to bucket_processed
    4 - Upload FHIR_file to bucket_processed with metadata
    """
    logger.info("Début du pipeline strength_json")
    objects_list = get_object_list(bucket=BUCKET_STRENGTH)
    logger.info(f"Liste des objets dans le bucket : {objects_list}")

    if not objects_list:
        logger.error(f"[WARN] No file got from bucket {BUCKET_STRENGTH}")
        return False

    success = False

    for obj in objects_list:
        logger.info(f"Traitement de l'objet : {obj}")

        json_file = get_object_json(bucket=BUCKET_STRENGTH, object_name=obj)
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
                        source_bucket=BUCKET_STRENGTH,
                        destination_bucket=BUCKET_PROCESSED
                    )
                except Exception as e:
                    logger.error(f"Erreur pendant le déplacement de l'objet dnas Minio : {e}")
                    raise
                logger.info(f"Object moved in processed-fhir bucket.")
                success = True
            else:
                logger.error(f"Erreur de pipeline_metrics sur {obj}")
        except Exception as e:
            logger.error(f"Fail in process ({obj}): {e}")
            raise
    return success



if __name__ == "__main__":
    result = strength_json_pipeline()
    logger.info(f"Pipeline is {result}")
