from fhir_custom.observation import list_to_fhir_observation
from fhir_custom.worker_template import CreatePreFHIR
from fhir_custom.bundle import build_bundle_fhir, upload_bundle
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


def average_strenght_results(strengths: Dict[str, Any]) -> Dict[str, Any]:
    """
    Average the results of the strengths for each category
    """
    metrics = []

    def _average_measures(measures):
        add = 0
        for measure in measures:
            add += measure.get('qty', 0)
        avg = add / len(measures)
        return avg

    for measures in strengths["metrics"]:
        name = measures.get("name")
        typ = measures.get("type")
        qty = _average_measures(measures["data"])
        metrics.append({
            "type": typ,
            "name": name,
            "data": [{
                "units": measures["data"][0]["units"],
                "date": measures["data"][0]["date"],
                "qty": qty
            }]
        })

    return {"metrics": metrics}


def process_global_strengths(strengths: Union[List, str, Dict[str, Any]]):
    error_report = []

    if not isinstance(strengths, dict):
        logger.error("Error on reading dict.")
        error_report.append({
            "type": "dict",
            "message": "Error on reading dict.",
            "data": str(strengths)
        })
        return None

    if not strengths.get("metrics"):
        logger.error("Error, not 'metrics' in file.")
        error_report.append({
            "type": "dict",
            "message": "Error, not 'metrics' in file.",
            "data": str(strengths)
        })
        return None

    metrics = strengths["metrics"]
    obs_list = []
    total_created = 0

    for i, strength in enumerate(metrics):
        if not isinstance(strength, dict):
            logger.warning(f"Error on reading dict : {strength}.")
            error_report.append({
                "type": "dict",
                "message": "Error on reading dict.",
                "data": str(strength)
            })
            continue

        try:
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR(strength, round_digits=1)
            resource = creator.render()
        except Exception:
            logger.exception(f"Fail to create PreFHIR for {i}.")
            error_report.append({
                "type": "PreFHIR",
                "message": "Fail to create PreFHIR",
                "data": str(strength)
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
                "data": str(strength)
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


def process_strengths_by_cats(i: int, strength: Union[dict, str]):
    obs_list = []
    error_report = []
    total_created = 0

    if not isinstance(strength, dict):
        logger.error("Error - not a dict.")
        error_report.append({
            "type": "dict",
            "message": "Error - not a dict.",
            "data": str(strength)
        })
        return None

    if not strength:
        logger.error("Error empty dict.")
        error_report.append({
            "type": "dict",
            "message": "Error empty dict.",
            "data": str(strength)
        })
        return None

    try:
        creator = CreatePreFHIR(strength, round_digits=1)
        resource = creator.render()
    except Exception:
        logger.exception(f"Fail to create PreFHIR for {i}.")
        error_report.append({
            "type": "PreFHIR",
            "message": "Fail to create PreFHIR",
            "data": str(strength)
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
            "data": str(strength)
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


def pipeline_metrics_by_cats(strengths: List[Any]):
    overall_success = True

    for i, strength in enumerate(strengths):
        try:
            bundle = process_strengths_by_cats(i, strength)
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
        logger.info("Traitement des 'strengths' terminé avec succès")
    else:
        logger.info("Erreur lors du traitement des 'strengths'.")

    return overall_success


def pipeline_metrics(strengths: List[Any]):
    try:
        strengths = average_strenght_results(strengths)
        bundle = process_global_strengths(strengths)
        if bundle is None:
            return False

        success = upload_bundle(bundle)
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
        strengths = json.load(f)

    try:
        bundle = process_global_strengths(strengths)
        success = upload_bundle(bundle) if bundle is not None else False

        if success:
            print("Traitement terminé avec succès")
        else:
            print("Erreur lors de l'upload")

    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")