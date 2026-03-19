from fhir_custom.observation import list_to_fhir_observation
from fhir_custom.worker_template import CreatePreFHIR_name
from fhir_custom.bundle import build_bundle_fhir, upload_bundle, upload_bundles_in_chunks
from typing import Any, Union, List
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


def process_global_stateofminds(stateofminds: Union[List, str]):
    obs_list = []
    error_report = []
    total_created = 0

    for i, stateofmind in enumerate(stateofminds):
        if not isinstance(stateofmind, dict):
            logger.warning(f"Error on reading dict : {stateofmind}.")
            error_report.append({
                "type": "dict",
                "message": "Error on reading dict.",
                "data": str(stateofmind)
            })
            continue

        try:
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR_name(stateofmind, name="stateofminds", round_digits=1)
            resource = creator.render()
        except Exception:
            logger.exception(f"Fail to create PreFHIR for {i}.")
            error_report.append({
                "type": "PreFHIR",
                "message": "Fail to create PreFHIR",
                "data": str(stateofmind)
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
                "data": str(stateofmind)
            })
            continue

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


def process_stateofminds_by_cats(stateofmind: Union[dict, str]):
    obs_list = []
    error_report = []
    total_created = 0

    if not isinstance(stateofmind, dict):
        logger.warning(f"Error on reading dict : {stateofmind}.")
        error_report.append({
            "type": "dict",
            "message": "Error on reading dict.",
            "data": str(stateofmind)
        })
        return None

    try:
        logger.info("Creating PreFHIR for stateofmind.")
        creator = CreatePreFHIR_name(stateofmind, name="stateofminds", round_digits=1)
        resource = creator.render()
    except Exception:
        logger.exception("Fail to create PreFHIR for stateofmind.")
        error_report.append({
            "type": "PreFHIR",
            "message": "Fail to create PreFHIR",
            "data": str(stateofmind)
        })
        return None

    try:
        logger.info("Formating to FHIR for stateofmind.")
        obs, total_created = list_to_fhir_observation(resource, total_created)
        obs_list.extend(obs)
    except Exception:
        logger.exception("Fail to format FHIR for stateofmind.")
        error_report.append({
            "type": "FHIR",
            "message": "Fail to format FHIR",
            "data": str(stateofmind)
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

    logger.info("Observation list built.")
    return obs_list


def pipeline_stateofminds(stateofminds: List[Any]):
    overall_success = True

    for stateofmind in stateofminds:
        try:                
            obs_list = process_stateofminds_by_cats(stateofmind)
            if obs_list is None:
                overall_success = False
                continue

            success = upload_bundles_in_chunks(obs_list, chunk_size=5)
            if not success:
                overall_success = False

        except Exception as e:
            logger.error(f"Erreur globale : {str(e)}")
            overall_success = False

    if overall_success:
        logger.info("Traitement des 'stateofminds' terminé avec succès")
    else:
        logger.info("Erreur lors du traitement des 'stateofminds'.")

    return overall_success


if __name__ == "__main__":
    with open("/app/data/stateofmind.json", "r", encoding="utf-8") as f:
        stateofminds = json.load(f)

    success = pipeline_stateofminds(stateofminds)
    if success:
        print("Traitement terminé avec succès")
    else:
        print("Erreur lors du traitement")