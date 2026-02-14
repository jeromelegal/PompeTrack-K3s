import pandas as pd
import pytest

from utils.shaping_df import shaping_metrics

@pytest.fixture
def full_metric():
    return {
        "category": [{"coding": [{"display": "Vitals"}]}],
        "code": {"coding": [{"display": "Heart rate"}]},
        "effectiveDateTime": "2025-01-01T10:00:00Z",
        "performer": [{"display": "Patient"}],
        "valueQuantity": {"value": 72, "unit": "bpm"},
        "device": {"display": "Polar H10"},
    }

@pytest.fixture
def minimal_metric():
    return {
        "category": [{"coding": [{"display": "Vitals"}]}],
        "code": {"coding": [{"display": "Weight"}]},
        "effectiveDateTime": "2025-01-01T10:00:00Z",
    }



def test_shaping_metrics_returns_dataframe(full_metric):
    df = shaping_metrics([full_metric])
    assert isinstance(df, pd.DataFrame)

def test_shaping_metrics_columns(full_metric):
    df = shaping_metrics([full_metric])

    assert list(df.columns) == [
        "category",
        "parameter",
        "timestamp",
        "performer",
        "value",
        "unit",
        "device",
    ]

def test_shaping_metrics_full_metric(full_metric):
    df = shaping_metrics([full_metric])

    row = df.iloc[0]
    assert row["category"] == "Vitals"
    assert row["parameter"] == "Heart rate"
    assert row["timestamp"] == "2025-01-01T10:00:00Z"
    assert row["performer"] == "Patient"
    assert row["value"] == 72
    assert row["unit"] == "bpm"
    assert row["device"] == "Polar H10"

def test_shaping_metrics_missing_optional_fields(minimal_metric):
    df = shaping_metrics([minimal_metric])
    row = df.iloc[0]

    assert row["performer"] is None
    assert row["value"] is None
    assert row["unit"] is None
    assert row["device"] is None

def test_shaping_metrics_multiple_rows(full_metric, minimal_metric):
    df = shaping_metrics([full_metric, minimal_metric])

    assert len(df) == 2
    assert df.iloc[1]["parameter"] == "Weight"

def test_shaping_metrics_empty_list():
    df = shaping_metrics([])
    assert isinstance(df, pd.DataFrame)
    assert df.empty
