import streamlit as st
import pandas as pd
import plotly.express as px

from utils.common import load_data, is_admin


st.set_page_config(page_title="State of Minds", page_icon="🧠", layout="wide")


def explode_token_counts(df: pd.DataFrame, list_col: str, label_name: str) -> pd.DataFrame:
    if df.empty or list_col not in df.columns:
        return pd.DataFrame(columns=[label_name, "count"])

    tmp = df[[list_col]].explode(list_col).dropna()
    if tmp.empty:
        return pd.DataFrame(columns=[label_name, "count"])

    out = (
        tmp.groupby(list_col)
        .size()
        .reset_index(name="count")
        .rename(columns={list_col: label_name})
        .sort_values("count", ascending=False)
    )
    return out


def prepare_som_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")

    df = df.dropna(subset=["timestamp"]).copy()

    df["date"] = df["timestamp"].dt.normalize()
    df["week"] = df["timestamp"].dt.to_period("W").dt.start_time
    df["month"] = df["timestamp"].dt.to_period("M").dt.to_timestamp()
    df["year"] = df["timestamp"].dt.year

    weekday_map = {
        0: "Lun",
        1: "Mar",
        2: "Mer",
        3: "Jeu",
        4: "Ven",
        5: "Sam",
        6: "Dim",
    }
    df["weekday_num"] = df["timestamp"].dt.dayofweek
    df["weekday"] = df["weekday_num"].map(weekday_map)

    hour = df["timestamp"].dt.hour
    bins = [-1, 5, 11, 17, 23]
    labels = ["Nuit", "Matin", "Après-midi", "Soir"]
    df["moment_of_day"] = pd.cut(hour, bins=bins, labels=labels)

    return df


st.title("🧠 State of Minds")

lookback_days = st.sidebar.slider(
    "Période (jours)",
    min_value=7,
    max_value=1095,
    value=180,
    key="som_page_lookback",
)

use_mock = is_admin()
som_df = load_data("stateofminds", lookback_days, use_mock)

if som_df is None or som_df.empty:
    st.warning("Aucune donnée d'état d'esprit disponible.")
    st.stop()

som_df = prepare_som_df(som_df)

if som_df.empty:
    st.warning("Aucune donnée exploitable après préparation.")
    st.stop()

type_options = sorted(som_df["parameter"].dropna().unique().tolist())
selected_types = st.sidebar.multiselect(
    "Type",
    options=type_options,
    default=type_options,
)

interp_options = sorted(som_df["interpretation"].dropna().unique().tolist())
selected_interpretations = st.sidebar.multiselect(
    "Interpretation",
    options=interp_options,
    default=interp_options,
)

filtered = som_df.copy()

if selected_types:
    filtered = filtered[filtered["parameter"].isin(selected_types)]

if selected_interpretations:
    filtered = filtered[filtered["interpretation"].isin(selected_interpretations)]

if filtered.empty:
    st.info("Aucune entrée ne correspond aux filtres.")
    st.stop()

entry_count = len(filtered)
avg_score = filtered["score"].mean() if filtered["score"].notna().any() else None
last_entry = filtered.sort_values("timestamp").iloc[-1]
last_interp = last_entry["interpretation"]
daily_count = int((filtered["parameter"] == "daily_mood").sum())
momentary_count = int((filtered["parameter"] == "momentary_emotion").sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Entrées", f"{entry_count}")
c2.metric("Score moyen", f"{avg_score:.2f}" if avg_score is not None else "N/A")
c3.metric("daily_mood", f"{daily_count}")
c4.metric("momentary_emotion", f"{momentary_count}")

st.caption(f"Dernière interprétation : {last_interp if pd.notna(last_interp) else 'N/A'}")

st.markdown("---")

monthly_score = (
    filtered.groupby(["month", "parameter"], dropna=False)["score"]
    .mean()
    .reset_index(name="avg_score")
    .sort_values("month")
)

interp_count = (
    filtered.groupby(["parameter", "interpretation"], dropna=False)
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)

weekday_score = (
    filtered.groupby(["weekday_num", "weekday"], dropna=False)["score"]
    .mean()
    .reset_index(name="avg_score")
    .sort_values("weekday_num")
)

assoc_counts = explode_token_counts(filtered, "association_list", "association").head(15)
label_counts = explode_token_counts(filtered, "label_list", "label").head(15)

col1, col2 = st.columns([1.7, 1.3])

with col1:
    st.subheader("Score dans le temps")
    score_df = filtered.dropna(subset=["score"]).sort_values("timestamp")
    fig_score = px.line(
        score_df,
        x="timestamp",
        y="score",
        color="parameter",
        markers=True,
        title="Évolution du score",
        labels={"timestamp": "Date", "score": "Score", "parameter": "Type"},
        hover_data=["interpretation", "labels", "associations"],
    )
    st.plotly_chart(fig_score, use_container_width=True)

with col2:
    st.subheader("Répartition des interprétations")
    fig_interp = px.bar(
        interp_count,
        x="interpretation",
        y="count",
        color="parameter",
        barmode="group",
        title="Interprétations par type",
        labels={"interpretation": "Interpretation", "count": "Nombre", "parameter": "Type"},
    )
    fig_interp.update_xaxes(tickangle=35)
    st.plotly_chart(fig_interp, use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    st.subheader("Score moyen mensuel")
    fig_month = px.line(
        monthly_score,
        x="month",
        y="avg_score",
        color="parameter",
        markers=True,
        title="Tendance mensuelle",
        labels={"month": "Mois", "avg_score": "Score moyen", "parameter": "Type"},
    )
    st.plotly_chart(fig_month, use_container_width=True)

with col4:
    st.subheader("Score moyen par jour")
    fig_weekday = px.bar(
        weekday_score,
        x="weekday",
        y="avg_score",
        title="Score moyen par jour de semaine",
        labels={"weekday": "Jour", "avg_score": "Score moyen"},
    )
    st.plotly_chart(fig_weekday, use_container_width=True)

col5, col6 = st.columns(2)

with col5:
    st.subheader("Associations les plus fréquentes")
    if assoc_counts.empty:
        st.info("Aucune association disponible.")
    else:
        fig_assoc = px.bar(
            assoc_counts,
            x="association",
            y="count",
            title="Top associations",
            labels={"association": "Association", "count": "Nombre"},
        )
        fig_assoc.update_xaxes(tickangle=35)
        st.plotly_chart(fig_assoc, use_container_width=True)

with col6:
    st.subheader("Labels les plus fréquents")
    if label_counts.empty:
        st.info("Aucun label disponible.")
    else:
        fig_labels = px.bar(
            label_counts,
            x="label",
            y="count",
            title="Top labels",
            labels={"label": "Label", "count": "Nombre"},
        )
        fig_labels.update_xaxes(tickangle=35)
        st.plotly_chart(fig_labels, use_container_width=True)

st.markdown("---")

st.subheader("Détail des entrées")
table_cols = [
    "timestamp",
    "parameter",
    "score",
    "unit",
    "interpretation",
    "associations",
    "labels",
    "device",
]

display_df = (
    filtered[table_cols]
    .sort_values("timestamp", ascending=False)
    .rename(columns={
        "timestamp": "Date",
        "parameter": "Type",
        "score": "Score",
        "unit": "Unité",
        "interpretation": "Interpretation",
        "associations": "Associations",
        "labels": "Labels",
        "device": "Device",
    })
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)

st.caption("Copyright - PHYLCERO©")