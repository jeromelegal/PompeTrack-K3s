import streamlit as st
import pandas as pd
from utils.common import load_data, is_admin, long_from_wide
from utils.common import ensure_datetime, rolling_trend, slope_of_trend, interpret_trend
import plotly.express as px
import plotly.graph_objects as go

lookback_days = st.sidebar.slider(
    "Période (jours)",
    7, 365, 90,
    key="spirometry_metrics_lookback"
)

use_mock = is_admin()

spirometry_df = load_data("spirometer", lookback_days, use_mock)
if spirometry_df is None or spirometry_df.empty:
    st.warning("Aucune donnée disponible.")
    st.stop()

end_date = pd.Timestamp.now()
start_date = end_date - pd.Timedelta(days=lookback_days)

st.header("🌬️ Spirométrie & Oxymétrie")
#st.dataframe(spirometry_df)
if spirometry_df is not None and not spirometry_df.empty:
    spirometry_df = ensure_datetime(spirometry_df, 'timestamp')
    st.dataframe(spirometry_df)
    spi_recent = spirometry_df[(spirometry_df['timestamp']>=start_date) & (spirometry_df['timestamp']<=end_date)].sort_values('timestamp')
    cols = ['FVC','FEV1','FEV6','FVC25','FVC50','FVC75','PEF','FEF25_75','Ratio FEV1 / FVC']
    present = [c for c in cols if c in spi_recent.columns]
    if present:
        for c in present:
            fig = px.line(spi_recent, x='timestamp', y=c, title=f"{c} dans le temps", markers=True)
            st.plotly_chart(fig, width='stretch')
        if 'FEV1' in spi_recent.columns and 'FVC' in spi_recent.columns:
            spi_recent['ratio'] = spi_recent['FEV1'] / spi_recent['FVC']
            st.subheader("Ratio FEV1 / FVC")
            st.write(spi_recent[['timestamp','FEV1','FVC','ratio']].tail(6).style.format({ 'FEV1':'{:.2f}', 'FVC':'{:.2f}', 'ratio':'{:.2f}'}))
            mean_ratio = spi_recent['ratio'].mean()
            st.markdown(f"Ratio moyen FEV1/FVC (période): **{mean_ratio:.2f}**")
            if mean_ratio < 0.7:
                st.warning("Ratio FEV1/FVC moyen < 0.7 → signe possible d'obstruction (à confirmer cliniquement).")
            else:
                st.success("Ratio FEV1/FVC dans une fourchette typique (≥ 0.7).")
    else:
        st.info("Colonnes spirométrie manquantes.")
else:
    st.info("Aucune donnée spirométrie disponible.")
    
    
st.markdown("---")
st.caption("Copyright - PHYLCERO©")