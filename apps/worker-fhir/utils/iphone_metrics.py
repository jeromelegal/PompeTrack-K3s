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

# For a complete metrics file (not too large !! else use process_metrics_by_cats)
def process_global_metrics(metrics: Union[List, str]) -> Dict[str, Any]:
    obs_list = []
    error_report = []
    total_created = 0
    for i, metric in enumerate(metrics):
        if not isinstance(metric, dict):
            logger.error(f"Error on reading dict.")
            error_report.append({
                "type": "dict",
                "message": "Error on reading dict.",
                "data": str(metric)
            })
            return

        # Instance CreatePreFHIR
        try: 
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR(metric, round_digits=1)
            resource = creator.render()
            # print(json.dumps(resource, indent=2, sort_keys=False))
        except Exception as e:
            logger.error(f"Fail to create PreFHIR for {i}.")
            error_report.append({
                "type": "PreFHIR",
                "message": "Fail to create PreFHIR",
                "data": str(metric)
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
                "data": str(metric)
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
    
# For a complete metrics file (not too large !! else use process_metrics_by_cats)
def process_metrics_by_cats(i: int, metric: Union[dict, str]) -> Dict[str, Any]:
    obs_list = []
    error_report = []
    total_created = 0
    if not isinstance(metric, dict):
        logger.error(f"Error on reading dict.")
        error_report.append({
            "type": "dict",
            "message": "Error on reading dict.",
            "data": str(metric)
        })
        return

    # Instance CreatePreFHIR
    try: 
        #logger.info(f"Creating PreFHIR for {i}.")
        creator = CreatePreFHIR(metric, round_digits=1)
        resource = creator.render()
        # print(json.dumps(resource, indent=2, sort_keys=False))
    except Exception as e:
        logger.error(f"Fail to create PreFHIR for {i}.")
        error_report.append({
            "type": "PreFHIR",
            "message": "Fail to create PreFHIR",
            "data": str(metric)
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
            "data": str(metric)
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
    

def pipeline_metrics(metrics: List[Union[str, Any]]):
    """
    Full process for metrics
    """
    for i, metric in enumerate(metrics):
        try:
            bundle_json = process_metrics_by_cats(i, metric)
            success = upload_bundle(bundle_json)
            
            if success:
                logger.info("Traitement des 'metrics' terminé avec succès")
                return True
            else:
                logger.info("Erreur lors du traitement des 'metrics'.")
                return False
                
        except Exception as e:
            logger.error(f"Erreur globale : {str(e)}")
        

if __name__ == "__main__":

    with open("/app/data/metrics.json", "r", encoding="utf-8") as f:
        json_file = json.load(f)

    metrics = json_file["metrics"]
    for i, metric in enumerate(metrics):
        
        try:
            bundle_json = process_metrics_by_cats(i, metric)
            #print(bundle_json)
            success = upload_bundle(bundle_json)
            
            if success:
                print("Traitement terminé avec succès")
            else:
                print("Erreur lors de l'upload")
                
        except Exception as e:
            logger.error(f"Erreur globale : {str(e)}")
        