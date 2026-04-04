from fhir_custom.medication import list_to_fhir_medication, to_fhir_medication
from fhir_custom.worker_template import CreatePreFHIR
from fhir_custom.bundle import build_bundle_medication, upload_bundle
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

# Function to process global medications
def process_global_medications(medication: Union[List, str, Dict[str, Any]]):
    """
    Function to process global medications and return a list of medications.
    """
    error_report = []

    if not isinstance(medication, dict):
        logger.error("Error on reading dict.")
        error_report.append({
            "type": "dict",
            "message": "Error on reading dict.",
            "data": str(medication)
        })
        return None

    try:
        logger.info("Creating PreFHIR for medication.")
        creator = CreatePreFHIR(medication)
        resource = creator.render()
    except Exception:
        logger.exception(f"Fail to create PreFHIR for medication.")
        error_report.append({
            "type": "PreFHIR",
            "message": "Fail to create PreFHIR",
            "data": str(medication)
        })
        raise

    try:
        logger.info("Formating to FHIR for medication.")
        med = list_to_fhir_medication(resource)
    except Exception:
        logger.exception("Fail to format FHIR for medication.")
        error_report.append({
            "type": "FHIR",
            "message": "Fail to format FHIR",
            "data": str(medication)
        })
        raise

    if error_report:
        with open("error_report.json", "w") as f:
            json.dump(error_report, f, indent=2)
        logger.info(f"Rapport d'erreurs généré avec {len(error_report)} erreurs")

    return build_bundle_medication(med)

# Pipeline to process global workouts
def pipeline_medication(medication: List[Any]):
    try:
        med = process_global_medications(medication)
        if med is None:
            return False

        success = upload_bundle(med)
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
        medications = json.load(f)

    try:
        bundle = process_global_medications(medications)
        success = upload_bundle(bundle) if bundle is not None else False

        if success:
            print("Traitement terminé avec succès")
        else:
            print("Erreur lors de l'upload")

    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")



















