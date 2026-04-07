from fhir_custom.medicationadministration import list_to_fhir_medicationadministration
from fhir_custom.worker_template import CreatePreFHIR_medicationadministration
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

# Function to process global medications
def process_global_medications(medications: Union[List, str]):
    """
    Function to process global medications and return a list of Medication.
    """
    error_report = []
    standard_bundle_created = 0
    transaction_bundle_created = 0

    for i, medication in enumerate(medications):
        if not isinstance(medication, dict):
            logger.error(f"Error on reading dict : {medication}.")
            error_report.append({
                "type": "dict",
                "message": "Error on reading dict.",
                "data": str(medication)
            })
            continue

        try:
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR_medicationadministration()
            medications, parent_index, children_indices = creator.process(medication)
        except Exception:
            logger.exception(f"Fail to create PreFHIR for {i}.")
            error_report.append({
                "type": "PreFHIR",
                "message": "Fail to create PreFHIR",
                "data": str(medication)
            })
            continue

        if children_indices:
            logger.info(f"Creating 'transaction bundle' for medication : {i}.")
            try:
                bundle = build_transaction_bundle(
                    medications,
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
                        "data": str(medication)
                    })
            except Exception:
                logger.exception(f"Fail to upload transaction bundle : {i}.")
                error_report.append({
                    "type": "FHIR",
                    "message": "Fail to upload transaction bundle",
                    "data": str(medication)
                })
        else:
            try:
                logger.info("Building FHIR Medication.")
                current_medication_list = []
                for medication in medications:
                    med = to_fhir_medication(medication)
                    current_medication_list.append(med)

                logger.info(f"Uploading chunked bundles for medication : {i}.")
                success = upload_bundles_in_chunks(current_medication_list, chunk_size=5)
                logger.info(f"Upload bundle {i} is {success}.")
                if success:
                    standard_bundle_created += 1
                else:
                    error_report.append({
                        "type": "FHIR",
                        "message": "Fail to upload bundle",
                        "data": str(medication)
                    })
            except Exception:
                logger.exception(f"Fail to upload bundle : {i}.")
                error_report.append({
                    "type": "FHIR",
                    "message": "Fail to upload bundle",
                    "data": str(medication)
                })

    if error_report:
        with open("error_report.json", "w") as f:
            json.dump(error_report, f, indent=2)
        logger.info(f"Rapport d'erreurs généré avec {len(error_report)} erreurs")

    logger.info(f"Total standard bundle uploaded : {standard_bundle_created}")
    logger.info(f"Total transaction bundle uploaded : {transaction_bundle_created}")
    return len(error_report) == 0

# Function to normalize medications
def _normalize_medications(medications):
    """
    Function to normalize medications.
    """
    if not isinstance(medications, list):
        return []

    out = []
    for medication in medications:
        if not isinstance(medication, dict):
            continue
        new = dict(medication)
        if "name" in new and "medication" not in new:
            new["medication"] = new.pop("name")
        out.append(new)
    return out

# Pipeline to process medications
def pipeline_medications(medications: List[Union[str, Any]]):
    normalized_medications = _normalize_medications(medications)

    try:
        success = process_global_medications(normalized_medications)

        if success:
            logger.info("Traitement des 'medications' terminé avec succès")
            return True

        logger.info("Erreur lors du traitement des 'medications'.")
        return False

    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")
        return False


if __name__ == "__main__":
    with open("/app/data/medications.json", "r", encoding="utf-8") as f:
        medications = json.load(f)

    pipeline_medications(medications)