import streamlit as st
import pandas as pd
from utils.common import load_data, is_admin, long_from_wide, ensure_datetime
import plotly.express as px
import plotly.graph_objects as go

lookback_days = st.sidebar.slider(
    "Période (jours)",
    7, 365, 90,
    key="workouts_metrics_lookback"
)

use_mock = is_admin()

# Load workouts data
workouts_df = load_data("workouts", lookback_days, use_mock)
if workouts_df is None :
    st.warning("Aucune donnée disponible.")
    st.stop()

# Load stateofminds data
som_df = load_data("stateofminds", lookback_days, use_mock)
if som_df is None :
    st.warning("Aucune donnée disponible.")
    st.stop()

if som_df is not None or som_df.empty():
    #st.dataframe(som_df)
    metrics_long = long_from_wide(som_df)

end_date = pd.Timestamp.now()
start_date = end_date - pd.Timedelta(days=lookback_days)

st.header("🤸 Workouts & 😕 État d'esprit")
c1, c2 = st.columns([2,1])
with c1:
    st.subheader("Répartition Workouts")
    if workouts_df is not None :
        workouts_df = ensure_datetime(workouts_df, 'timestamp')
        recent_ws = workouts_df[(workouts_df['timestamp']>=start_date) & (workouts_df['timestamp']<=end_date)]
        ct = recent_ws['parameter'].value_counts().reset_index()
        ct.columns = ['parameter','count']
        fig_bar = px.bar(ct, x='parameter', y='count', title="Nombre de séances par type", text='count')
        st.plotly_chart(fig_bar, width='stretch')
        dur = recent_ws.groupby('parameter')['duration_min'].agg(['count','mean']).reset_index().round(1)
        st.table(dur)
        # calendrier (barres par date)
        cal = recent_ws.copy()
        cal['date'] = cal['timestamp'].dt.date
        heat = cal.groupby('date').size().reset_index(name='count')
        heat['date'] = pd.to_datetime(heat['date'])
        fig_cal = px.bar(heat, x='date', y='count', title="Séances / jour")
        st.plotly_chart(fig_cal, width='stretch')
    else:
        st.info("Aucun workout détecté.")
with c2:
    st.subheader("État d'esprit (Mood)")
    if som_df is not None :
        som_df = ensure_datetime(som_df, 'timestamp')
        som_recent = som_df[(som_df['timestamp']>=start_date)].sort_values('timestamp')
        if not som_recent.empty:
            mood_col = som_recent.columns[1]
            fig_mood = px.line(som_recent, x='timestamp', y=mood_col, title="Score humeur dans le temps", markers=True)
            st.plotly_chart(fig_mood, width='stretch')
            st.markdown(f"**Moyenne humeur (période):** {som_recent[mood_col].mean():.2f} / 10")
            # corrélation humeur <-> pas
            if metrics_long is not None:
                steps = metrics_long[(metrics_long['metric']=='step_count') & (metrics_long['timestamp']>=start_date)].sort_values('timestamp')
                merged = pd.merge_asof(som_recent.sort_values('timestamp'), steps.sort_values('timestamp'), on='timestamp', direction='nearest', tolerance=pd.Timedelta('1D'))
                if 'value' in merged.columns and not merged['value'].isnull().all():
                    corr = merged.iloc[:,1].corr(merged['value'])
                    st.markdown(f"Corrélation approximative humeur ↔ pas : **{corr:.2f}**")
    else:
        st.info("Pas de données d'état d'esprit.")
        
            
st.markdown("---")
st.caption("Copyright - PHYLCERO©")