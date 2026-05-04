from unittest.mock import MagicMock, patch

from utils.iphone_medicationadministrations import process_global_medications


def test_process_global_medications_filters_completed_status():
    medications = [{"status": "Pris", "medication": "test"}]
    completed = MagicMock(status="completed")

    with (
        patch("utils.iphone_medicationadministrations.CreatePreFHIR_medicationadministration") as creator_cls,
        patch("utils.iphone_medicationadministrations.to_fhir_medicationadministration", return_value=completed),
        patch("utils.iphone_medicationadministrations.upload_medicationadministration_bundles_in_chunks", return_value=True) as upload,
    ):
        creator = creator_cls.return_value
        creator.process.return_value = (medications, None, [])

        assert process_global_medications(medications) is True

    upload.assert_called_once_with([completed], chunk_size=5)


def test_process_global_medications_ignores_not_done_status():
    medications = [{"status": "Ignoré", "medication": "test"}]
    not_done = MagicMock(status="not-done")

    with (
        patch("utils.iphone_medicationadministrations.CreatePreFHIR_medicationadministration") as creator_cls,
        patch("utils.iphone_medicationadministrations.to_fhir_medicationadministration", return_value=not_done),
        patch("utils.iphone_medicationadministrations.upload_medicationadministration_bundles_in_chunks", return_value=True) as upload,
    ):
        creator = creator_cls.return_value
        creator.process.return_value = (medications, None, [])

        assert process_global_medications(medications) is True

    upload.assert_not_called()
