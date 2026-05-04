import pytest
from unittest.mock import MagicMock
from pipeline_iphone import split_json
from pipeline_iphone import iphone_json_pipeline

@pytest.fixture
def mock_external(monkeypatch):
    """
    Patche toutes les fonctions externes du worker.
    Retourne un mapping : {'function_name': mock_obj}
    """
    from pipeline_iphone import get_object_list, get_object_json, move_object
    from utils.iphone_metrics import pipeline_metrics
    from utils.iphone_workouts import pipeline_workouts
    from utils.iphone_stateofminds import pipeline_stateofminds
    from utils.iphone_symptoms import pipeline_symptoms
    from utils.iphone_medicationadministrations import pipeline_medications

    mocks = {
        'get_object_list': MagicMock(),
        'get_object_json': MagicMock(),
        'move_object': MagicMock(),
        'pipeline_metrics': MagicMock(),
        'pipeline_workouts': MagicMock(),
        'pipeline_stateofminds': MagicMock(),
        'pipeline_symptoms': MagicMock(),
        'pipeline_medications': MagicMock(),
    }

    monkeypatch.setattr('pipeline_iphone.get_object_list', mocks['get_object_list'])
    monkeypatch.setattr('pipeline_iphone.get_object_json', mocks['get_object_json'])
    monkeypatch.setattr('pipeline_iphone.move_object', mocks['move_object'])
    monkeypatch.setattr('pipeline_iphone.pipeline_metrics', mocks['pipeline_metrics'])
    monkeypatch.setattr('pipeline_iphone.pipeline_workouts', mocks['pipeline_workouts'])
    monkeypatch.setattr('pipeline_iphone.pipeline_stateofminds', mocks['pipeline_stateofminds'])
    monkeypatch.setattr('pipeline_iphone.pipeline_symptoms', mocks['pipeline_symptoms'])
    monkeypatch.setattr('pipeline_iphone.pipeline_medications', mocks['pipeline_medications'])

    return mocks

# Test for `split_json`
def test_split_json_basic():
    input_file = {
        'data': {
            'metrics':    {'heart_rate': 80},
            'workouts':   [{'name': 'run', 'duration': 30}],
            'stateOfMind': [{'mood': 'happy'}],
            'extra':     'ignored'  
        }
    }

    metrics, workouts, stateofminds, symptoms, medications = split_json(input_file)

    assert metrics == {'heart_rate': 80}
    assert workouts == [{'name': 'run', 'duration': 30}]
    assert stateofminds == [{'mood': 'happy'}]
    assert symptoms is None
    assert medications is None
    

# Tests for `iphone_json_pipeline`   
def test_pipeline_success(mock_external):
    # Simulate Minio returning 1 object
    mock_external['get_object_list'].return_value = ['file1.json']

    # Simulate json object
    mock_obj = {
        'data': {
            'metrics':     {'hr': 70},
            'workouts':    [{'type': 'swim'}],
            'stateOfMind': [{'mood': 'calm'}],
            'symptoms':    [{'name': 'fatigue'}],
            'medications': [{'name': 'test'}],
        }
    }
    mock_external['get_object_json'].return_value = mock_obj

    # Return pipelines
    mock_external['pipeline_metrics'].return_value = 'metrics_result'
    mock_external['pipeline_workouts'].return_value = 'workouts_result'
    mock_external['pipeline_stateofminds'].return_value = 'state_result'
    mock_external['pipeline_symptoms'].return_value = 'symptoms_result'
    mock_external['pipeline_medications'].return_value = 'medications_result'
    
    result = iphone_json_pipeline()
    assert result is True

    # Verify everything called once
    mock_external['get_object_list'].assert_called_once_with(bucket='raw-iphone')
    mock_external['get_object_json'].assert_called_once_with(bucket='raw-iphone', object_name='file1.json')
    mock_external['pipeline_metrics'].assert_called_once_with({'hr': 70})
    mock_external['pipeline_workouts'].assert_called_once_with([{'type': 'swim'}])
    mock_external['pipeline_stateofminds'].assert_called_once_with([{'mood': 'calm'}])
    mock_external['pipeline_symptoms'].assert_called_once_with([{'name': 'fatigue'}])
    mock_external['pipeline_medications'].assert_called_once_with([{'name': 'test'}])

    # Verify `move_object` called once
    mock_external['move_object'].assert_called_once_with(
        object_name='file1.json',
        source_bucket='raw-iphone',
        destination_bucket='processed-fhir'
    )
    
def test_pipeline_no_objects(mock_external):
    mock_external['get_object_list'].return_value = []

    result = iphone_json_pipeline()

    assert result is False
    mock_external['get_object_json'].assert_not_called()
    mock_external['move_object'].assert_not_called()
    

def test_pipeline_metrics_error(mock_external):
    mock_external['get_object_list'].return_value = ['file1.json']

    mock_external['get_object_json'].return_value = {
        'data': {'metrics': {'foo': 'bar'}, 'workouts': None, 'stateOfMind': None}
    }

    # Simulate exception
    mock_external['pipeline_metrics'].side_effect = RuntimeError("bad metrics")

    with pytest.raises(RuntimeError, match="bad metrics"):
        iphone_json_pipeline()

    mock_external['move_object'].assert_not_called()
