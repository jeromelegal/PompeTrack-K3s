import pytest
from utils.iphone_stateofminds import process_global_stateofminds
import json
from unittest.mock import patch, MagicMock

# Fixtures
@pytest.fixture
def dummy_workout_list():
    """Un petit tableau de dicts simulant un fichier workout."""
    return [
        {
            "kind": "momentary_emotion",
            "associations": [
            "tasks",
            "work",
            "family"
            ],
            "id": "0630A61B-2B8F-4BFA-A140-5C9DB6193410",
            "valenceClassification": "slightly_pleasant",
            "end": "2025-12-07T13:32:10Z",
            "valence": 0.33333333333333326,
            "start": "2025-12-07T13:32:10Z",
            "labels": [
            "proud",
            "satisfied"
            ]
        }
    ]

@pytest.fixture
def expected_bundle():
    """Le JSON que l’on attend que la fonction renvoie."""
    return {"resourceType": "Bundle", "entry": []}

@pytest.fixture
def mock_build(mocked_build_func):
    mocked_build_func.return_value.json.return_value = expected_bundle
    return mocked_build_func


@patch('utils.iphone_stateofminds.build_bundle_fhir')
@patch('utils.iphone_stateofminds.logger')
def test_process_global_stateofminds_success(mock_logger, mock_build,
                                        dummy_workout_list,
                                        expected_bundle):

    mock_build.return_value.json.return_value = expected_bundle

    result = process_global_stateofminds(dummy_workout_list)

    mock_build.assert_called_once()  
    mock_logger.info.assert_any_call('Building bundle.')
    assert result == expected_bundle, "Le retour doit être le JSON du bundle"
    
@patch('utils.iphone_stateofminds.build_bundle_fhir')
@patch('utils.iphone_stateofminds.logger')
def test_process_global_stateofminds_empty(mock_logger, mock_build):
    mock_build.return_value.json.return_value = None  

    result = process_global_stateofminds([]) 

    mock_logger.error.assert_called_with("Fail to build bundle.")
    assert result is None  