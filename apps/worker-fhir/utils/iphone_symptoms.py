from fhir_custom.observation import to_fhir_observation
from fhir_custom.worker_template import CreatePreFHIR_symptoms
from fhir_custom.bundle import build_bundle_fhir, upload_bundle
from fhir_custom.bundle import build_transaction_bundle, upload_transaction_bundle
from typing import Dict, Any, Union, List
import logging
import json
from fhir_codes.severity_levels_code import SEVERITY_LEVELS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def process_global_symptoms(symptoms: Union[List, str]) -> Dict[str, Any]:
    obs_list = []
    standard_bundle_created = 0
    transaction_bundle_created = 0
    for i, symptom in enumerate(symptoms):
        if not isinstance(symptom, dict):
            logger.error(f"Error on reading dict : {symptom}.")
            return False

        # Instance CreatePreFHIR_name
        try: 
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR_symptoms()
            observations, parent_index, children_indices = creator.process(symptom)
            # print(json.dumps(resource, indent=2, sort_keys=False))
        except Exception as e:
            logger.error(f"Fail to create PreFHIR for {i}.")
            return False
        
        # Formating to FHIR 
        if children_indices:
            logger.info(f"Creating 'transaction bundle' for symptom : {i}.")
            bundle = build_transaction_bundle(
                observations,
                parent_index=parent_index,
                children_indices=children_indices
            )
            try: 
                success = upload_transaction_bundle(bundle)
                logger.info(f"Upload transaction bundle {i} is {success}.")
                transaction_bundle_created += 1
            except Exception as e:
                logger.error(f"Fail to upload transaction bundle : {i}.")
                return False
        
        else:
            
            logger.info(f"Building FHIR Observation.")
            for observation in observations:
                obs = to_fhir_observation(observation)
                obs_list.append(obs)
            logger.info(f"Creating 'bundle' for symptom : {i}.")
            bundle_json = build_bundle_fhir(obs_list).json(
                indent=2,
                by_alias=True
            )
            try:
                success = upload_bundle(bundle_json)
                logger.info(f"Upload bundle {i} is {success}.")
                standard_bundle_created += 1
            except Exception as e:
                logger.error(f"Fail to upload bundle : {i}.")
                return False

    logger.info(f"Total standard bundle uploaded : {standard_bundle_created}")
    logger.info(f"Total transaction bundle uploaded : {transaction_bundle_created}")
    return True


def pipeline_symptoms(symptoms: List[Union[str, Any]]):
    """
    Full process for symptoms
    """            
    try:
        success = process_global_symptoms(symptoms)
        
        if success:
            logger.info("Traitement des 'symptoms' terminé avec succès")
            return True
        else:
            logger.info("Erreur lors du traitement des 'symptoms'.")
            return False
            
    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")
 
            

if __name__ == "__main__":

    with open("/app/data/symptoms.json", "r", encoding="utf-8") as f:
        symptoms = json.load(f)

    pipeline_symptoms(symptoms)