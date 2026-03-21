import streamlit as st
import pandas as pd
import numpy as np

from utils.stream_requests import tag_stream_request
from utils.shaping_df import shaping_metrics, df_workouts, df_stateofminds
import streamlit as st

# Config
DEFAULT_LOOKBACK_DAYS = 90
SPIROMETRY_COLS = {
    "Capacité vitale forcée": "FVC",
    "Volume expiratoire forcé en une seconde": "FEV1",
    "Rapport FEV1 / FVC": "Ratio FEV1 / FVC",
    "Volume Expiratoire Maximal en 6 secondes": "FEV6",
    "Vitesse maximale d'expiration": "PEF",
    " Vitesse d'expulsion de l'air à 25% de la FVC": "FVC25",
    " Vitesse d'expulsion de l'air à 50% de la FVC": "FVC50",
    " Vitesse d'expulsion de l'air à 75% de la FVC": "FVC75",
    " Vitesse d'expulsion de l'air entre 25% et 75% de la FVC": "FEF25_75"
}
MANUAL_WEEKLY_COLS = {
    "Heart rate": "FVC",
    "Oxygen saturation in Arterial blood by Pulse oxymetry": "FEV1",
    "Systolic blood pressure": "Ratio FEV1 / FVC",
    "Diastolic blood pressure": "FEV6",
    "Vitesse maximale d'expiration": "PEF",
    " Vitesse d'expulsion de l'air à 25% de la FVC": "FVC25",
    " Vitesse d'expulsion de l'air à 50% de la FVC": "FVC50",
    " Vitesse d'expulsion de l'air à 75% de la FVC": "FVC75",
    " Vitesse d'expulsion de l'air entre 25% et 75% de la FVC": "FEF25_75"
}

# Helpers
def is_admin() -> bool:
    return st.session_state.get("admin", False)

def df_generic(list_metrics):
    global_df = shaping_metrics(list_metrics)
    df = global_df.pivot_table(
        index='timestamp',         
        columns='parameter',        
        values='value'
    )
    unit_map = global_df.set_index('parameter')['unit'].to_dict()
    df = df.rename(columns=lambda col: f"{col} ({unit_map.get(col, '')})") 
    df = df.reset_index()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
    # st.dataframe(df)
    return df

# def df_workouts(list_metrics):
#     df = shaping_metrics(list_metrics)
#     df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
#     df["duration_min"] = round(df["value"] / 60, 0)
#     return df

def df_spirometry(list_metrics):
    global_df = shaping_metrics(list_metrics)
    df = global_df.pivot_table(
        index='timestamp',         
        columns='parameter',        
        values='value'
    )
    df = df.rename(columns=SPIROMETRY_COLS)
    df = df.reset_index()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
    # st.dataframe(df)
    return df

def df_weekly(list_metrics):
    global_df = shaping_metrics(list_metrics)
    #st.dataframe(global_df)
    df = global_df.pivot_table(
        index='timestamp',         
        columns='parameter',        
        values='value'
    )
    #st.dataframe(df)
    unit_map = global_df.set_index('parameter')['unit'].to_dict()
    df = df.rename(columns=lambda col: f"{col} ({unit_map.get(col, '')})") 
    df = df.reset_index()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
    # st.dataframe(df)
    return df

def df_monthly(list_metrics):
    global_df = shaping_metrics(list_metrics)
    #st.dataframe(global_df)
    df = global_df.pivot_table(
        index='timestamp',         
        columns='parameter',        
        values='value'
    )
    unit_map = global_df.set_index('parameter')['unit'].to_dict()
    df = df.rename(columns=lambda col: f"{col} ({unit_map.get(col, '')})") 
    df = df.reset_index()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
    # st.dataframe(df)
    return df


def shape_df(stream_name, data):
    if stream_name == "metrics":
        return df_generic(data)
    elif stream_name == "workouts":
        return df_workouts(data)
    elif stream_name == "stateofminds":
        return df_stateofminds(data)
    elif stream_name == "spirometer":
        return df_spirometry(data)
    elif stream_name == "manual_weekly":
        return df_weekly(data)
    elif stream_name == "manual_monthly":
        return df_monthly(data)
    else:
        return Exception
    
def ensure_datetime(df, col='timestamp'):
    if df is None:
        return df
    if col in df.columns and not pd.api.types.is_datetime64_any_dtype:
        df[col] = pd.to_datetime(df[col])
    return df

def long_from_wide(df):
    if df is None:
        return None
    if 'metric' in df.columns and 'value' in df.columns:
        return df.copy()
    df = df.copy()
    # detect timestamp column or index
    if 'timestamp' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index().rename(columns={'index':'timestamp'})
        else:
            # fallback: assume first col is timestamp
            df = df.rename(columns={df.columns[0]:'timestamp'})
    df = ensure_datetime(df, 'timestamp')
    id_cols = ['timestamp']
    value_cols = [c for c in df.columns if c not in id_cols]
    long = df.melt(id_vars='timestamp', value_vars=value_cols, var_name='metric', value_name='value')
    return long

def rolling_trend(series, window=7):
    return series.rolling(window, min_periods=1).mean()

def slope_of_trend(df, xcol='timestamp', ycol='value'):
    if df is None or df.empty or df[ycol].isnull().all():
        return None
    tmp = df.dropna(subset=[ycol]).copy()
    tmp['x'] = (pd.to_datetime(tmp[xcol]) - pd.to_datetime(tmp[xcol]).min()).dt.total_seconds() / 86400.0
    if tmp['x'].nunique() < 2:
        return 0.0
    coeff = np.polyfit(tmp['x'], tmp[ycol], 1)
    return float(coeff[0])

