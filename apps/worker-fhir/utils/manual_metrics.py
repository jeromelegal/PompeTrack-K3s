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

# For a complete manuals file (not too large !! else use process_manuals_by_cats)
def process_global_manuals(manuals: Union[List, str]) -> Dict[str, Any]:
    error_report = []
    if not isinstance(manuals, dict):
        logger.error(f"Error on reading dict.")
        error_report.append({
            "type": "dict",
            "message": "Error on reading dict.",
            "data": str(manuals)
        })
        return
   
    if not manuals.get("metrics"):
        logger.error(f"Error, not 'metrics' in file.")
        error_report.append({
            "type": "dict",
            "message": "Error, not 'metrics' in file.",
            "data": str(manuals)
        })
        return
    
    metrics = manuals["metrics"]
    obs_list = []
    total_created = 0
    for i, manual in enumerate(metrics):
        if not isinstance(manual, dict):
            logger.warning(f"Error on reading dict : {manual}.")
            error_report.append({
                "type": "dict",
                "message": "Error on reading dict.",
                "data": str(manual)
            })
            continue

        # Instance CreatePreFHIR
        try: 
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR(manual, round_digits=1)
            resource = creator.render()
            # print(json.dumps(resource, indent=2, sort_keys=False))
        except Exception as e:
            logger.error(f"Fail to create PreFHIR for {i}.")
            error_report.append({
                "type": "PreFHIR",
                "message": "Fail to create PreFHIR",
                "data": str(manual)
            })
            raise
        
        # Formating to FHIR 
        try: 
            logger.info(f"Formating to FHIR for {i}.")
            obs, total_created = list_to_fhir_observation(resource, total_created)
            obs_list = obs_list + obs
        except Exception as e:
            logger.error(f"Fail to format FHIR for {i}.")
            error_report.append({
                "type": "FHIR",
                "message": "Fail to format FHIR",
                "data": str(manual)
            })
            raise

    logger.info(f"Total resources ajoutées au bundle: {total_created}")
    
    if error_report:
        with open('error_report.json', 'w') as f:
            json.dump(error_report, f, indent=2)
        logger.info(f"Rapport d'erreurs généré avec {len(error_report)} erreurs")

    if not obs_list:
        logger.error("Fail to build bundle.")
        
    else:
        logger.info(f"Building bundle.")
        bundle_json = build_bundle_fhir(obs_list).json(
            indent=2,
            by_alias=True
        )

        return bundle_json
    
# For a complete manuals file (not too large !! else use process_manuals_by_cats)
def process_manuals_by_cats(i: int, manual: Union[dict, str]) -> Dict[str, Any]:

    obs_list = []
    error_report = []
    total_created = 0
    if not isinstance(manual, dict):
        logger.error(f"Error - not a dict.")
        error_report.append({
            "type": "dict",
            "message": "Error - not a dict.",
            "data": str(manual)
        })
        return
    
    if not manual:
        logger.error(f"Error empty dict.")
        error_report.append({
            "type": "dict",
            "message": "Error empty dict.",
            "data": str(manual)
        })
        return

    # Instance CreatePreFHIR
    try: 
        #logger.info(f"Creating PreFHIR for {i}.")
        creator = CreatePreFHIR(manual, round_digits=1)
        resource = creator.render()
        # print(json.dumps(resource, indent=2, sort_keys=False))
    except Exception as e:
        logger.error(f"Fail to create PreFHIR for {i}.")
        error_report.append({
            "type": "PreFHIR",
            "message": "Fail to create PreFHIR",
            "data": str(manual)
        })
        raise
    
    # Formating to FHIR 
    try: 
        logger.info(f"Formating to FHIR for {i}.")
        obs, total_created = list_to_fhir_observation(resource, total_created)
        obs_list = obs_list + obs
    except Exception as e:
        logger.error(f"Fail to format FHIR for {i}.")
        error_report.append({
            "type": "FHIR",
            "message": "Fail to format FHIR",
            "data": str(manual)
        })
        raise

    logger.info(f"Total resources ajoutées au bundle: {total_created}")
    
    if error_report:
        with open('error_report.json', 'w') as f:
            json.dump(error_report, f, indent=2)
        logger.info(f"Rapport d'erreurs généré avec {len(error_report)} erreurs")

    if not obs_list:
        logger.error("Fail to build bundle.")
        
    else:
        logger.info(f"Building bundle.")
        bundle_json = build_bundle_fhir(obs_list).json(
            indent=2,
            by_alias=True
        )

        return bundle_json
    

def pipeline_metrics_by_cats(manuals: List[Any]):
    """
    Full process for manuals by categories
    """
    for i, manual in enumerate(manuals):
        try:
            bundle_json = process_manuals_by_cats(i, manual)
            success = upload_bundle(bundle_json)
            
            if success:
                logger.info("Traitement des 'manuals' terminé avec succès")
                return True
            else:
                logger.info("Erreur lors du traitement des 'manuals'.")
                return False
                
        except Exception as e:
            logger.error(f"Erreur globale : {str(e)}")
            
def pipeline_metrics(manuals: List[Any]):
    """
    Full process for manuals
    """
    try:
        bundle_json = process_global_manuals(manuals)
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

    with open("/app/data/pain.json", "r", encoding="utf-8") as f:
        manuals = json.load(f)

    # metrics = manuals["metrics"]
    # for i, manual in enumerate(metrics):
    #     try:
    #         bundle_json = process_manuals_by_cats(i, manual)
    #         #print(bundle_json)
    #         success = upload_bundle(bundle_json)
            
    #         if success:
    #             print("Traitement terminé avec succès")
    #         else:
    #             print("Erreur lors de l'upload")
                
    #     except Exception as e:
    #         logger.error(f"Erreur globale : {str(e)}")
            
    try:
        bundle_json = process_global_manuals(manuals)
        #print(bundle_json)
        success = upload_bundle(bundle_json)
        
        if success:
            print("Traitement terminé avec succès")
        else:
            print("Erreur lors de l'upload")
            
    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")
        
        