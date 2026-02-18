from fhir_custom.observation import list_to_fhir_observation
from fhir_custom.worker_template import CreatePreFHIR_name
from fhir_custom.bundle import build_bundle_fhir, upload_bundle
from typing import Dict, Any, Union, List
import logging
import json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# For a complete stateofminds file (not too large !! else use process_stateofminds_by_cats)
def process_global_stateofminds(stateofminds: Union[List, str]) -> Dict[str, Any]:

    obs_list = []
    total_created = 0
    for i, stateofmind in enumerate(stateofminds):
        if not isinstance(stateofmind, dict):
            logger.warning(f"Error on reading dict : {stateofmind}.")
            continue

        # Instance CreatePreFHIR
        try: 
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR_name(stateofmind, name="stateofminds", round_digits=1)
            resource = creator.render()
            # print(json.dumps(resource, indent=2, sort_keys=False))
        except Exception as e:
            logger.error(f"Fail to create PreFHIR for {i}.")
            raise
        
        # Formating to FHIR 
        try: 
            logger.info(f"Formating to FHIR for {i}.")
            obs, total_created = list_to_fhir_observation(resource, total_created)
            obs_list = obs_list + obs
        except Exception as e:
            logger.error(f"Fail to format FHIR for {i}.")
            raise

    logger.info(f"Total resources ajoutées au bundle: {total_created}")

    if not obs_list:
        logger.error("Fail to build bundle.")
        
    else:
        logger.info(f"Building bundle.")
        bundle_json = build_bundle_fhir(obs_list).json(
            indent=2,
            by_alias=True
        )

        return bundle_json
    
# For a complete stateofminds file (not too large !! else use process_stateofminds_by_cats)
def process_stateofminds_by_cats(stateofmind: Union[dict, str]) -> Dict[str, Any]:

    obs_list = []
    total_created = 0
    if not isinstance(stateofmind, dict):
        logger.warning(f"Error on reading dict : {stateofmind}.")

    # Instance CreatePreFHIR
    try: 
        logger.info(f"Creating PreFHIR for stateofmind.")
        creator = CreatePreFHIR_name(stateofmind, name="stateofminds", round_digits=1)
        resource = creator.render()
        # print(json.dumps(resource, indent=2, sort_keys=False))
    except Exception as e:
        logger.error(f"Fail to create PreFHIR for stateofmind.")
        raise
    
    # Formating to FHIR 
    try: 
        logger.info(f"Formating to FHIR for stateofmind.")
        obs, total_created = list_to_fhir_observation(resource, total_created)
        obs_list = obs_list + obs
    except Exception as e:
        logger.error(f"Fail to format FHIR for stateofmind.")
        raise

    logger.info(f"Total resources ajoutées au bundle: {total_created}")

    if not obs_list:
        logger.error("Fail to build bundle.")
        
    else:
        logger.info(f"Building bundle.")
        bundle_json = build_bundle_fhir(obs_list).json(
            indent=2,
            by_alias=True
        )

        return bundle_json
    

def pipeline_stateofminds(stateofminds: List[Any]):
    """
    Full process for stateofminds
    """
    for i, stateofmind in enumerate(stateofminds):
        try:
            bundle_json = process_stateofminds_by_cats(stateofmind)
            success = upload_bundle(bundle_json)
            
            if success:
                logger.info("Traitement des 'stateofminds' terminé avec succès")
                return True
            else:
                logger.info("Erreur lors du traitement des 'stateofminds'.")
                return False
                
        except Exception as e:
            logger.error(f"Erreur globale : {str(e)}")
        

if __name__ == "__main__":

    with open("/app/data/stateofmind.json", "r", encoding="utf-8") as f:
        stateofminds = json.load(f)

    for i, stateofmind in enumerate(stateofminds):
        
        try:
            bundle_json = process_stateofminds_by_cats(stateofmind)
            #print(bundle_json)
            success = upload_bundle(bundle_json)
            
            if success:
                print("Traitement terminé avec succès")
            else:
                print("Erreur lors de l'upload")
                
        except Exception as e:
            logger.error(f"Erreur globale : {str(e)}")
        