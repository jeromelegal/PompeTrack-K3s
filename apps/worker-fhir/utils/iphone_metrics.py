from fhir_custom.observation import list_to_fhir_observation
from fhir_custom.worker_template import CreatePreFHIR
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


def process_global_metrics(metrics: Union[List, str]):
    obs_list = []
    error_report = []
    total_created = 0

    for i, metric in enumerate(metrics):
        if not isinstance(metric, dict):
            logger.error("Error on reading dict.")
            error_report.append({
                "type": "dict",
                "message": "Error on reading dict.",
                "data": str(metric)
            })
            continue

        try:
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR(metric, round_digits=1)
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
                "data": str(metric)
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


def process_metrics_by_cats(i: int, metric: Union[dict, str]):
    obs_list = []
    error_report = []
    total_created = 0

    if not isinstance(metric, dict):
        logger.error("Error on reading dict.")
        error_report.append({
            "type": "dict",
            "message": "Error on reading dict.",
            "data": str(metric)
        })
        return None

    try:
        creator = CreatePreFHIR(metric, round_digits=1)
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

    logger.info("Observation list built.")
    return obs_list


def pipeline_metrics(metrics: List[Union[str, Any]]):
    overall_success = True

    for i, metric in enumerate(metrics):
        try:           
            obs_list = process_metrics_by_cats(i, metric)
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
        logger.info("Traitement des 'metrics' terminé avec succès")
    else:
        logger.info("Erreur lors du traitement des 'metrics'.")

    return overall_success


if __name__ == "__main__":
    with open("/app/data/metrics.json", "r", encoding="utf-8") as f:
        json_file = json.load(f)

    metrics = json_file["metrics"]
    success = pipeline_metrics(metrics)

    if success:
        print("Traitement terminé avec succès")
    else:
        print("Erreur lors du traitement")