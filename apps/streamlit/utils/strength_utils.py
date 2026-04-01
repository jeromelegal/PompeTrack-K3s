import numpy as np

# Function to compute stats
def compute_trials_stats(trials):
    """
    Compute stats for a list of trials.
    """
    vals = [v for v in trials if v is not None]
    if not vals:
        return {"max": None, "mean": None, "fatigue_index_pct": None}
    mx = float(np.max(vals))
    mean = float(np.mean(vals))
    if len(vals) >= 3 and vals[0] != 0:
        fi = (vals[0] - vals[2]) / vals[0] * 100.0
        fi = float(fi)
    else:
        fi = None
    return {"max": mx, "mean": mean, "fatigue_index_pct": fi}

# Function to verify that x can be converted to float
def safe_float(x):
    """
    Verify that x can be converted to float.
    """
    try:
        return float(x)
    except Exception:
        return None

# Function to flag asymmetry
def flag_asymmetry(left_max, right_max, threshold_pct=10.0):
    """
    Returns asymmetry ratio and flag.
    """
    if left_max is None or right_max is None:
        return None, False, "Données insuffisantes pour asymétrie."
    if right_max == 0:
        return None, True, "Force droite = 0 -> vérifier saisie."
    ratio = (left_max - right_max) / right_max * 100.0
    flag = abs(ratio) >= threshold_pct
    msg = f"Différence gauche-droite = {ratio:.1f}% (seuil {threshold_pct}%)."
    if flag:
        msg = "⚠️ " + msg
    return ratio, flag, msg

# Function to interpret fatigue
def interpret_fatigue(fi_pct):
    """
    Interpret fatigue index.
    """
    if fi_pct is None:
        return "Pas assez d'essais pour calculer la fatigabilité."
    if fi_pct <= 5:
        return f"Faible fatigabilité ({fi_pct:.1f}% de chute)."
    elif fi_pct <= 20:
        return f"Fatigabilité modérée ({fi_pct:.1f}%)."
    else:
        return f"Fatigabilité élevée ({fi_pct:.1f}%)."
