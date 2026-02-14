import pytest
from utils.manual_metrics import process_global_manuals, process_manuals_by_cats
import json
from unittest.mock import patch, MagicMock

# Fixtures
PAYLOAD = {"metrics":[
    {
        "name":"manual_pain",
        "data":
        {
            "body_system":"http://snomed.info/sct",
            "body_code":"43799004",
            "body_display":"Chest structure",
            "value_value":5,
            "note_text":["fff"],
            "date":"2026-01-07T08:47:13.758796Z"
        }
    },
    {
        "name":"manual_pain",
        "data":
        {
            "body_system":"http://snomed.info/sct",
            "body_code":"77568009",
            "body_display":"Back structure",
            "body_text":"Région dorsale haute",
            "value_value":2,
            "note_text":["tee"],
            "date":"2026-01-07T08:49:21.443598Z"
        }
    }
]}

@pytest.fixture
def dummy_metrics_example():
    """Un dict simulant un fichier metrics."""
    return PAYLOAD

@pytest.fixture
def dummy_metrics__by_cats_example():
    """Un dict simulant un fichier metrics."""
    return PAYLOAD["metrics"][0]
    
@pytest.fixture
def expected_bundle():
    """Le JSON que l’on attend que la fonction renvoie."""
    return {"resourceType": "Bundle", "entry": []}

@pytest.fixture
def mock_build(mocked_build_func):
    mocked_build_func.return_value.json.return_value = expected_bundle
    return mocked_build_func

# Tests for 'process_global_manuals'
@patch('utils.manual_metrics.build_bundle_fhir')
@patch('utils.manual_metrics.logger')
def test_process_global_manuals_success(mock_logger, mock_build,
                                        dummy_metrics_example,
                                        expected_bundle):

    mock_build.return_value.json.return_value = expected_bundle

    result = process_global_manuals(dummy_metrics_example)

    mock_build.assert_called_once()  
    mock_logger.info.assert_any_call('Building bundle.')
    assert result == expected_bundle, "Le retour doit être le JSON du bundle"
 
@patch('utils.manual_metrics.build_bundle_fhir')
@patch('utils.manual_metrics.logger')
def test_process_global_manuals_list(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_global_manuals([]) 

    mock_logger.error.assert_called_with("Error on reading dict.")
    assert result is None   
 
@patch('utils.manual_metrics.build_bundle_fhir')
@patch('utils.manual_metrics.logger')
def test_process_global_manuals_empty(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_global_manuals({}) 

    mock_logger.error.assert_called_with("Error, not 'metrics' in file.")
    assert result is None  
    
    
    
 # Tests for 'process_manuals_by_cats'
@patch('utils.manual_metrics.build_bundle_fhir')
@patch('utils.manual_metrics.logger')
def test_process_manuals_by_cats_success(mock_logger, mock_build,
                                        dummy_metrics__by_cats_example,
                                        expected_bundle):

    mock_build.return_value.json.return_value = expected_bundle

    result = process_manuals_by_cats(0, dummy_metrics__by_cats_example)

    mock_build.assert_called_once()  
    mock_logger.info.assert_any_call('Building bundle.')
    assert result == expected_bundle, "Le retour doit être le JSON du bundle"
 
@patch('utils.manual_metrics.build_bundle_fhir')
@patch('utils.manual_metrics.logger')
def test_process_manuals_by_cats_list(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_manuals_by_cats(0, []) 

    mock_logger.error.assert_called_with("Error - not a dict.")
    assert result is None   
 
@patch('utils.manual_metrics.build_bundle_fhir')
@patch('utils.manual_metrics.logger')
def test_process_manuals_by_cats_empty(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_manuals_by_cats(0, {}) 

    mock_logger.error.assert_called_with("Error empty dict.")
    assert result is None  