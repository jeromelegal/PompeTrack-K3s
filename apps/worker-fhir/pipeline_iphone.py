import os
from utils.iphone_metrics import pipeline_metrics
from utils.iphone_workouts import pipeline_workouts
from utils.iphone_stateofminds import pipeline_stateofminds
from utils.iphone_symptoms import pipeline_symptoms
from libs.minio_requests import get_object_list, get_object_json, move_object
import logging

logger = logging.getLogger("Worker-fhir")
logging.basicConfig(level=logging.INFO)

BUCKET_RAW = "raw-iphone"
BUCKET_PROCESSED = "processed-fhir"

def split_json(json_file):
    metrics = None
    workouts = None
    stateofmind = None
    symptoms = None

    for k in json_file["data"].keys():
        if k == "metrics":
            metrics = json_file["data"]["metrics"]
        elif k == "workouts":
            workouts = json_file["data"]["workouts"]
        elif k == "stateOfMind":
            stateofmind = json_file["data"]["stateOfMind"]
        elif k == "symptoms":
            symptoms = json_file["data"]["symptoms"]
        else:
            print(f"Nouvelle catégorie: {k}.")

    return metrics, workouts, stateofmind, symptoms

def _run_pipeline(name, pipeline_func, data, obj_id):
    """
    Exécute une fonction de pipeline (metrics/workouts/stateofminds)
    et gére l’échec avec un message log.  
    Retourne le résultat ou None en cas d’erreur.
    """
    if not data:
        return None
    try:
        return pipeline_func(data)
    except Exception as exc:
        logger.error(f"Erreur de pipeline_{name} sur {obj_id} : {exc}")
        raise   
    
def iphone_json_pipeline():
    """
    Pipeline iphone :
    1 – Récupérer les fichiers en RAW
    2 – Transformer en FHIR et uploader
    3 – Déplacer le fichier RAW vers BUCKET_PROCESSED
    """
    logger.info("Début du pipeline iphone_json")
    objects_list = get_object_list(bucket=BUCKET_RAW)
    logger.info(f"Liste des objets dans le bucket : {objects_list}")

    if not objects_list:
        logger.warning(f"[WARN] No file got from bucket {BUCKET_RAW}")
        return False

    success = False

    for obj_id in objects_list:
        logger.info(f"Traitement de l'objet : {obj_id}")

        json_file = get_object_json(bucket=BUCKET_RAW, object_name=obj_id)
        if not json_file:
            logger.warning(f"[WARN] Nothing to precess for object : {obj_id}")
            continue

        try:
            logger.info(
                f"Découpe du fichier en parties : metrics, workouts, stateOfMinds."
            )
            metrics, workouts, stateofminds, symptoms = split_json(json_file)

            result_metrics = _run_pipeline("metrics", pipeline_metrics, metrics, obj_id)
            result_workouts = _run_pipeline("workouts", pipeline_workouts, workouts, obj_id)
            result_stateofminds = _run_pipeline("stateofminds", pipeline_stateofminds, stateofminds, obj_id)
            result_symptoms = _run_pipeline("symptoms", pipeline_symptoms, symptoms, obj_id)

            if any([result_metrics, result_workouts, result_stateofminds, result_symptoms]):
                logger.info("Upload status is OK.")
                move_object(
                    object_name=obj_id,
                    source_bucket=BUCKET_RAW,
                    destination_bucket=BUCKET_PROCESSED
                )
                logger.info("Object moved in processed-fhir bucket.")
                success = True

        except Exception as exc:
            logger.error(f"Fail in process ({obj_id}): {exc}")
            raise

    return success

if __name__ == "__main__":
    result = iphone_json_pipeline()
    logger.info(f"Pipeline is {result}")
