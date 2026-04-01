from fhir_custom.observation import list_to_fhir_observation
from fhir_custom.worker_template import CreatePreFHIR
from fhir_custom.bundle import build_bundle_fhir, upload_bundle
from fhir_custom.bundle import upload_bundles_in_chunks
from typing import Dict, Any, Union, List
import logging
import json
import os

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fhir_processor.log'),
        logging.StreamHandler()
    ]
)

MEDPLUM_DEVICE_ID_SPRIROMETER = os.getenv("MEDPLUM_DEVICE_ID_SPRIROMETER")

# Function to process global spirometer
def process_global_spirometer(spirometer: Union[List, str, Dict[str, Any]]):
    """
    Function to process global spirometer and return a list of observations.
    """
    error_report = []

    if not isinstance(spirometer, dict):
        logger.error("Error on reading dict.")
        error_report.append({
            "type": "dict",
            "message": "Error on reading dict.",
            "data": str(spirometer)
        })
        return None

    if not spirometer.get("metrics"):
        logger.error("Error, not 'metrics' in file.")
        error_report.append({
            "type": "dict",
            "message": "Error, not 'metrics' in file.",
            "data": str(spirometer)
        })
        return None

    metrics = spirometer["metrics"]
    obs_list = []
    total_created = 0

    for i, metric in enumerate(metrics):
        if not isinstance(metric, dict):
            logger.warning(f"Error on reading dict : {metric}.")
            error_report.append({
                "type": "dict",
                "message": "Error on reading dict.",
                "data": str(metric)
            })
            continue

        try:
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR(metric, 
                                    device_id=MEDPLUM_DEVICE_ID_SPRIROMETER,
                                    round_digits=1)
            resource = creator.render()
        except Exception:
            logger.exception(f"Fail to create PreFHIR for {i}.")
            error_report.append({
                "type": "PreFHIR",
                "message": "Fail to create PreFHIR",
                "data": str(metric)
            })
            continue

        try:
            logger.info(f"Formating to FHIR for {i}.")
            obs, total_created = list_to_fhir_observation(resource, total_created)
            obs_list.extend(obs)
        except Exception:
            logger.exception(f"Fail to format FHIR for {i}.")
            error_report.append({
                "type": "FHIR",
                "message": "Fail to format FHIR",
                "data": str(resource)
            })
            continue

    logger.info(f"Total resources ajoutées au bundle: {total_created}")

    if error_report:
        with open("error_report.json", "w") as f:
            json.dump(error_report, f, indent=2)
        logger.info(f"Rapport d'erreurs généré avec {len(error_report)} erreurs")

    if not obs_list:
        logger.error("Fail to build observations list.")
        return None

    return obs_list

# Function to process spirometer by categories
def process_spirometer_by_cats(i: int, metric: Union[dict, str]):
    """
    Function to process spirometer by categories and return a list of observations.
    """
    obs_list = []
    error_report = []
    total_created = 0

    if not isinstance(metric, dict):
        logger.error("Error - not a dict.")
        error_report.append({
            "type": "dict",
            "message": "Error - not a dict.",
            "data": str(metric)
        })
        return None

    if not metric:
        logger.error("Error empty dict.")
        error_report.append({
            "type": "dict",
            "message": "Error empty dict.",
            "data": str(metric)
        })
        return None

    try:
        creator = CreatePreFHIR(metric, 
                                device_id=MEDPLUM_DEVICE_ID_SPRIROMETER,
                                round_digits=1)
        resource = creator.render()
    except Exception:
        logger.exception(f"Fail to create PreFHIR for {i}.")
        error_report.append({
            "type": "PreFHIR",
            "message": "Fail to create PreFHIR",
            "data": str(metric)
        })
        return None

    try:
        logger.info(f"Formating to FHIR for {i}.")
        obs, total_created = list_to_fhir_observation(resource, total_created)
        obs_list.extend(obs)
    except Exception:
        logger.exception(f"Fail to format FHIR for {i}.")
        error_report.append({
            "type": "FHIR",
            "message": "Fail to format FHIR",
            "data": str(metric)
        })
        return None

    logger.info(f"Total resources ajoutées au bundle: {total_created}")

    if error_report:
        with open("error_report.json", "w") as f:
            json.dump(error_report, f, indent=2)
        logger.info(f"Rapport d'erreurs généré avec {len(error_report)} erreurs")

    if not obs_list:
        logger.error("Fail to build bundle.")
        return None

    logger.info("Building bundle.")
    return build_bundle_fhir(obs_list)

# Pipeline to process global spirometer by categories
def pipeline_metrics_by_cats(spirometer: List[Any]):
    overall_success = True

    for i, metric in enumerate(spirometer):
        try:
            bundle = process_spirometer_by_cats(i, metric)
            if bundle is None:
                overall_success = False
                continue

            success = upload_bundle(bundle)
            if not success:
                overall_success = False

        except Exception as e:
            logger.error(f"Erreur globale : {str(e)}")
            overall_success = False

    if overall_success:
        logger.info("Traitement des 'spirometer' terminé avec succès")
    else:
        logger.info("Erreur lors du traitement des 'spirometer'.")

    return overall_success

# Pipeline to process global spirometer
def pipeline_metrics(spirometer: List[Any]):
    try:
        obs_list = process_global_spirometer(spirometer)
        if obs_list is None:
            return False

        success = upload_bundles_in_chunks(obs_list, chunk_size=10)
        if success:
            print("Traitement terminé avec succès")
            return True

        print("Erreur lors de l'upload")
        return False

    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")
        return False


if __name__ == "__main__":
    with open("/app/data/spirometer.json", "r", encoding="utf-8") as f:
        spirometer = json.load(f)

    try:
        bundle = process_global_spirometer(spirometer)
        success = upload_bundle(bundle) if bundle is not None else False

        if success:
            print("Traitement terminé avec succès")
        else:
            print("Erreur lors de l'upload")

    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")