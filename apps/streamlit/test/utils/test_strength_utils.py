import numpy as np
from utils.strength_utils import compute_trials_stats, safe_float, flag_asymmetry, interpret_fatigue

def test_compute_trials_stats_empty():
    result = compute_trials_stats([])
    assert result == {
        "max": None,
        "mean": None,
        "fatigue_index_pct": None
    }


def test_compute_trials_stats_only_none():
    result = compute_trials_stats([None, None])
    assert result["max"] is None
    assert result["mean"] is None
    assert result["fatigue_index_pct"] is None


def test_compute_trials_stats_nominal_with_fatigue():
    trials = [100, 90, 80]
    result = compute_trials_stats(trials)

    assert result["max"] == 100.0
    assert result["mean"] == 90.0
    assert result["fatigue_index_pct"] == 20.0


def test_compute_trials_stats_less_than_3_trials():
    trials = [100, 90]
    result = compute_trials_stats(trials)

    assert result["fatigue_index_pct"] is None


def test_compute_trials_stats_first_value_zero():
    trials = [0, 50, 40]
    result = compute_trials_stats(trials)

    assert result["fatigue_index_pct"] is None


def test_safe_float_valid_number():
    assert safe_float(12.3) == 12.3


def test_safe_float_numeric_string():
    assert safe_float("45.6") == 45.6


def test_safe_float_invalid_string():
    assert safe_float("abc") is None


def test_safe_float_none():
    assert safe_float(None) is None


def test_flag_asymmetry_missing_data():
    ratio, flag, msg = flag_asymmetry(None, 100)
    assert ratio is None
    assert flag is False
    assert "Données insuffisantes" in msg


def test_flag_asymmetry_right_zero():
    ratio, flag, msg = flag_asymmetry(50, 0)
    assert ratio is None
    assert flag is True
    assert "Force droite = 0" in msg


def test_flag_asymmetry_no_flag():
    ratio, flag, msg = flag_asymmetry(105, 100, threshold_pct=10)
    assert round(ratio, 1) == 5.0
    assert flag is False


def test_flag_asymmetry_with_flag():
    ratio, flag, msg = flag_asymmetry(130, 100, threshold_pct=10)
    assert round(ratio, 1) == 30.0
    assert flag is True
    assert msg.startswith("⚠️")



def test_interpret_fatigue_none():
    msg = interpret_fatigue(None)
    assert "Pas assez d'essais" in msg


def test_interpret_fatigue_low():
    msg = interpret_fatigue(3.0)
    assert "Faible fatigabilité" in msg


def test_interpret_fatigue_moderate():
    msg = interpret_fatigue(15.0)
    assert "modérée" in msg


def test_interpret_fatigue_high():
    msg = interpret_fatigue(30.0)
    assert "élevée" in msg
