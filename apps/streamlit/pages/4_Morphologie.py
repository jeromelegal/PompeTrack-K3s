import streamlit as st
import pandas as pd
from utils.common import load_data, is_admin, long_from_wide
from utils.common import ensure_datetime, rolling_trend, slope_of_trend, interpret_trend
import plotly.express as px
import plotly.graph_objects as go

lookback_days = st.sidebar.slider(
    "Période (jours)",
    7, 365, 90,
    key="manual_metrics_lookback"
)

use_mock = is_admin()

manual_weekly_df = load_data("manual_weekly", lookback_days, use_mock)
if manual_weekly_df is None or manual_weekly_df.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()
    
manual_monthly_df = load_data("manual_monthly", lookback_days, use_mock)
if manual_monthly_df is None or manual_monthly_df.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

end_date = pd.Timestamp.now()
start_date = end_date - pd.Timedelta(days=lookback_days)

# st.dataframe(df.tail(50))

# st.header("✊ Mesures manuelles")
# st.subheader("Hebdomadaire")
# if manual_weekly_df is not None and not manual_weekly_df.empty:
#     manual_weekly_df = ensure_datetime(manual_weekly_df, 'timestamp')
#     recent_w = manual_weekly_df[(manual_weekly_df['timestamp']>=start_date) & (manual_weekly_df['timestamp']<=end_date)].sort_values('timestamp')
#     if not recent_w.empty:
#         fig_w = px.line(recent_w, x='timestamp', y='poids_kg', title='Poids (kg)', markers=True)
#         st.plotly_chart(fig_w, width='stretch')
#         bp_cols = [c for c in ['tension_sys','tension_dia'] if c in recent_w.columns]
#         if bp_cols:
#             fig_bp = go.Figure()
#             for c in bp_cols:
#                 fig_bp.add_trace(go.Scatter(x=recent_w['timestamp'], y=recent_w[c], mode='lines+markers', name=c))
#             fig_bp.update_layout(title='Tension artérielle', xaxis_title='Date', yaxis_title='mmHg')
#             st.plotly_chart(fig_bp, width='stretch')
#         st.table(recent_w.tail(8).set_index('timestamp'))
#         slope_poids = slope_of_trend(recent_w, 'timestamp', 'poids_kg')
#         st.markdown(f"**Tendance poids :** {interpret_trend(slope_poids, unit='kg/jour', threshold_small=0.01)}")
#     else:
#         st.info("Aucune donnée hebdomadaire sur la période.")
# else:
#     st.info("Aucune donnée hebdomadaire fournie.")


# calf_left=calf_left,
# calf_right=calf_right,
# thigh_left=thigh_left,
# thigh_right=thigh_right,
# waist=waist,
# hips=hips,
# neck=neck,
# comments=comments,

st.markdown("---")

st.subheader("Mensuel — Morphologie & Force")
if manual_monthly_df is not None and not manual_monthly_df.empty:
    manual_monthly_df = ensure_datetime(manual_monthly_df, 'timestamp')
    recent_m = manual_monthly_df[(manual_monthly_df['timestamp']>=start_date) & (manual_monthly_df['timestamp']<=end_date)].sort_values('timestamp')
    if not recent_m.empty:
        circ_cols = [c for c in ['mollet_cm','cuisse_cm','taille_cm','hanches_cm','cou_cm'] if c in recent_m.columns]
        if circ_cols:
            latest = recent_m[circ_cols].iloc[-1]
            radar_theta = circ_cols
            radar_r = latest.values.tolist()
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(r=radar_r + [radar_r[0]], theta=radar_theta + [radar_theta[0]], fill='toself', name='Circonférences'))
            fig_radar.update_layout(title='Circonférences (dernière mesure)', polar=dict(radialaxis=dict(visible=True)))
            st.plotly_chart(fig_radar, width='stretch')
        force_cols = [c for c in ['bras_kgf','quadriceps_kgf'] if c in recent_m.columns]
        if force_cols:
            fig_force = px.line(recent_m, x='timestamp', y=force_cols, title='Force musculaire (kgf)', markers=True)
            st.plotly_chart(fig_force, width='stretch')
        st.table(recent_m.tail(6).set_index('timestamp'))
    else:
        st.info("Aucune donnée mensuelle sur la période.")
else:
    st.info("Aucune donnée mensuelle fournie.")
    
    
    
st.markdown("---")
st.caption("Copyright - PHYLCERO©")