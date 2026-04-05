import json
import pandas as pd
import streamlit as st
from libs.minio_requests import upload_medication_json
from libs.db_service import get_connection

st.set_page_config(page_title="RxNorm → FHIR Medication", layout="wide")

RXNORM_SYSTEM = "http://www.nlm.nih.gov/research/umls/rxnorm"


@st.cache_data(ttl=60)
def search_rxnorm(keyword: str, tty_values: tuple[str, ...]) -> pd.DataFrame:
    """Search RxNorm concepts by keyword and TTY."""
    if not keyword.strip():
        return pd.DataFrame(columns=["rxcui", "tty", "code", "str"])

    conn = get_connection()
    placeholders = ", ".join(["%s"] * len(tty_values))
    query = f"""
        SELECT rxcui, tty, code, str
        FROM rxnconso
        WHERE str ILIKE %s
          AND tty IN ({placeholders})
        ORDER BY tty, str;
    """ 
    params = [f"%{keyword.strip()}%", *tty_values]
    return pd.read_sql_query(query, conn, params=params)


def build_medication_json(rxcui: str, display: str) -> dict:
    """Build a minimal FHIR Medication resource."""
    return {
        "code_system": RXNORM_SYSTEM,
        "code_code": str(rxcui),
        "code_display": display,
        "code_text": display
    }

# Initialisation du state
if "rxnorm_results" not in st.session_state:
    st.session_state.rxnorm_results = None

if "rxnorm_keyword" not in st.session_state:
    st.session_state.rxnorm_keyword = "mirtazapine"

if "rxnorm_tty_selection" not in st.session_state:
    st.session_state.rxnorm_tty_selection = ["SCD", "SBD"]

if "selected_rxnorm_label" not in st.session_state:
    st.session_state.selected_rxnorm_label = None


st.title("Recherche RxNorm pour créer un FHIR Medication")
st.write(
    "Recherche dans `rxnconso` sur les types `SCD` et `SBD` afin de récupérer un code RxNorm précis "
    "(dosage / forme / éventuellement marque)."
)

col1, col2 = st.columns([2, 1])

with col1:
    keyword = st.text_input(
        "Mot clé médicament",
        value=st.session_state.rxnorm_keyword,
        help="Exemples : mirtazapine, duloxetine, levothyroxine, etc.",
    )

with col2:
    tty_selection = st.multiselect(
        "Types RxNorm",
        options=["SCD", "SBD"],
        default=st.session_state.rxnorm_tty_selection,
        help="SCD = générique structuré ; SBD = version brandée.",
    )


if st.button("Rechercher", type="primary"):
    st.session_state.rxnorm_keyword = keyword
    st.session_state.rxnorm_tty_selection = tty_selection

    if not keyword.strip():
        st.warning("Saisis un mot clé.")
        st.session_state.rxnorm_results = None
        st.session_state.selected_rxnorm_label = None

    elif not tty_selection:
        st.warning("Sélectionne au moins un type RxNorm.")
        st.session_state.rxnorm_results = None
        st.session_state.selected_rxnorm_label = None

    else:
        try:
            results = search_rxnorm(keyword, tuple(tty_selection))
            st.session_state.rxnorm_results = results
            st.session_state.selected_rxnorm_label = None
        except Exception as exc:
            st.error(f"Erreur PostgreSQL : {exc}")
            st.session_state.rxnorm_results = None
            st.session_state.selected_rxnorm_label = None


results = st.session_state.rxnorm_results

if results is not None:
    st.subheader("Résultats")
    st.caption(f"{len(results)} résultat(s)")
    st.dataframe(results, use_container_width=True, hide_index=True)

    if not results.empty:
        results_display = results.copy()
        results_display["label"] = results_display.apply(
            lambda row: (
                f"[{row['tty']}] {row['str']}  |  "
                f"RxCUI={row['rxcui']}  |  code={row['code']}"
            ),
            axis=1,
        )

        labels = results_display["label"].tolist()

        if (
            st.session_state.selected_rxnorm_label is None
            or st.session_state.selected_rxnorm_label not in labels
        ):
            st.session_state.selected_rxnorm_label = labels[0]

        selected_label = st.selectbox(
            "Choisis une entrée pour générer le JSON FHIR Medication",
            options=labels,
            key="selected_rxnorm_label",
        )

        selected_row = results_display.loc[
            results_display["label"] == selected_label
        ].iloc[0]

        st.subheader("Détail de l'entrée sélectionnée")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("RxCUI", str(selected_row["rxcui"]))
        c2.metric("TTY", str(selected_row["tty"]))
        c3.metric("Code", str(selected_row["code"]))
        c4.metric("Display", str(selected_row["str"]))

        medication_json = build_medication_json(
            rxcui=str(selected_row["rxcui"]),
            display=str(selected_row["str"]),
        )

        st.subheader("FHIR Medication JSON")
        st.json(medication_json)

        medication_text = json.dumps(medication_json, indent=2, ensure_ascii=False)
        # st.upload_button(
        #     label="Upload le Medication JSON",
        #     data=medication_text,
        #     file_name=f"medication_{selected_row['rxcui']}.json",
        #     mime="application/json",
        # )

        if medication_text is not None:
            if st.button("Envoyer JSON"):
                try:
                    r = upload_medication_json(medication_text)
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as e:
                    st.error(str(e))
                except requests.RequestException as e:
                    st.error(f"Erreur réseau: {e}")
                else:
                    show_response(r)

        with st.expander("Medication JSON à copier"):
            st.code(medication_text, language="json")

        # transaction_bundle = build_medplum_transaction_bundle(
        #     rxcui=str(selected_row["rxcui"]),
        #     display=str(selected_row["str"]),
        # )

        # st.subheader("Bundle transaction Medplum")
        # st.json(transaction_bundle)

        # bundle_text = json.dumps(transaction_bundle, indent=2, ensure_ascii=False)
        # st.download_button(
        #     label="Télécharger le Bundle transaction",
        #     data=bundle_text,
        #     file_name=f"bundle_medication_{selected_row['rxcui']}.json",
        #     mime="application/json",
        # )

        # with st.expander("Bundle transaction à copier"):
        #     st.code(bundle_text, language="json")

    else:
        st.info("Aucun résultat trouvé pour ce mot clé.")

st.divider()
