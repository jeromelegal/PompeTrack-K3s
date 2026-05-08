from fastapi.testclient import TestClient
import pytest

import main
from main import app


client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "Worker API ready."}


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    js = r.json()
    assert js["status"] == "ok"
    assert isinstance(js["time"], str)


def test_run_worker_iphone_success(mocker):
    pipeline = mocker.patch("main.iphone_json_pipeline", return_value=True)

    result = main.run_worker_iphone(device={})

    assert result == {
        "status": "success",
        "output": "iphone pipeline completed",
    }
    pipeline.assert_called_once_with()


def test_run_worker_iphone_false_is_500(mocker):
    mocker.patch("main.iphone_json_pipeline", return_value=False)

    with pytest.raises(main.HTTPException) as exc_info:
        main.run_worker_iphone(device={})

    assert exc_info.value.status_code == 500
    assert "iphone pipeline failed or no object processed" in exc_info.value.detail


def test_run_worker_iphone_exception_is_500(mocker):
    mocker.patch("main.iphone_json_pipeline", side_effect=RuntimeError("Boom!"))

    with pytest.raises(main.HTTPException) as exc_info:
        main.run_worker_iphone(device={})

    assert exc_info.value.status_code == 500
    assert "Boom!" in exc_info.value.detail


@pytest.mark.parametrize(
    ("endpoint_func", "pipeline_attr", "expected_output"),
    [
        (main.run_worker_manual, "manual_json_pipeline", "manual pipeline completed"),
        (
            main.run_worker_spirometer,
            "spirometer_json_pipeline",
            "spirometer pipeline completed",
        ),
        (main.run_worker_strength, "strength_json_pipeline", "strength pipeline completed"),
        (main.run_worker_medication, "medication_json_pipeline", "medication pipeline completed"),
        (main.run_logs_transfert, "transfert_logs_pipeline", "logs pipeline completed"),
    ],
)
def test_other_pipeline_endpoints_use_boolean_contract(
    mocker,
    endpoint_func,
    pipeline_attr,
    expected_output,
):
    pipeline = mocker.patch(f"main.{pipeline_attr}", return_value=True)

    result = endpoint_func(device={})

    assert result == {"status": "success", "output": expected_output}
    pipeline.assert_called_once_with()
