import re
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from libs.db_service import get_connection
from utils.stream_requests import get_medication


st.set_page_config(page_title="Medication map", layout="wide")
st.title("Medication map")
st.caption("Créer, charger, éditer et enregistrer les correspondances Medication → medication_map")


# =========================
# Constantes
# =========================
SOURCE_SYSTEM_DEFAULT = "iphone"

FORM_FIELDS = [
    "source_system",
    "canonical_key",
    "raw_name",
    "normalized_name",
    "medplum_medication_id",
    "code_system",
    "code_value",
    "display",
    "strength_value",
    "strength_unit",
    "dose_form",
]

DEFAULT_FORM = {
    "source_system": SOURCE_SYSTEM_DEFAULT,
    "canonical_key": "",
    "raw_name": "",
    "normalized_name": "",
    "medplum_medication_id": "",
    "code_system": "",
    "code_value": "",
    "display": "",
    "strength_value": "",
    "strength_unit": "",
    "dose_form": "",
}


# =========================
# Helpers généraux
# =========================
def normalize_name(value: str) -> str:
    """Normalise un nom pour recherche/correspondance."""
    value = (value or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def parse_rxnorm_display(display: str) -> Dict[str, str]:
    """
    Essaie d'extraire:
    - nom
    - dosage
    - unité
    - forme
    depuis un display RxNorm du type:
    'gabapentin 300 MG Oral Capsule'
    """
    result = {
        "parsed_name": "",
        "strength_value": "",
        "strength_unit": "",
        "dose_form": "",
    }

    text = (display or "").strip()
    if not text:
        return result

    # Nom + force + unité + reste
    match = re.match(
        r"^(?P<name>.*?)\s+(?P<strength>\d+(?:[.,]\d+)?)\s+(?P<unit>[A-Za-z/%]+)\s+(?P<form>.+)$",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        result["parsed_name"] = match.group("name").strip()
        result["strength_value"] = match.group("strength").strip().replace(",", ".")
        result["strength_unit"] = match.group("unit").strip()
        result["dose_form"] = match.group("form").strip()
    else:
        result["parsed_name"] = text

    return result


def build_canonical_key(
    source_system: str,
    normalized_name: str,
    strength_value: str,
    strength_unit: str,
    dose_form: str,
) -> str:
    """Construit une clé canonique stable."""
    parts = [
        (source_system or "").strip(),
        normalize_name(normalized_name),
        normalize_name(strength_value),
        normalize_name(strength_unit),
        normalize_name(dose_form),
    ]
    parts = [p for p in parts if p]
    return "|".join(parts)


def ensure_form_state() -> None:
    for field, default_value in DEFAULT_FORM.items():
        st.session_state.setdefault(f"medmap_{field}", default_value)


def get_form_data() -> Dict[str, str]:
    return {
        field: st.session_state.get(f"medmap_{field}", "")
        for field in FORM_FIELDS
    }


def set_form_data(data: Dict[str, Any]) -> None:
    for field in FORM_FIELDS:
        value = data.get(field, DEFAULT_FORM[field])
        st.session_state[f"medmap_{field}"] = "" if value is None else str(value)


def reset_form() -> None:
    set_form_data(DEFAULT_FORM)


# =========================
# DB helpers
# =========================
def fetch_dataframe(query: str, params: Dict[str, Any] | None = None) -> pd.DataFrame:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or {})
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        return pd.DataFrame(rows, columns=columns)
    finally:
        conn.close()


@st.cache_data(ttl=30)
def load_medication_map() -> pd.DataFrame:
    query = """
        SELECT
            source_system,
            canonical_key,
            raw_name,
            normalized_name,
            medplum_medication_id,
            code_system,
            code_value,
            display,
            strength_value,
            strength_unit,
            dose_form,
            last_seen_at,
            created_at,
            updated_at
        FROM medication_map
        ORDER BY updated_at DESC, source_system, canonical_key
    """
    return fetch_dataframe(query)


def upsert_mapping(record: Dict[str, str]) -> None:
    query = """
        INSERT INTO medication_map
        (
            source_system,
            canonical_key,
            raw_name,
            normalized_name,
            medplum_medication_id,
            code_system,
            code_value,
            display,
            strength_value,
            strength_unit,
            dose_form,
            last_seen_at,
            updated_at
        )
        VALUES
        (
            %(source_system)s,
            %(canonical_key)s,
            %(raw_name)s,
            %(normalized_name)s,
            %(medplum_medication_id)s,
            %(code_system)s,
            %(code_value)s,
            %(display)s,
            %(strength_value)s,
            %(strength_unit)s,
            %(dose_form)s,
            now(),
            now()
        )
        ON CONFLICT (source_system, canonical_key)
        DO UPDATE SET
            raw_name              = EXCLUDED.raw_name,
            normalized_name       = EXCLUDED.normalized_name,
            medplum_medication_id = EXCLUDED.medplum_medication_id,
            code_system           = EXCLUDED.code_system,
            code_value            = EXCLUDED.code_value,
            display               = EXCLUDED.display,
            strength_value        = EXCLUDED.strength_value,
            strength_unit         = EXCLUDED.strength_unit,
            dose_form             = EXCLUDED.dose_form,
            last_seen_at          = now(),
            updated_at            = now()
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, record)
        conn.commit()
    finally:
        conn.close()


# =========================
# Medplum helpers
# =========================
@st.cache_data(ttl=60)
def load_medplum_medications() -> pd.DataFrame:
    payload = get_medication() or {}
    resources = payload.get("data", [])

    rows: List[Dict[str, Any]] = []

    for med in resources:
        code_obj = med.get("code") or {}
        coding = code_obj.get("coding") or []
        first_coding = coding[0] if coding else {}

        display = (
            first_coding.get("display")
            or code_obj.get("text")
            or ""
        )
        parsed = parse_rxnorm_display(display)

        rows.append(
            {
                "id": med.get("id", ""),
                "display": display,
                "text": code_obj.get("text", ""),
                "code_system": first_coding.get("system", ""),
                "code_value": first_coding.get("code", ""),
                "parsed_name": parsed["parsed_name"],
                "strength_value": parsed["strength_value"],
                "strength_unit": parsed["strength_unit"],
                "dose_form": parsed["dose_form"],
                "last_updated": ((med.get("meta") or {}).get("lastUpdated", "")),
                "resource": med,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "id",
                "display",
                "text",
                "code_system",
                "code_value",
                "parsed_name",
                "strength_value",
                "strength_unit",
                "dose_form",
                "last_updated",
                "resource",
            ]
        )

    return df.sort_values(by=["display", "id"]).reset_index(drop=True)


def prefill_from_medication_row(row: pd.Series) -> None:
    current = get_form_data()

    raw_name = current["raw_name"] or row.get("parsed_name", "") or row.get("display", "")
    normalized_name = current["normalized_name"] or normalize_name(raw_name)

    merged = {
        "source_system": current["source_system"] or SOURCE_SYSTEM_DEFAULT,
        "canonical_key": current["canonical_key"],
        "raw_name": raw_name,
        "normalized_name": normalized_name,
        "medplum_medication_id": row.get("id", ""),
        "code_system": row.get("code_system", ""),
        "code_value": row.get("code_value", ""),
        "display": row.get("display", ""),
        "strength_value": row.get("strength_value", ""),
        "strength_unit": row.get("strength_unit", ""),
        "dose_form": row.get("dose_form", ""),
    }

    # Si la canonical_key était vide, on la propose automatiquement
    if not merged["canonical_key"]:
        merged["canonical_key"] = build_canonical_key(
            source_system=merged["source_system"],
            normalized_name=merged["normalized_name"],
            strength_value=merged["strength_value"],
            strength_unit=merged["strength_unit"],
            dose_form=merged["dose_form"],
        )

    set_form_data(merged)


# =========================
# Initialisation
# =========================
ensure_form_state()

# Boutons utilitaires
col_top_1, col_top_2 = st.columns([1, 1])
with col_top_1:
    if st.button("Rafraîchir Medplum + Postgres"):
        load_medplum_medications.clear()
        load_medication_map.clear()
        st.rerun()

with col_top_2:
    if st.button("Nouveau mapping / vider le formulaire"):
        reset_form()
        st.rerun()


# Chargement données
try:
    meds_df = load_medplum_medications()
except Exception as e:
    st.error(f"Erreur chargement Medplum : {e}")
    meds_df = pd.DataFrame()

try:
    mappings_df = load_medication_map()
except Exception as e:
    st.error(f"Erreur chargement Postgres : {e}")
    mappings_df = pd.DataFrame()


tab_edit, tab_view = st.tabs(["Créer / éditer", "Voir les mappings"])


# =========================
# TAB 1 - Création / édition
# =========================
with tab_edit:
    st.subheader("1) Sélection d'un Medication Medplum")

    med_filter = st.text_input(
        "Filtrer les Medication Medplum",
        placeholder="Ex: gabapentin, mirtazapine, 300, capsule...",
    )

    med_work_df = meds_df.copy()

    if not med_work_df.empty and med_filter.strip():
        pattern = med_filter.strip().lower()
        med_work_df = med_work_df[
            med_work_df["display"].fillna("").str.lower().str.contains(pattern, na=False)
            | med_work_df["text"].fillna("").str.lower().str.contains(pattern, na=False)
            | med_work_df["code_value"].fillna("").str.lower().str.contains(pattern, na=False)
        ]

    med_options = med_work_df["id"].tolist() if not med_work_df.empty else []

    selected_med_id = st.selectbox(
        "Medication Medplum",
        options=[""] + med_options,
        format_func=lambda x: (
            "-- sélectionner --"
            if x == ""
            else (
                lambda row: f"{row['display']}  |  id={row['id']}  |  code={row['code_value']}"
            )(med_work_df.loc[med_work_df["id"] == x].iloc[0])
        ),
    )

    col_med_1, col_med_2 = st.columns([1, 3])

    with col_med_1:
        if st.button("Préremplir depuis ce Medication"):
            if not selected_med_id:
                st.warning("Sélectionne un Medication Medplum.")
            else:
                selected_row = med_work_df.loc[med_work_df["id"] == selected_med_id].iloc[0]
                prefill_from_medication_row(selected_row)
                st.success("Formulaire prérempli depuis Medplum.")
                st.rerun()

    with col_med_2:
        if selected_med_id:
            selected_row = med_work_df.loc[med_work_df["id"] == selected_med_id].iloc[0]
            with st.expander("Voir le Medication Medplum sélectionné", expanded=False):
                st.json(selected_row["resource"])

    st.markdown("---")
    st.subheader("2) Charger un mapping existant")

    if mappings_df.empty:
        st.info("Aucun mapping présent dans la table medication_map.")
    else:
        mapping_options = mappings_df.index.tolist()

        selected_mapping_idx = st.selectbox(
            "Mapping existant",
            options=[""] + mapping_options,
            format_func=lambda x: (
                "-- sélectionner --"
                if x == ""
                else (
                    f"{mappings_df.loc[x, 'source_system']} | "
                    f"{mappings_df.loc[x, 'raw_name'] or mappings_df.loc[x, 'normalized_name']} "
                    f"→ {mappings_df.loc[x, 'display']} "
                    f"({mappings_df.loc[x, 'canonical_key']})"
                )
            ),
        )

        if st.button("Charger ce mapping dans le formulaire"):
            if selected_mapping_idx == "":
                st.warning("Sélectionne un mapping existant.")
            else:
                row = mappings_df.loc[selected_mapping_idx].to_dict()
                set_form_data(row)
                st.success("Mapping chargé dans le formulaire.")
                st.rerun()

    st.markdown("---")
    st.subheader("3) Formulaire")

    col_left, col_right = st.columns(2)

    with col_left:
        st.text_input("source_system", key="medmap_source_system")
        st.text_input("raw_name (nom venant de l'iPhone)", key="medmap_raw_name")

        col_norm_1, col_norm_2 = st.columns([2, 1])
        with col_norm_1:
            st.text_input("normalized_name", key="medmap_normalized_name")
        with col_norm_2:
            if st.button("Normaliser le nom"):
                st.session_state["medmap_normalized_name"] = normalize_name(
                    st.session_state.get("medmap_raw_name", "")
                )
                st.rerun()

        st.text_input("strength_value", key="medmap_strength_value")
        st.text_input("strength_unit", key="medmap_strength_unit")
        st.text_input("dose_form", key="medmap_dose_form")

        auto_key = build_canonical_key(
            source_system=st.session_state.get("medmap_source_system", ""),
            normalized_name=st.session_state.get("medmap_normalized_name", ""),
            strength_value=st.session_state.get("medmap_strength_value", ""),
            strength_unit=st.session_state.get("medmap_strength_unit", ""),
            dose_form=st.session_state.get("medmap_dose_form", ""),
        )

        st.caption(f"Clé canonique suggérée : `{auto_key}`")

        col_key_1, col_key_2 = st.columns([2, 1])
        with col_key_1:
            st.text_input("canonical_key", key="medmap_canonical_key")
        with col_key_2:
            if st.button("Utiliser la clé suggérée"):
                st.session_state["medmap_canonical_key"] = auto_key
                st.rerun()

    with col_right:
        st.text_input("medplum_medication_id", key="medmap_medplum_medication_id")
        st.text_input("code_system", key="medmap_code_system")
        st.text_input("code_value", key="medmap_code_value")
        st.text_input("display", key="medmap_display")

    st.markdown("---")
    st.subheader("4) Enregistrement")

    current_form = get_form_data()

    preview_record = current_form.copy()
    if not preview_record["normalized_name"]:
        preview_record["normalized_name"] = normalize_name(
            preview_record["raw_name"] or preview_record["display"]
        )
    if not preview_record["canonical_key"]:
        preview_record["canonical_key"] = build_canonical_key(
            source_system=preview_record["source_system"],
            normalized_name=preview_record["normalized_name"],
            strength_value=preview_record["strength_value"],
            strength_unit=preview_record["strength_unit"],
            dose_form=preview_record["dose_form"],
        )

    with st.expander("Prévisualisation de l'enregistrement à sauvegarder", expanded=False):
        st.json(preview_record)

    if st.button("Enregistrer / mettre à jour dans medication_map", type="primary"):
        record = get_form_data()

        if not record["normalized_name"]:
            record["normalized_name"] = normalize_name(record["raw_name"] or record["display"])

        if not record["canonical_key"]:
            record["canonical_key"] = build_canonical_key(
                source_system=record["source_system"],
                normalized_name=record["normalized_name"],
                strength_value=record["strength_value"],
                strength_unit=record["strength_unit"],
                dose_form=record["dose_form"],
            )

        missing = []
        if not record["source_system"]:
            missing.append("source_system")
        if not record["medplum_medication_id"]:
            missing.append("medplum_medication_id")
        if not record["canonical_key"]:
            missing.append("canonical_key")
        if not record["raw_name"] and not record["normalized_name"]:
            missing.append("raw_name ou normalized_name")

        if missing:
            st.error("Champs obligatoires manquants : " + ", ".join(missing))
        else:
            try:
                upsert_mapping(record)
                load_medication_map.clear()
                st.success("Mapping enregistré avec succès.")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de l'enregistrement : {e}")


# =========================
# TAB 2 - Visualisation
# =========================
with tab_view:
    st.subheader("Mappings existants")

    if mappings_df.empty:
        st.info("La table medication_map est vide.")
    else:
        view_filter = st.text_input(
            "Filtrer les mappings",
            placeholder="Ex: gabapentin, iphone, capsule, 300..."
        )

        view_df = mappings_df.copy()

        if view_filter.strip():
            pattern = view_filter.strip().lower()
            mask = (
                view_df["source_system"].fillna("").str.lower().str.contains(pattern, na=False)
                | view_df["canonical_key"].fillna("").str.lower().str.contains(pattern, na=False)
                | view_df["raw_name"].fillna("").str.lower().str.contains(pattern, na=False)
                | view_df["normalized_name"].fillna("").str.lower().str.contains(pattern, na=False)
                | view_df["display"].fillna("").str.lower().str.contains(pattern, na=False)
                | view_df["code_value"].fillna("").astype(str).str.lower().str.contains(pattern, na=False)
                | view_df["medplum_medication_id"].fillna("").str.lower().str.contains(pattern, na=False)
            )
            view_df = view_df[mask]

        st.dataframe(view_df, use_container_width=True, hide_index=True)

        csv_bytes = view_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Télécharger en CSV",
            data=csv_bytes,
            file_name="medication_map.csv",
            mime="text/csv",
        )