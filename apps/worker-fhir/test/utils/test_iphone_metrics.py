import pytest
from utils.iphone_metrics import process_global_metrics, process_metrics_by_cats
import json
from unittest.mock import patch, MagicMock

# Fixtures
PAYLOAD = [
         {
  "units": "hr",
  "data": [
    {
      "sleepEnd": "2025-01-01 07:00:01 +0200",
      "awake": 0.43333333333333335,
      "rem": 1.0333333333333332,
      "inBedEnd": "2025-01-01 07:00:00 +0200",
      "inBedStart": "2025-01-01 00:00:00 +0200",
      "totalSleep": 7.0,
      "date": "2025-01-01 00:00:00 +0200",
      "inBed": 7.0,
      "asleep": 0,
      "source": "Connect",
      "deep": 1.9,
      "core": 4.99,
      "sleepStart": "2025-01-01 00:00:00 +0200"
    }
  ],
  "name": "sleep_analysis"
}
    ]

@pytest.fixture
def dummy_workout_list():
    """Un tableau de dicts simulant un fichier workout."""
    return PAYLOAD
  
@pytest.fixture
def dummy_workout_by_cats_list():
    """Un tableau de dicts simulant un fichier workout."""
    return PAYLOAD[0]

@pytest.fixture
def expected_bundle():
    """Le JSON que l’on attend que la fonction renvoie."""
    return {"resourceType": "Bundle", "entry": []}

@pytest.fixture
def mock_build(mocked_build_func):
    mocked_build_func.return_value.json.return_value = expected_bundle
    return mocked_build_func

# Tests for 'process_global_metrics'
@patch('utils.iphone_metrics.build_bundle_fhir')
@patch('utils.iphone_metrics.logger')
def test_process_global_metrics_success(mock_logger, mock_build,
                                        dummy_workout_list,
                                        expected_bundle):

    mock_build.return_value.json.return_value = expected_bundle

    result = process_global_metrics(dummy_workout_list)

    mock_build.assert_called_once()  
    mock_logger.info.assert_any_call('Building bundle.')
    assert result == expected_bundle, "Le retour doit être le JSON du bundle"
    
@patch('utils.iphone_metrics.build_bundle_fhir')
@patch('utils.iphone_metrics.logger')
def test_process_global_metrics_empty(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_global_metrics([]) 

    mock_logger.error.assert_called_with("Fail to build bundle.")
    assert result is None  
    
# Tests for 'process_metrics_by_cats'
@patch('utils.iphone_metrics.build_bundle_fhir')
@patch('utils.iphone_metrics.logger')
def test_process_metrics_by_cats_success(mock_logger, mock_build,
                                        dummy_workout_by_cats_list,
                                        expected_bundle):

    mock_build.return_value.json.return_value = expected_bundle

    result = process_metrics_by_cats(0, dummy_workout_by_cats_list)

    mock_build.assert_called_once()  
    mock_logger.info.assert_any_call('Building bundle.')
    assert result == expected_bundle, "Le retour doit être le JSON du bundle"
    
@patch('utils.iphone_metrics.build_bundle_fhir')
@patch('utils.iphone_metrics.logger')
def test_process_metrics_by_cats_empty(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_metrics_by_cats(0, []) 

    mock_logger.error.assert_called_with("Error on reading dict.")
    assert result is None  