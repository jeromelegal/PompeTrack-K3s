import pytest
from unittest.mock import MagicMock
from pipeline_manual import manual_json_pipeline


@pytest.fixture
def mock_external(monkeypatch):
    """
    Patche toutes les fonctions externes du worker.
    Retourne un mapping : {'function_name': mock_obj}
    """
    from pipeline_manual import get_object_list, get_object_json, move_object
    from utils.manual_metrics import pipeline_metrics

    mocks = {
        'get_object_list': MagicMock(),
        'get_object_json': MagicMock(),
        'move_object': MagicMock(),
        'pipeline_metrics': MagicMock(),
    }

    monkeypatch.setattr('pipeline_manual.get_object_list', mocks['get_object_list'])
    monkeypatch.setattr('pipeline_manual.get_object_json', mocks['get_object_json'])
    monkeypatch.setattr('pipeline_manual.move_object', mocks['move_object'])
    monkeypatch.setattr('pipeline_manual.pipeline_metrics', mocks['pipeline_metrics'])

    return mocks

# Tests for `manual_json_pipeline`   
def test_pipeline_success(mock_external):
    # Simulate Minio returning 1 object
    mock_external["get_object_list"].return_value = ["file1.json"]
    
    # Simulate json object
    mock_obj = {"metrics":[
    {
        "name": "manual_weight",
        "type": "weekly",
        "data": [
            {
                "qty": 75.0
            }
        ]
    }
    ]}
    
    # Return pipeline
    mock_external["pipeline_metrics"].return_value = "metrics_result"
    
    result = manual_json_pipeline()
    assert result == True
    
    # Verify everything called once
    mock_external['get_object_list'].assert_called_once_with(bucket='raw-manual')
    mock_external['get_object_json'].assert_called_once_with(bucket='raw-manual', object_name='file1.json')
    
    # Verify `move_object` called once
    mock_external['move_object'].assert_called_once_with(
        object_name='file1.json',
        source_bucket='raw-manual',
        destination_bucket='processed-fhir'
    )
    
def test_pipeline_no_objects(mock_external):
    mock_external['get_object_list'].return_value = []

    result = manual_json_pipeline()

    assert result is False
    mock_external['get_object_json'].assert_not_called()
    mock_external['move_object'].assert_not_called()
    

def test_pipeline_metrics_error(mock_external):
    mock_external['get_object_list'].return_value = ['file1.json']

    mock_external['get_object_json'].return_value = {
        'data': {"name": "toto"}
    }

    # Simulate exception
    mock_external['pipeline_metrics'].side_effect = RuntimeError("bad metrics")

    with pytest.raises(RuntimeError, match="bad metrics"):
        manual_json_pipeline()

    mock_external['move_object'].assert_not_called()