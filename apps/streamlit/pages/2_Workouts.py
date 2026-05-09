import streamlit as st
import pandas as pd
import plotly.express as px

from utils.common import load_data, is_admin, ensure_datetime


st.set_page_config(page_title="Workouts", page_icon="🤸", layout="wide")


def prepare_workouts_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df = ensure_datetime(df, "timestamp")

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if "duration_min" in df.columns:
        df["duration_min"] = pd.to_numeric(df["duration_min"], errors="coerce")
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

    if "parameter" in df.columns:
        df["parameter"] = df["parameter"].fillna("Inconnu")
    else:
        df["parameter"] = "Inconnu"

    if "category" not in df.columns:
        df["category"] = None
    if "performer" not in df.columns:
        df["performer"] = None
    if "device" not in df.columns:
        df["device"] = None
    if "unit" not in df.columns:
        df["unit"] = None

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

    if "energy_kcal" in df.columns:
        df["energy_kcal"] = pd.to_numeric(df["energy_kcal"], errors="coerce")
    else:
        df["energy_kcal"] = pd.NA

    if "energy_kj" in df.columns:
        df["energy_kj"] = pd.to_numeric(df["energy_kj"], errors="coerce")
    else:
        df["energy_kj"] = pd.NA

    mask_missing_kcal = df["energy_kcal"].isna() & df["energy_kj"].notna()
    df.loc[mask_missing_kcal, "energy_kcal"] = df.loc[mask_missing_kcal, "energy_kj"] / 4.184

    mask_missing_kj = df["energy_kj"].isna() & df["energy_kcal"].notna()
    df.loc[mask_missing_kj, "energy_kj"] = df.loc[mask_missing_kj, "energy_kcal"] * 4.184

    return df


def build_kpis(df: pd.DataFrame) -> dict:
    total_sessions = len(df)
    total_minutes = float(df["duration_min"].sum()) if "duration_min" in df.columns else 0.0
    avg_duration = float(df["duration_min"].mean()) if total_sessions else 0.0
    max_duration = float(df["duration_min"].max()) if total_sessions else 0.0
    active_days = int(df["date"].nunique()) if "date" in df.columns else 0
    total_kcal = float(df["energy_kcal"].sum()) if df["energy_kcal"].notna().any() else None

    return {
        "total_sessions": total_sessions,
        "total_minutes": total_minutes,
        "avg_duration": avg_duration,
        "max_duration": max_duration,
        "active_days": active_days,
        "total_kcal": total_kcal,
    }


st.title("🤸 Workouts")

lookback_days = st.sidebar.slider(
    "Période (jours)",
    min_value=7,
    max_value=1095,
    value=180,
    key="workouts_page_lookback",
)

use_mock = is_admin()
workouts_df = load_data("workouts", lookback_days, use_mock)

if workouts_df is None or workouts_df.empty:
    st.warning("Aucune donnée de workout disponible.")
    st.stop()

workouts_df = prepare_workouts_df(workouts_df)

if workouts_df.empty:
    st.warning("Aucune donnée exploitable après préparation.")
    st.stop()

type_options = sorted(workouts_df["parameter"].dropna().unique().tolist())
selected_types = st.sidebar.multiselect(
    "Type de workout",
    options=type_options,
    default=type_options,
)

max_duration_available = int(
    max(1, workouts_df["duration_min"].fillna(0).max())
) if "duration_min" in workouts_df.columns else 1

min_duration = st.sidebar.slider(
    "Durée minimale (min)",
    min_value=0,
    max_value=max_duration_available,
    value=0,
)

filtered = workouts_df.copy()

if selected_types:
    filtered = filtered[filtered["parameter"].isin(selected_types)]

if "duration_min" in filtered.columns:
    filtered = filtered[filtered["duration_min"].fillna(0) >= min_duration]

filtered = filtered.sort_values("timestamp", ascending=False)

if filtered.empty:
    st.info("Aucune séance ne correspond aux filtres.")
    st.stop()

# KPIs
kpis = build_kpis(filtered)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Séances", f"{kpis['total_sessions']}")
c2.metric("Temps total", f"{kpis['total_minutes']:.0f} min")
c3.metric("Durée moyenne", f"{kpis['avg_duration']:.1f} min")
c4.metric("Durée max", f"{kpis['max_duration']:.1f} min")

if kpis["total_kcal"] is not None:
    c5.metric("Calories totales", f"{kpis['total_kcal']:.0f} kcal")
else:
    c5.metric("Jours actifs", f"{kpis['active_days']}")

st.markdown("---")

by_type = (
    filtered.groupby("parameter", dropna=False)
    .agg(
        sessions=("parameter", "size"),
        minutes_total=("duration_min", "sum"),
        minutes_moy=("duration_min", "mean"),
    )
    .reset_index()
    .sort_values("sessions", ascending=False)
)

if filtered["energy_kcal"].notna().any():
    kcal_by_type = (
        filtered.groupby("parameter", dropna=False)["energy_kcal"]
        .sum()
        .reset_index(name="kcal_total")
    )
    by_type = by_type.merge(kcal_by_type, on="parameter", how="left")

