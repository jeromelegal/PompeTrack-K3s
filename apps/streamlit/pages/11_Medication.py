import json
import os
from typing import Optional
from libs.db_service import get_connection

import pandas as pd
import psycopg2
import streamlit as st


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


def build_medication_json(code: str, display: str) -> dict:
    """Build a minimal FHIR Medication resource."""
    return {
        "resourceType": "Medication",
        "code": {
            "coding": [
                {
                    "system": RXNORM_SYSTEM,
                    "code": str(code),
                    "display": display,
                }
            ],
            "text": display,
        },
    }


st.title("Recherche RxNorm pour créer un FHIR Medication")
st.write(
    "Recherche dans `rxnconso` sur les types `SCD` et `SBD` afin de récupérer un code RxNorm précis "
    "(dosage / forme / éventuellement marque)."
)

# with st.sidebar:
#     st.header("Connexion PostgreSQL")
#     st.caption("Les paramètres sont lus depuis les variables d'environnement.")
#     st.code(
#         "\n".join(
#             [
#                 f"PGHOST={os.getenv('PGHOST', 'localhost')}",
#                 f"PGPORT={os.getenv('PGPORT', '5432')}",
#                 f"PGDATABASE={os.getenv('PGDATABASE', 'postgres')}",
#                 f"PGUSER={os.getenv('PGUSER', 'postgres')}",
#                 "PGPASSWORD=********" if os.getenv("PGPASSWORD") else "PGPASSWORD=(vide)",
#             ]
#         )
#     )

col1, col2 = st.columns([2, 1])

with col1:
    keyword = st.text_input(
        "Mot clé médicament",
        value="mirtazapine",
        help="Exemples : mirtazapine, duloxetine, levothyroxine, etc.",
    )

with col2:
    tty_selection = st.multiselect(
        "Types RxNorm",
        options=["SCD", "SBD"],
        default=["SCD", "SBD"],
        help="SCD = générique structuré ; SBD = version brandée.",
    )

search_clicked = st.button("Rechercher", type="primary")

if search_clicked:
    if not keyword.strip():
        st.warning("Saisis un mot clé.")
    elif not tty_selection:
        st.warning("Sélectionne au moins un type RxNorm.")
    else:
        try:
            results = search_rxnorm(keyword, tuple(tty_selection))
        except Exception as exc:
            st.error(f"Erreur PostgreSQL : {exc}")
        else:
            st.subheader("Résultats")
            st.caption(f"{len(results)} résultat(s)")
            st.dataframe(results, use_container_width=True, hide_index=True)

            if not results.empty:
                results = results.copy()
                results["label"] = results.apply(
                    lambda row: f"[{row['tty']}] {row['str']}  |  RxCUI={row['rxcui']}  |  code={row['code']}",
                    axis=1,
                )

                selected_label = st.selectbox(
                    "Choisis une entrée pour générer le JSON FHIR Medication",
                    options=results["label"].tolist(),
                )
                selected_row = results.loc[results["label"] == selected_label].iloc[0]

                st.subheader("Détail de l'entrée sélectionnée")
                detail_col1, detail_col2, detail_col3, detail_col4 = st.columns(4)
                detail_col1.metric("RxCUI", str(selected_row["rxcui"]))
                detail_col2.metric("TTY", str(selected_row["tty"]))
                detail_col3.metric("Code", str(selected_row["code"]))
                detail_col4.metric("Display", str(selected_row["str"]))

                medication_json = build_medication_json(
                    code=str(selected_row["code"]),
                    display=str(selected_row["str"]),
                )

                st.subheader("FHIR Medication JSON")
                st.json(medication_json)

                json_text = json.dumps(medication_json, indent=2, ensure_ascii=False)
                st.download_button(
                    label="Télécharger le JSON",
                    data=json_text,
                    file_name=f"medication_{selected_row['code']}.json",
                    mime="application/json",
                )

                with st.expander("Version texte à copier"):
                    st.code(json_text, language="json")
            else:
                st.info("Aucun résultat trouvé pour ce mot clé.")

st.divider()

with st.expander("SQL utilisé"):
    st.code(
        """
SELECT rxcui, tty, code, str
FROM rxnconso
WHERE str ILIKE '%mirtazapine%'
  AND tty IN ('SCD', 'SBD')
ORDER BY tty, str;
        """.strip(),
        language="sql",
    )

# with st.expander("Exemple de variables d'environnement"):
#     st.code(
#         """
# PGHOST=pompetrack-core-postgresql
# PGPORT=5432
# PGDATABASE=postgres
# PGUSER=<utilisateur_sql>
# PGPASSWORD=<mot_de_passe>
#         """.strip(),
#         language="bash",
#     )
