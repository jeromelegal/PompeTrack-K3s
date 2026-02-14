from fhir_custom.observation import list_to_fhir_observation
from fhir_custom.worker_template import CreatePreFHIR
from fhir_custom.bundle import build_bundle_fhir, upload_bundle
from typing import Dict, Any, Union, List
import logging
import json

logger = logging.getLogger(__name__)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO, 
    format='- %(name) - %(message)s'
)

# For a complete spirometer file (not too large !! else use process_spirometer_by_cats)
def process_global_spirometer(spirometer: Union[List, str]) -> Dict[str, Any]:
    if not isinstance(spirometer, dict):
        logger.error(f"Error on reading dict.")
        return
   
    if not spirometer.get("metrics"):
        logger.error(f"Error, not 'metrics' in file.")
        return
    
    metrics = spirometer["metrics"]
    obs_list = []
    total_created = 0
    for i, manual in enumerate(metrics):
        if not isinstance(manual, dict):
            logger.warning(f"Error on reading dict : {manual}.")
            continue

        # Instance CreatePreFHIR
        try: 
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR(manual, round_digits=1)
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
    
# For a complete spirometer file (not too large !! else use process_spirometer_by_cats)
def process_spirometer_by_cats(i: int, manual: Union[dict, str]) -> Dict[str, Any]:

    obs_list = []
    total_created = 0
    if not isinstance(manual, dict):
        logger.error(f"Error - not a dict.")
        return
    
    if not manual:
        logger.error(f"Error empty dict.")
        return

    # Instance CreatePreFHIR
    try: 
        #logger.info(f"Creating PreFHIR for {i}.")
        creator = CreatePreFHIR(manual, round_digits=1)
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
    

def pipeline_metrics_by_cats(spirometer: List[Any]):
    """
    Full process for spirometer by categories
    """
    for i, metric in enumerate(spirometer):
        try:
            bundle_json = process_spirometer_by_cats(i, metric)
            success = upload_bundle(bundle_json)
            
            if success:
                logger.info("Traitement des 'spirometer' terminé avec succès")
                return True
            else:
                logger.info("Erreur lors du traitement des 'spirometer'.")
                return False
                
        except Exception as e:
            logger.error(f"Erreur globale : {str(e)}")
            
def pipeline_metrics(spirometer: List[Any]):
    """
    Full process for spirometer
    """
    try:
        bundle_json = process_global_spirometer(spirometer)
        #print(bundle_json)
        success = upload_bundle(bundle_json)
        if success:
            print("Traitement terminé avec succès")
            return True
        else:
            print("Erreur lors de l'upload")
            return False
    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")
        return False
        

if __name__ == "__main__":

    with open("/app/data/spirometer.json", "r", encoding="utf-8") as f:
        spirometer = json.load(f)

    # metrics = spirometer["metrics"]
    # for i, manual in enumerate(metrics):
    #     try:
    #         bundle_json = process_spirometer_by_cats(i, manual)
    #         #print(bundle_json)
    #         success = upload_bundle(bundle_json)
            
    #         if success:
    #             print("Traitement terminé avec succès")
    #         else:
    #             print("Erreur lors de l'upload")
                
    #     except Exception as e:
    #         logger.error(f"Erreur globale : {str(e)}")
            
    try:
        bundle_json = process_global_spirometer(spirometer)
        #print(bundle_json)
        success = upload_bundle(bundle_json)
        
        if success:
            print("Traitement terminé avec succès")
        else:
            print("Erreur lors de l'upload")
            
    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")
        
        