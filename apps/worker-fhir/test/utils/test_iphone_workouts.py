import pytest
from unittest.mock import patch, MagicMock
from utils.iphone_workouts import process_global_workouts


@pytest.fixture
def dummy_workout_list():
    """Données d’entrée cohérentes avec l’iPhone."""
    return [
        {
            "id": "19323448-8391-472B-9997-8E02A36615AS",
            "name": "Yoga",
            "start": "2025-01-01 01:01:01 +0100",
            "end": "2025-01-01 03:01:01 +0100",
            "duration": 2.0,
        }
    ]


@patch("utils.iphone_workouts.upload_bundle")
@patch("utils.iphone_workouts.build_bundle_fhir")
@patch("utils.iphone_workouts.to_fhir_observation")
@patch("utils.iphone_workouts.CreatePreFHIR_workouts")
def test_process_workout_without_children(
    mock_creator_cls,
    mock_to_fhir,
    mock_build_bundle,
    mock_upload,
    dummy_workout_list
):
    """
    Cas : aucune sous-observation → bundle standard
    """

    # ----- CreatePreFHIR_workouts.process -----
    mock_creator = MagicMock()
    mock_creator.process.return_value = (
        [{"fake": "observation"}],  # observations
        0,                           # parent_index
        []                           # children_indices → chemin standard
    )
    mock_creator_cls.return_value = mock_creator

    # ----- to_fhir_observation -----
    mock_to_fhir.return_value = {"resourceType": "Observation"}

    # ----- build_bundle_fhir().json() -----
    mock_bundle = MagicMock()
    mock_bundle.json.return_value = {"resourceType": "Bundle"}
    mock_build_bundle.return_value = mock_bundle

    # ----- upload_bundle -----
    mock_upload.return_value = True

    result = process_global_workouts(dummy_workout_list)

    assert result is True
    mock_creator.process.assert_called_once()
    mock_build_bundle.assert_called_once()
    mock_upload.assert_called_once()


@patch("utils.iphone_workouts.upload_transaction_bundle")
@patch("utils.iphone_workouts.build_transaction_bundle")
@patch("utils.iphone_workouts.CreatePreFHIR_workouts")
def test_process_workout_with_children(
    mock_creator_cls,
    mock_build_transaction,
    mock_upload_transaction,
    dummy_workout_list
):
    """
    Cas : sous-observations → transaction bundle
    """

    mock_creator = MagicMock()
    mock_creator.process.return_value = (
        [{"parent": "obs"}, {"child": "obs"}],
        0,
        [1]  # children_indices non vide
    )
    mock_creator_cls.return_value = mock_creator

    mock_build_transaction.return_value = {"resourceType": "Bundle"}
    mock_upload_transaction.return_value = True

    result = process_global_workouts(dummy_workout_list)

    assert result is True
    mock_build_transaction.assert_called_once()
    mock_upload_transaction.assert_called_once()