weekly_sessions = (
    filtered.groupby(["week", "parameter"], dropna=False)
    .size()
    .reset_index(name="sessions")
    .sort_values("week")
)

weekly_minutes = (
    filtered.groupby(["week", "parameter"], dropna=False)["duration_min"]
    .sum()
    .reset_index(name="minutes")
    .sort_values("week")
)

weekday_order = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
by_weekday = (
    filtered.groupby(["weekday_num", "weekday"], dropna=False)
    .agg(
        sessions=("parameter", "size"),
        minutes=("duration_min", "sum"),
    )
    .reset_index()
    .sort_values("weekday_num")
)
by_weekday["weekday"] = pd.Categorical(by_weekday["weekday"], categories=weekday_order, ordered=True)
by_weekday = by_weekday.sort_values("weekday")

monthly_minutes = (
    filtered.groupby(["month", "parameter"], dropna=False)["duration_min"]
    .sum()
    .reset_index(name="minutes")
    .sort_values("month")
)

col1, col2 = st.columns([1.8, 1.2])

with col1:
    st.subheader("Séances par semaine")
    fig_weekly = px.bar(
        weekly_sessions,
        x="week",
        y="sessions",
        color="parameter",
        barmode="stack",
        title="Volume hebdomadaire par type",
        labels={"week": "Semaine", "sessions": "Séances", "parameter": "Type"},
    )
    fig_weekly.update_layout(legend_title_text="Type")
    st.plotly_chart(fig_weekly, width="stretch")

with col2:
    st.subheader("Répartition par type")
    fig_pie = px.pie(
        by_type,
        names="parameter",
        values="sessions",
        hole=0.45,
        title="Part des séances par type",
    )
    st.plotly_chart(fig_pie, width="stretch")

col3, col4 = st.columns(2)

with col3:
    st.subheader("Distribution des durées")
    fig_box = px.box(
        filtered,
        x="parameter",
        y="duration_min",
        points="all",
        title="Durée des séances par type",
        labels={"parameter": "Type", "duration_min": "Durée (min)"},
    )
    st.plotly_chart(fig_box, width="stretch")

with col4:
    if filtered["energy_kcal"].notna().any():
        st.subheader("Durée vs calories")
        energy_df = filtered.dropna(subset=["duration_min", "energy_kcal"]).copy()
        fig_scatter = px.scatter(
            energy_df,
            x="duration_min",
            y="energy_kcal",
            color="parameter",
            hover_data=["timestamp", "device"],
            title="Relation durée / calories",
            labels={"duration_min": "Durée (min)", "energy_kcal": "Calories (kcal)"},
        )
        st.plotly_chart(fig_scatter, width="stretch")
    else:
        st.subheader("Répartition par jour de semaine")
        fig_weekday = px.bar(
            by_weekday,
            x="weekday",
            y="sessions",
            title="Séances par jour de semaine",
            labels={"weekday": "Jour", "sessions": "Séances"},
        )
        st.plotly_chart(fig_weekday, width="stretch")

col5, col6 = st.columns([1.5, 1.5])

with col5:
    st.subheader("Temps d'entraînement mensuel")
    fig_monthly = px.area(
        monthly_minutes,
        x="month",
        y="minutes",
        color="parameter",
        title="Minutes par mois",
        labels={"month": "Mois", "minutes": "Minutes", "parameter": "Type"},
    )
    st.plotly_chart(fig_monthly, width="stretch")

with col6:
    st.subheader("Résumé par type")
    summary_cols = ["parameter", "sessions", "minutes_total", "minutes_moy"]
    if "kcal_total" in by_type.columns:
        summary_cols.append("kcal_total")

    summary_df = by_type[summary_cols].copy()
    summary_df = summary_df.rename(
        columns={
            "parameter": "Type",
            "sessions": "Séances",
            "minutes_total": "Temps total (min)",
            "minutes_moy": "Durée moy. (min)",
            "kcal_total": "Calories totales",
        }
    )

    st.dataframe(
        summary_df.style.format({
            "Temps total (min)": "{:.1f}",
            "Durée moy. (min)": "{:.1f}",
            "Calories totales": "{:.0f}",
        }),
        width="stretch",
        hide_index=True,
    )

st.markdown("---")

st.subheader("Dernières séances")
table_cols = ["timestamp", "parameter", "category", "duration_min", "device", "performer"]
if filtered["energy_kcal"].notna().any():
    table_cols.append("energy_kcal")

recent = filtered[table_cols].copy().sort_values("timestamp", ascending=False).head(50)
recent = recent.rename(
    columns={
        "timestamp": "Date",
        "parameter": "Workout",
        "category": "Catégorie",
        "duration_min": "Durée (min)",
        "device": "Device",
        "performer": "Performer",
        "energy_kcal": "Calories (kcal)",
    }
)

st.dataframe(
    recent.style.format({
        "Durée (min)": "{:.1f}",
        "Calories (kcal)": "{:.0f}",
    }),
    width="stretch",
    hide_index=True,
)

st.caption("Copyright - PHYLCERO©")
