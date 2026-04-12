import streamlit as st
import pandas as pd
import numpy as np
from utils.common import load_data, is_admin, long_from_wide
from utils.common import ensure_datetime, rolling_trend, slope_of_trend, interpret_trend
import plotly.express as px
import plotly.graph_objects as go

STEP_COUNT = "Number of steps in 24 hour (count)"
WALKING_RUNNING_DISTANCE = "Distance walked + run (km)"
RESTING_HEART_RATE = "Heart rate --resting (count/min)"
MINDFUL_MINUTES = "Mindful Minutes (min)"

lookback_days = st.sidebar.slider(
    "Période (jours)",
    7, 365, 90,
    key="iphone_metrics_lookback"
)

use_mock = is_admin()

df = load_data("metrics", lookback_days, use_mock)
if df is None or df.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

# st.dataframe(df.tail(50))

metrics_long = long_from_wide(df)

end_date = pd.Timestamp.now()
start_date = end_date - pd.Timedelta(days=lookback_days)

st.header("📱 iPhone — Metrics")
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.subheader("KPI rapides")
    if metrics_long is not None:
        recent = metrics_long[(metrics_long['timestamp'] >= start_date) & (metrics_long['timestamp'] <= end_date)]
        def last_val(metric):
            s = recent[recent['metric'] == metric].sort_values('timestamp', ascending=False)
            return s['value'].iloc[0] if not s.empty else np.nan
        last_steps = last_val(STEP_COUNT)
        last_rhr = last_val(RESTING_HEART_RATE)
        avg_mindful = recent[recent['metric']==MINDFUL_MINUTES]['value'].mean() if not recent[recent['metric']==MINDFUL_MINUTES].empty else np.nan
        st.metric("Pas (dernier)", f"{int(last_steps) if not pd.isna(last_steps) else '—'}")
        st.metric("RHR (dernier)", f"{last_rhr if not pd.isna(last_rhr) else '—'} bpm")
        st.metric("Méd. (moy/jour)", f"{avg_mindful:.1f}" if not pd.isna(avg_mindful) else "—")
    else:
        st.info("Pas de données metrics disponibles.")
with col2:
    st.subheader("Série temporelle & Analyse")
    if metrics_long is not None:
        metric_list = sorted(metrics_long['metric'].unique().tolist())
        default_idx = metric_list.index(STEP_COUNT) if STEP_COUNT in metric_list else 0
        metric_choice = st.selectbox("Choisir une métrique", options=metric_list, index=default_idx)
        metric_df = metrics_long[metrics_long['metric']==metric_choice].copy()
        metric_df = ensure_datetime(metric_df, 'timestamp')
        metric_df = metric_df[(metric_df['timestamp']>=start_date) & (metric_df['timestamp']<=end_date)].sort_values('timestamp')
        if metric_df.empty:
            st.warning("Aucune donnée pour cette métrique sur la période sélectionnée.")
        else:
            metric_df['rolling7'] = rolling_trend(metric_df['value'], window=7)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=metric_df['timestamp'], y=metric_df['value'], mode='lines+markers', name='Valeur'))
            fig.add_trace(go.Scatter(x=metric_df['timestamp'], y=metric_df['rolling7'], mode='lines', name='Moyenne glissante 7j', line=dict(dash='dash')))
            fig.update_layout(title=f"{metric_choice} — Série temporelle", xaxis_title="Date", yaxis_title=metric_choice, height=380)
            st.plotly_chart(fig, width='stretch')
            # histogramme + box
            h = px.histogram(metric_df, x='value', nbins=30, title="Distribution")
            b = px.box(metric_df, y='value', title="Boxplot")
            c1, c2 = st.columns(2)
            c1.plotly_chart(h, width='stretch')
            c2.plotly_chart(b, width='stretch')
            # trend + anomalies
            slope = slope_of_trend(metric_df, 'timestamp', 'value')
            interp = interpret_trend(slope, unit='unit', threshold_small=max(abs(metric_df['value'].mean()*0.0005), 1e-6))
            st.markdown(f"**Interprétation :** {interp}")
            mu = metric_df['value'].mean()
            sigma = metric_df['value'].std()
            anomalous = metric_df[metric_df['value'] > mu + 2*sigma]
            st.write(f"Points anormaux (> mean + 2σ) : {len(anomalous)}")
    else:
        st.info("Aucune métrique iPhone disponible.")
with col3:
    st.subheader("Comparaisons & Corrélations")
    if metrics_long is not None:
        subset = metrics_long[(metrics_long['metric'].isin([STEP_COUNT,WALKING_RUNNING_DISTANCE])) & (metrics_long['timestamp']>=start_date)]
        if not subset.empty:
            wide = subset.pivot_table(index='timestamp', columns='metric', values='value', aggfunc='mean').reset_index()
            if STEP_COUNT in wide.columns and WALKING_RUNNING_DISTANCE in wide.columns:
                fig_scatter = px.scatter(wide, x=STEP_COUNT, y=WALKING_RUNNING_DISTANCE, trendline='ols', title="Pas vs Distance")
                st.plotly_chart(fig_scatter, width='stretch')
    st.write("Idées : corréler RHR ↔ sommeil, montrer l'impact des workouts sur active_energy.")

    
st.markdown("---")
st.caption("Copyright - PHYLCERO©")