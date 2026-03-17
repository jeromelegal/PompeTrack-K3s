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

def average_strenght_results(strengths: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Average the results of the strengths for each category
    """
    metrics = []
    def _average_measures(measures):
        add = 0
        for measure in measures:
            add += measure.get('qty')
        avg = add / len(measures)
        return avg
        
    for measures in strengths["metrics"]:
        name = measures.get("name")
        typ = measures.get("type")
        qty = _average_measures(measures["data"])
        metrics.append({
            'type': typ,
            'name': name,
            'data': [{'units': measures["data"][0]["units"],
                      'date': measures["data"][0]["date"], 
                      'qty': qty}]})
    return {"metrics": metrics}


# For a complete strengths file (not too large !! else use process_strengths_by_cats)
def process_global_strengths(strengths: Union[List, str]) -> Dict[str, Any]:
    error_report = []
    if not isinstance(strengths, dict):
        logger.error(f"Error on reading dict.")
        error_report.append({
            "type": "dict",
            "message": "Error on reading dict.",
            "data": str(strengths)
        })
        return
   
    if not strengths.get("metrics"):
        logger.error(f"Error, not 'metrics' in file.")
        error_report.append({
            "type": "dict",
            "message": "Error, not 'metrics' in file.",
            "data": str(strengths)
        })
        return
    
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

        # Instance CreatePreFHIR
        try: 
            logger.info(f"Creating PreFHIR for {i}.")
            creator = CreatePreFHIR(strength, round_digits=1)
            resource = creator.render()
            # print(json.dumps(resource, indent=2, sort_keys=False))
        except Exception as e:
            logger.error(f"Fail to create PreFHIR for {i}.")
            error_report.append({
                "type": "PreFHIR",
                "message": "Fail to create PreFHIR",
                "data": str(strength)
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
                "data": str(strength)
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
    
# For a complete strengths file (not too large !! else use process_strengths_by_cats)
def process_strengths_by_cats(i: int, strength: Union[dict, str]) -> Dict[str, Any]:

    obs_list = []
    error_report = []
    total_created = 0
    if not isinstance(strength, dict):
        logger.error(f"Error - not a dict.")
        error_report.append({
            "type": "dict",
            "message": "Error - not a dict.",
            "data": str(strength)
        })
        return
    
    if not strength:
        logger.error(f"Error empty dict.")
        error_report.append({
            "type": "dict",
            "message": "Error empty dict.",
            "data": str(strength)
        })
        return

    # Instance CreatePreFHIR
    try: 
        #logger.info(f"Creating PreFHIR for {i}.")
        creator = CreatePreFHIR(strength, round_digits=1)
        resource = creator.render()
        # print(json.dumps(resource, indent=2, sort_keys=False))
    except Exception as e:
        logger.error(f"Fail to create PreFHIR for {i}.")
        error_report.append({
            "type": "PreFHIR",
            "message": "Fail to create PreFHIR",
            "data": str(strength)
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
            "data": str(strength)
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
    

def pipeline_metrics_by_cats(strengths: List[Any]):
    """
    Full process for strengths by categories
    """
    for i, strength in enumerate(strengths):
        try:
            bundle_json = process_strengths_by_cats(i, strength)
            success = upload_bundle(bundle_json)
            
            if success:
                logger.info("Traitement des 'strengths' terminé avec succès")
                return True
            else:
                logger.info("Erreur lors du traitement des 'strengths'.")
                return False
                
        except Exception as e:
            logger.error(f"Erreur globale : {str(e)}")
            
def pipeline_metrics(strengths: List[Any]):
    """
    Full process for strengths
    """
    try:
        # Create average version of the strengths file
        strengths = average_strenght_results(strengths)
        bundle_json = process_global_strengths(strengths)
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
        strengths = json.load(f)

    # metrics = strengths["metrics"]
    # for i, strength in enumerate(metrics):
    #     try:
    #         bundle_json = process_strengths_by_cats(i, strength)
    #         #print(bundle_json)
    #         success = upload_bundle(bundle_json)
            
    #         if success:
    #             print("Traitement terminé avec succès")
    #         else:
    #             print("Erreur lors de l'upload")
                
    #     except Exception as e:
    #         logger.error(f"Erreur globale : {str(e)}")
            
    try:
        bundle_json = process_global_strengths(strengths)
        #print(bundle_json)
        success = upload_bundle(bundle_json)
        
        if success:
            print("Traitement terminé avec succès")
        else:
            print("Erreur lors de l'upload")
            
    except Exception as e:
        logger.error(f"Erreur globale : {str(e)}")
        
        