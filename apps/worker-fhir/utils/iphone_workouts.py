from fhir_custom.observation import to_fhir_observation
from fhir_custom.worker_template import CreatePreFHIR_workouts
from fhir_custom.bundle import build_bundle_fhir, upload_bundle
from fhir_custom.bundle import build_transaction_bundle, upload_transaction_bundle
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

def process_global_workouts(workouts: Union[List, str]) -> Dict[str, Any]:
    obs_list = []
    error_report = []
    standard_bundle_created = 0
    transaction_bundle_created = 0
    for i, workout in enumerate(workouts):
        if not isinstance(workout, dict):
            logger.error(f"Error on reading dict : {workout}.")
            error_report.append({
                "type": "dict",
                "message": "Error on reading dict.",
                "data": str(workout)
            })
            return False

        # Instance CreatePreFHIR_workouts
        try: 
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR_workouts()
            observations, parent_index, children_indices = creator.process(workout)
            # print(json.dumps(resource, indent=2, sort_keys=False))
        except Exception as e:
            logger.error(f"Fail to create PreFHIR for {i}.")
            error_report.append({
                "type": "PreFHIR",
                "message": "Fail to create PreFHIR",
                "data": str(workout)
            })
            return False
        
        # Formating to FHIR 
        if children_indices:
            logger.info(f"Creating 'transaction bundle' for workout : {i}.")
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
                error_report.append({
                "type": "FHIR",
                "message": "Fail to format FHIR",
                "data": str(workout)
                })
                return False
        
        else:
            
            logger.info(f"Building FHIR Observation.")
            for observation in observations:
                obs = to_fhir_observation(observation)
                obs_list.append(obs)
            logger.info(f"Creating 'bundle' for workout : {i}.")
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
                error_report.append({
                "type": "FHIR",
                "message": "Fail to upload bundle",
                "data": str(workout)
                })
                return False
            
    if error_report:
        with open('error_report.json', 'w') as f:
            json.dump(error_report, f, indent=2)
        logger.info(f"Rapport d'erreurs généré avec {len(error_report)} erreurs")

    logger.info(f"Total standard bundle uploaded : {standard_bundle_created}")
    logger.info(f"Total transaction bundle uploaded : {transaction_bundle_created}")
    return True


def pipeline_workouts(workouts: List[Union[str, Any]]):
    """
    Full process for workouts
    """            
    try:
        success = process_global_workouts(workouts)
        
        if success:
            logger.info("Traitement des 'workouts' terminé avec succès")
            return True
        else:
            logger.info("Erreur lors du traitement des 'workouts'.")
            return False
            
    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")
 
            

if __name__ == "__main__":

    with open("/app/data/workouts.json", "r", encoding="utf-8") as f:
        workouts = json.load(f)

    pipeline_workouts(workouts)