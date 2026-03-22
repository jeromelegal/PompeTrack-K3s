from fhir_custom.observation import list_to_fhir_observation
from fhir_custom.worker_template import CreatePreFHIR
from fhir_custom.bundle import build_bundle_fhir, upload_bundle
from fhir_custom.bundle import upload_bundles_in_chunks
from typing import Dict, Any, Union, List
import logging
import json

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fhir_processor.log'),
        logging.StreamHandler()
    ]
)

MEDPLUM_DEVICE_ID_STREAMLIT = os.getenv("MEDPLUM_DEVICE_ID_STREAMLIT")

def process_global_manuals(manuals: Union[List, str, Dict[str, Any]]):
    error_report = []

    if not isinstance(manuals, dict):
        logger.error("Error on reading dict.")
        error_report.append({
            "type": "dict",
            "message": "Error on reading dict.",
            "data": str(manuals)
        })
        return None

    if not manuals.get("metrics"):
        logger.error("Error, not 'metrics' in file.")
        error_report.append({
            "type": "dict",
            "message": "Error, not 'metrics' in file.",
            "data": str(manuals)
        })
        return None

    metrics = manuals["metrics"]
    obs_list = []
    total_created = 0

    for i, manual in enumerate(metrics):
        if not isinstance(manual, dict):
            logger.warning(f"Error on reading dict : {manual}.")
            error_report.append({
                "type": "dict",
                "message": "Error on reading dict.",
                "data": str(manual)
            })
            continue

        try:
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR(manual, 
                                    device_id=MEDPLUM_DEVICE_ID_STREAMLIT,
                                    round_digits=1)
            resource = creator.render()
        except Exception:
            logger.exception(f"Fail to create PreFHIR for {i}.")
            error_report.append({
                "type": "PreFHIR",
                "message": "Fail to create PreFHIR",
                "data": str(manual)
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
                "data": str(manual)
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


def process_manuals_by_cats(i: int, manual: Union[dict, str]):
    obs_list = []
    error_report = []
    total_created = 0

    if not isinstance(manual, dict):
        logger.error("Error - not a dict.")
        error_report.append({
            "type": "dict",
            "message": "Error - not a dict.",
            "data": str(manual)
        })
        return None

    if not manual:
        logger.error("Error empty dict.")
        error_report.append({
            "type": "dict",
            "message": "Error empty dict.",
            "data": str(manual)
        })
        return None

    try:
        creator = CreatePreFHIR(manual, 
                                device_id=MEDPLUM_DEVICE_ID_STREAMLIT,
                                round_digits=1)
        resource = creator.render()
    except Exception:
        logger.exception(f"Fail to create PreFHIR for {i}.")
        error_report.append({
            "type": "PreFHIR",
            "message": "Fail to create PreFHIR",
            "data": str(manual)
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
            "data": str(manual)
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


def pipeline_metrics_by_cats(manuals: List[Any]):
    overall_success = True

    for i, manual in enumerate(manuals):
        try:
            bundle = process_manuals_by_cats(i, manual)
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
        logger.info("Traitement des 'manuals' terminé avec succès")
    else:
        logger.info("Erreur lors du traitement des 'manuals'.")

    return overall_success


def pipeline_metrics(manuals: List[Any]):
    try:
        obs_list = process_global_manuals(manuals)
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
    with open("/app/data/pain.json", "r", encoding="utf-8") as f:
        manuals = json.load(f)

    try:
        bundle = process_global_manuals(manuals)
        success = upload_bundle(bundle) if bundle is not None else False

        if success:
            print("Traitement terminé avec succès")
        else:
            print("Erreur lors de l'upload")

    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")