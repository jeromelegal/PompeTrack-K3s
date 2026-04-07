from libs.db_service import get_id_medication, get_all_medications
import json
import logger

logger = logging.getLogger(__name__)

def create_correspondence_dict():
    """
    Creates a dictionary mapping source system to canonical key to
    MedPLUM medication id.
    Returns a dictionary with the following structure:
    {
        "source_system": {
            "normalized_name ": "medplum_medication_id",
            ...
        },
        ...
    }
    """
    status = False
    all_medications = get_all_medications()
    correspondence_dict = {}
    for medication in all_medications:
        source_system = medication["source_system"]
        normalized_name  = medication["normalized_name "]
        medplum_medication_id = medication["medplum_medication_id"]
        if source_system not in correspondence_dict:
            correspondence_dict[source_system] = {}
        correspondence_dict[source_system][normalized_name ] = medplum_medication_id
    
    try:
        with open("/tmp/medication_correspondence.json", "w") as f:
            json.dump(correspondence_dict, f)
            status = True
    except Exception as e:
        logger.error(f"Error saving medication correspondence: {e}")
        
    return status

def update_correspondence_dict():
    """
    Updates the correspondence dictionary by adding new medications.
    Returns a dictionary with the following structure:
    {
        "source_system": {
            "normalized_name ": "medplum_medication_id",
            ...
        },
        ...
    }
    """
    correspondence_status = create_correspondence_dict()
    
    return correspondence_status

def normalize_name(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value

def get_id_medication(source_system, name):
    """
    Returns the MedPLUM medication id for a given source system and canonical key.
    """
    normalized_name = normalize_name(name)
    with open("/tmp/medication_correspondence.json", "r") as f:
        correspondence_dict = json.load(f)    
    if source_system in correspondence_dict and normalized_name  in correspondence_dict[source_system]:
        return correspondence_dict[source_system][normalized_name ]
    else:
        update_correspondence_dict()
        if source_system in correspondence_dict and normalized_name  in correspondence_dict[source_system]:
            return correspondence_dict[source_system][normalized_name ]
        else:
            logger.error(f"Medication not found for source system: {source_system} and canonical key: {normalized_name }")
            return None
        
    return None

