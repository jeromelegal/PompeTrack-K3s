import pytest
from utils.spirometer_metrics import process_global_spirometer, process_spirometer_by_cats
import json
from unittest.mock import patch, MagicMock

# Fixtures
PAYLOAD = {
    "metrics": [
        {
            "name": "FVC",
            "data": [
                {
                    "qty": "5.03",
                    "date": "2026-01-09T11:33:58"
                }
            ],
            "units": "L"
        },
        {
            "name": "FEV1",
            "data": [
                {
                    "qty": "3.88",
                    "date": "2026-01-09T11:33:58"
                }
            ],
            "units": "L"
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

# Tests for 'process_global_spirometer'
@patch('utils.spirometer_metrics.build_bundle_fhir')
@patch('utils.spirometer_metrics.logger')
def test_process_global_spirometer_success(mock_logger, mock_build,
                                        dummy_metrics_example,
                                        expected_bundle):

    mock_build.return_value.json.return_value = expected_bundle

    result = process_global_spirometer(dummy_metrics_example)

    mock_build.assert_called_once()  
    mock_logger.info.assert_any_call('Building bundle.')
    assert result == expected_bundle, "Le retour doit être le JSON du bundle"
 
@patch('utils.spirometer_metrics.build_bundle_fhir')
@patch('utils.spirometer_metrics.logger')
def test_process_global_spirometer_list(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_global_spirometer([]) 

    mock_logger.error.assert_called_with("Error on reading dict.")
    assert result is None   
 
@patch('utils.spirometer_metrics.build_bundle_fhir')
@patch('utils.spirometer_metrics.logger')
def test_process_global_spirometer_empty(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_global_spirometer({}) 

    mock_logger.error.assert_called_with("Error, not 'metrics' in file.")
    assert result is None  
    
    
    
 # Tests for 'process_spirometer_by_cats'
@patch('utils.spirometer_metrics.build_bundle_fhir')
@patch('utils.spirometer_metrics.logger')
def test_process_spirometer_by_cats_success(mock_logger, mock_build,
                                        dummy_metrics__by_cats_example,
                                        expected_bundle):

    mock_build.return_value.json.return_value = expected_bundle

    result = process_spirometer_by_cats(0, dummy_metrics__by_cats_example)

    mock_build.assert_called_once()  
    mock_logger.info.assert_any_call('Building bundle.')
    assert result == expected_bundle, "Le retour doit être le JSON du bundle"
 
@patch('utils.spirometer_metrics.build_bundle_fhir')
@patch('utils.spirometer_metrics.logger')
def test_process_spirometer_by_cats_list(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_spirometer_by_cats(0, []) 

    mock_logger.error.assert_called_with("Error - not a dict.")
    assert result is None   
 
@patch('utils.spirometer_metrics.build_bundle_fhir')
@patch('utils.spirometer_metrics.logger')
def test_process_spirometer_by_cats_empty(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_spirometer_by_cats(0, {}) 

    mock_logger.error.assert_called_with("Error empty dict.")
    assert result is None  