def interpret_trend(slope, unit='', threshold_small=0.01):
    if slope is None:
        return "Données insuffisantes."
    if abs(slope) < threshold_small:
        return f"Stable (variation faible, ≈ {slope:.3g} {unit}/jour)."
    if slope > 0:
        return f"Tendance à la hausse ({slope:.3g} {unit}/jour)."
    else:
        return f"Tendance à la baisse ({slope:.3g} {unit}/jour)."
        
# Data loading
@st.cache_data(show_spinner=True)
def load_data(stream_name: str, lookback_days: int, use_mock: bool):
    if use_mock:
        return _load_mock(stream_name)

    data = tag_stream_request(stream_name, lookback_days)

    if data is None:
        return None

    try:
        return shape_df(stream_name, data)
    except Exception as e:
        st.markdown(f"Nothing to load : {e}")
        return None


# Mock data
def _load_mock(stream_name: str):
    from utils.common import generate_mock_data
    (
        metrics,
        workouts,
        som,
        spirometry,
        manual_weekly,
        manual_monthly,
    ) = generate_mock_data()

    return {
        "metrics": metrics,
        "workouts": workouts,
        "stateofminds": som,
        "spirometer": spirometry,
        "manual_weekly": manual_weekly,
        "manual_monthly": manual_monthly,
    }.get(stream_name)

def generate_mock_data():
    idx = pd.date_range(end=pd.Timestamp.now(), periods=365, freq="D")

    metrics = pd.DataFrame({
        'timestamp': idx,
        'mindful_minutes': np.maximum(0, np.random.normal(10, 5, len(idx)).round(1)),
        'step_count': np.abs((np.random.normal(7000, 2500, len(idx))).astype(int)),
        'walking_running_distance': np.abs(np.random.normal(4.5, 2.0, len(idx)).round(2)),
        'resting_heart_rate': np.round(np.random.normal(60, 4, len(idx)), 1),
        'sleep_analysis': np.round(np.random.normal(7.2, 1.0, len(idx)), 2),
        'active_energy': np.round(np.abs(np.random.normal(400, 120, len(idx))), 1),
        'walking_speed': np.abs(np.random.normal(1.3, 0.25, len(idx))),
    })

    workouts = pd.DataFrame({
        'timestamp': pd.to_datetime(np.random.choice(idx, size=40)),
        'parameter': np.random.choice(['yoga', 'exercice', 'kine'], size=40, p=[0.3, 0.5, 0.2]),
        'duration_min': np.random.randint(10, 90, size=40),
        'calories': np.random.randint(50, 600, 40),
    })

    som = pd.DataFrame({
        'timestamp': idx,
        'mood_score': np.clip(np.random.normal(6.5, 1.2, len(idx)), 1, 10)
    })

    spirometry = pd.DataFrame({
        'timestamp': pd.to_datetime(np.random.choice(idx, size=30)),
        'FVC': np.round(np.random.normal(4.5, 0.5, 30), 2),
        'FEV1': np.round(np.random.normal(2.8, 0.4, 30), 2),
        'FEV6': np.round(np.random.normal(6.3, 0.4, 30), 2),
        'FVC25': np.round(np.random.normal(1.5, 0.5, 30), 2),
        'FVC50': np.round(np.random.normal(2.5, 0.5, 30), 2),
        'FVC75': np.round(np.random.normal(3.5, 0.5, 30), 2),
        'PEF': np.round(np.random.normal(6.0, 1.0, 30), 2),
        'FEF25_75': np.round(np.random.normal(2.5, 0.6, 30), 2),
    })

    start = idx.min()
    weeks = pd.date_range(start=start, end=idx.max(), freq='7D')
    manual_weekly = pd.DataFrame({
        'timestamp': weeks,
        'poids_kg': np.round(75 + np.random.normal(0, 0.6, len(weeks)), 1),
        'fc': np.round(np.random.normal(70, 6, len(weeks)), 1),
        'tension_sys': np.round(np.random.normal(120, 8, len(weeks)), 0),
        'tension_dia': np.round(np.random.normal(78, 6, len(weeks)), 0),
        'SpO2': np.round(np.random.normal(97, 1.2, len(weeks)), 1),
        'douleurs': np.random.randint(0, 4, len(weeks)),
    })
    months = pd.date_range(start=start, end=idx.max(), freq='30D')
    manual_monthly = pd.DataFrame({
        'timestamp': months,
        'mollet_cm': np.round(np.random.normal(38, 1, len(months)), 1),
        'cuisse_cm': np.round(np.random.normal(55, 1.5, len(months)), 1),
        'taille_cm': np.round(np.random.normal(84, 1.8, len(months)), 1),
        'hanches_cm': np.round(np.random.normal(98, 2.0, len(months)), 1),
        'cou_cm': np.round(np.random.normal(37, 0.8, len(months)), 1),
        'bras_kgf': np.round(np.random.normal(32, 3, len(months)), 1),
        'quadriceps_kgf': np.round(np.random.normal(120, 12, len(months)), 1),
        'temps_distance_jardin_min': np.round(np.random.normal(20, 8, len(months)), 0),
    })
    return metrics, workouts, som, spirometry, manual_weekly, manual_monthly