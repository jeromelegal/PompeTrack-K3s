from fhir_custom.observation import to_fhir_observation
from fhir_custom.worker_template import CreatePreFHIR_symptoms
from fhir_custom.bundle import build_bundle_fhir, upload_bundle
from fhir_custom.bundle import build_transaction_bundle, upload_transaction_bundle
from fhir_custom.bundle import upload_bundles_in_chunks
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


def process_global_symptoms(symptoms: Union[List, str]) -> bool:
    error_report = []
    standard_bundle_created = 0
    transaction_bundle_created = 0

    for i, symptom in enumerate(symptoms):
        if not isinstance(symptom, dict):
            logger.error(f"Error on reading dict : {symptom}.")
            error_report.append({
                "type": "dict",
                "message": "Error on reading dict.",
                "data": str(symptom)
            })
            continue

        try:
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR_symptoms()
            observations, parent_index, children_indices = creator.process(symptom)
        except Exception:
            logger.exception(f"Fail to create PreFHIR for {i}.")
            error_report.append({
                "type": "PreFHIR",
                "message": "Fail to create PreFHIR",
                "data": str(symptom)
            })
            continue

        if children_indices:
            logger.info(f"Creating 'transaction bundle' for symptom : {i}.")
            try:
                bundle = build_transaction_bundle(
                    observations,
                    parent_index=parent_index,
                    children_indices=children_indices
                )
                success = upload_transaction_bundle(bundle)
                logger.info(f"Upload transaction bundle {i} is {success}.")
                if success:
                    transaction_bundle_created += 1
                else:
                    error_report.append({
                        "type": "FHIR",
                        "message": "Fail to upload transaction bundle",
                        "data": str(symptom)
                    })
            except Exception:
                logger.exception(f"Fail to upload transaction bundle : {i}.")
                error_report.append({
                    "type": "FHIR",
                    "message": "Fail to upload transaction bundle",
                    "data": str(symptom)
                })
        else:
            try:
                logger.info("Building FHIR Observation.")
                current_obs_list = []
                for observation in observations:
                    obs = to_fhir_observation(observation)
                    current_obs_list.append(obs)

                logger.info(f"Uploading chunked bundles for symptom : {i}.")
                success = upload_bundles_in_chunks(current_obs_list, chunk_size=5)
                logger.info(f"Upload bundle {i} is {success}.")
                if success:
                    standard_bundle_created += 1
                else:
                    error_report.append({
                        "type": "FHIR",
                        "message": "Fail to upload bundle",
                        "data": str(symptom)
                    })
            except Exception:
                logger.exception(f"Fail to upload bundle : {i}.")
                error_report.append({
                    "type": "FHIR",
                    "message": "Fail to upload bundle",
                    "data": str(symptom)
                })

    if error_report:
        with open("error_report.json", "w") as f:
            json.dump(error_report, f, indent=2)
        logger.info(f"Rapport d'erreurs généré avec {len(error_report)} erreurs")

    logger.info(f"Total standard bundle uploaded : {standard_bundle_created}")
    logger.info(f"Total transaction bundle uploaded : {transaction_bundle_created}")
    return len(error_report) == 0


def _normalize_symptoms(symptoms):
    if not isinstance(symptoms, list):
        return []

    out = []
    for symptom in symptoms:
        if not isinstance(symptom, dict):
            continue
        new = dict(symptom)
        if "name" in new and "symptom" not in new:
            new["symptom"] = new.pop("name")
        out.append(new)
    return out


def pipeline_symptoms(symptoms: List[Union[str, Any]]):
    normalized_symptoms = _normalize_symptoms(symptoms)

    try:
        success = process_global_symptoms(normalized_symptoms)

        if success:
            logger.info("Traitement des 'symptoms' terminé avec succès")
            return True

        logger.info("Erreur lors du traitement des 'symptoms'.")
        return False

    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")
        return False


if __name__ == "__main__":
    with open("/app/data/symptoms.json", "r", encoding="utf-8") as f:
        symptoms = json.load(f)

    pipeline_symptoms(symptoms)