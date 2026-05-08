import os
import json
import time
from utils.iphone_metrics import pipeline_metrics
from utils.iphone_workouts import pipeline_workouts
from utils.iphone_stateofminds import pipeline_stateofminds
from utils.iphone_symptoms import pipeline_symptoms
from utils.iphone_medicationadministrations import pipeline_medications
from libs.minio_requests import get_object_list, get_object_json, move_object
import logging

from metrics.metrics_iphone import (
    UNKNOWN_CATEGORY_TOTAL,
    IPHONE_PIPELINE_RUN_TOTAL,
    IPHONE_PIPELINE_RUN_SUCCESS_TOTAL,
    IPHONE_PIPELINE_RUN_FAILURE_TOTAL,
    IPHONE_PIPELINE_OBJECT_TOTAL,
    IPHONE_PIPELINE_OBJECT_SUCCESS_TOTAL,
    IPHONE_PIPELINE_OBJECT_FAILURE_TOTAL,
    IPHONE_SUBPIPELINE_RUN_TOTAL,
    IPHONE_SUBPIPELINE_SUCCESS_TOTAL,
    IPHONE_SUBPIPELINE_FAILURE_TOTAL,
    SPLIT_JSON_DURATION_SECONDS,
    IPHONE_PIPELINE_DURATION_SECONDS,
    IPHONE_SUBPIPELINE_DURATION_SECONDS,
    IPHONE_PIPELINE_LAST_SUCCESS_UNIXTIME,
)

logger = logging.getLogger("Worker-fhir")
logging.basicConfig(level=logging.INFO)

BUCKET_RAW = "raw-iphone"
BUCKET_PROCESSED = "processed-fhir"

KNOWN_CATEGORIES = json.loads(os.environ["CATEGORIES_MAP"])

# Function to split json
@SPLIT_JSON_DURATION_SECONDS.time()
def split_json(json_file):
    metrics = None
    workouts = None
    stateofmind = None
    symptoms = None
    medications = None

    for k in json_file["data"].keys():
        if k == "metrics":
            metrics = json_file["data"]["metrics"]
        elif k == "workouts":
            workouts = json_file["data"]["workouts"]
        elif k == "stateOfMind":
            stateofmind = json_file["data"]["stateOfMind"]
        elif k == "symptoms":
            symptoms = json_file["data"]["symptoms"]
        elif k =="medications":
            medications = json_file["data"]["medications"]
        else:
            print(f"Nouvelle catégorie: {k}.")
            UNKNOWN_CATEGORY_TOTAL.labels(category=k).inc()

    return metrics, workouts, stateofmind, symptoms, medications

def _run_pipeline(name, pipeline_func, data, obj_id):
    """
    Run pipeline (metrics/workouts/stateofminds)  
    Return None if error.
    """
    if not data:
        return None
    
    IPHONE_SUBPIPELINE_RUN_TOTAL.labels(stage=name).inc()
    start = time.perf_counter()
    
    try:
        result = pipeline_func(data)
        IPHONE_SUBPIPELINE_SUCCESS_TOTAL.labels(stage=name).inc()
        return result
    except Exception as exc:
        IPHONE_SUBPIPELINE_FAILURE_TOTAL.labels(
            stage=name,
            error_type=type(exc).__name__,
        ).inc()
        logger.error(f"Erreur de pipeline_{name} sur {obj_id} : {exc}")
        raise
    finally:
        IPHONE_SUBPIPELINE_DURATION_SECONDS.labels(stage=name).observe(
            time.perf_counter() - start
        ) 

# Main pipeline    
@IPHONE_PIPELINE_DURATION_SECONDS.time()
def iphone_json_pipeline():
    """
    Pipeline iphone :
    1 – Retrieve file list from BUCKET_RAW
    2 – Transform FHIR file and upload 
    3 – Move raw_file to BUCKET_PROCESSED
    """
    IPHONE_PIPELINE_RUN_TOTAL.inc()
    logger.info("Début du pipeline iphone_json")
    objects_list = get_object_list(bucket=BUCKET_RAW)
    logger.info(f"Liste des objets dans le bucket : {objects_list}")

    if not objects_list:
        logger.warning(f"[WARN] No file got from bucket {BUCKET_RAW}")
        return False

    success = False

    for obj_id in objects_list:
        IPHONE_PIPELINE_OBJECT_TOTAL.inc()
        logger.info(f"Traitement de l'objet : {obj_id}")

        json_file = get_object_json(bucket=BUCKET_RAW, object_name=obj_id)
        if not json_file:
            logger.warning(f"[WARN] Nothing to precess for object : {obj_id}")
            continue

        try:
            logger.info(
                f"Découpe du fichier en parties : metrics, workouts, stateOfMinds."
            )
            metrics, workouts, stateofminds, symptoms, medications = split_json(json_file)

            result_metrics = _run_pipeline("metrics", pipeline_metrics, metrics, obj_id)
            result_workouts = _run_pipeline("workouts", pipeline_workouts, workouts, obj_id)
            result_stateofminds = _run_pipeline("stateofminds", pipeline_stateofminds, stateofminds, obj_id)
            result_symptoms = _run_pipeline("symptoms", pipeline_symptoms, symptoms, obj_id)
            result_medications = _run_pipeline("medications", pipeline_medications, medications, obj_id)
            stage_results = {
                "metrics": result_metrics,
                "workouts": result_workouts,
                "stateofminds": result_stateofminds,
                "symptoms": result_symptoms,
                "medications": result_medications,
            }
            logger.info("Résultats sous-pipelines pour %s: %s", obj_id, stage_results)

            if any(stage_results.values()):
                logger.info("Upload status is OK.")
                move_object(
                    object_name=obj_id,
                    source_bucket=BUCKET_RAW,
                    destination_bucket=BUCKET_PROCESSED
                )
                logger.info("Object moved in processed-fhir bucket.")
                IPHONE_PIPELINE_OBJECT_SUCCESS_TOTAL.inc()
                IPHONE_PIPELINE_LAST_SUCCESS_UNIXTIME.set_to_current_time()
                success = True
            else:
                logger.warning("Aucun sous-pipeline réussi pour %s, objet conservé dans %s.", obj_id, BUCKET_RAW)

        except Exception as exc:
            logger.error(f"Fail in process ({obj_id}): {exc}")
            IPHONE_PIPELINE_OBJECT_FAILURE_TOTAL.inc()
            raise
        
    if success:
        IPHONE_PIPELINE_RUN_SUCCESS_TOTAL.inc()
    else:
        IPHONE_PIPELINE_RUN_FAILURE_TOTAL.inc() 

    return success

if __name__ == "__main__":
    result = iphone_json_pipeline()
    logger.info(f"Pipeline is {result}")
