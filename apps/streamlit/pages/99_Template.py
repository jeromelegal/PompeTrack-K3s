import streamlit as st
import json
from collections import defaultdict
from typing import Dict, Any
from utils.common import is_admin

if not is_admin():
    st.warning("Page réservée au mode ADMIN")
    st.stop()

#st.set_page_config(page_title="Template JSON Builder", layout="wide")

TEMPLATE: Dict[str, Any] = {
    "effectiveDateTime": "date",
    "periodstart": "start",
    "periodend": "end",
    "hasmember_reference": "Observation/id",
    "hasmember_display": "hasmember_display",
    "code_system": "code_system",
    "code_code": "code_code",
    "code_display": "code_display code",
    "code_text": "code_text",
    "cat_system": "cat_system",
    "cat_code": "cat_code",
    "cat_display": "cat_display",
    "cat_text": "cat_text",
    "patient_id": "patient_id",
    "performer_id": "performer_id",
    "interpret_system": "interpret_system",
    "interpret_code": "interpret_code",
    "interpret_display": "interpret_display",
    "interpret_text": "interpret_text",
    "bodysite": [],
    "method": [],
    "device_id": "device_id",
    "range_low": {},
    "range_high": {},
    "range_text": "range_text",
    "components": [
        {"code_system[0]": "code_system[0]",
         "code_code[0]": "code_code[0]",
         "code_display[0]": "code_display[0]",
         "value_value[0]": "value_value[0]",
         "value_unit[0]": "value_unit[0]",
         "inter_system[0]": "inter_system[0]",
         "inter_code[0]": "inter_code[0]",
         "inter_display[0]": "inter_display[0]"},
        {"code_system[1]": "code_system[1]",
         "code_code[1]": "code_code[1]",
         "code_display[1]": "code_display[1]",
         "value_value[1]": "value_value[1]",
         "value_unit[1]": "value_unit[1]",
         "inter_system[1]": "inter_system[1]",
         "inter_code[1]": "inter_code[1]",
         "inter_display[1]": "inter_display[1]"}
    ],
    "value_value": "qty",
    "value_unit": "units",
    "note_text": [],
    "tag_system": "http://phylcero.fr/fhir/StructureDefinition/observation-group",
    "tag_code": "tag_code"
}

def group_by_prefix(template: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Group keys by prefix (text before first underscore)."""
    groups = defaultdict(dict)
    for k, v in template.items():
        if "_" in k:
            prefix = k.split("_", 1)[0]
        else:
            prefix = "other"
        groups[prefix][k] = v
    return dict(groups)

def build_selected_template(selected_keys: Dict[str, bool], template: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dict containing only selected keys."""
    return {k: template[k] for k, v in selected_keys.items() if v}


st.title("Générateur de template JSON")
st.caption("Choisir les clés à inclure dans le JSON final.")

# Filename
col1, col2 = st.columns([3,1])
with col1:
    filename = st.text_input("Nom du fichier final", value="template_observation")
with col2:
    st.write("")
    st.markdown("**Format :** `.json`")

# Grouping
groups = group_by_prefix(TEMPLATE)

# Initialize checkbox state → all False by default
if "selected_keys" not in st.session_state:
    st.session_state.selected_keys = {k: False for k in TEMPLATE.keys()}

# Display sections
left, right = st.columns(2)
group_items = sorted(groups.items(), key=lambda t: t[0])

for i, (prefix, entries) in enumerate(group_items):
    target_col = left if i % 2 == 0 else right
    with target_col:
        with st.expander(f"Section '{prefix}' — {len(entries)} éléments", expanded=False):

            for k, v in sorted(entries.items()):
                preview = json.dumps(v, ensure_ascii=False)
                label = f"{k} — {preview}"

                st.session_state.selected_keys.setdefault(k, False)
                st.session_state.selected_keys[k] = st.checkbox(
                    label,
                    value=st.session_state.selected_keys[k],
                    key=f"cb_{k}"
                )

st.markdown("---")
actions_col1, actions_col2, actions_col3 = st.columns([1,1,2])

with actions_col1:
    if st.button("Voir le résultat"):
        selected = build_selected_template(st.session_state.selected_keys, TEMPLATE)
        st.code(json.dumps(selected, indent=2, ensure_ascii=False), language="json")

with actions_col2:
    selected = build_selected_template(st.session_state.selected_keys, TEMPLATE)
    json_bytes = json.dumps(selected, indent=2, ensure_ascii=False).encode("utf-8")
    st.download_button("Télécharger le JSON", data=json_bytes,
                       file_name=f"{filename or 'template'}.json",
                       mime="application/json")

with actions_col3:
    st.write("Uploader (placeholder)")
    if st.button("Uploader (stub)"):
        def upload_stub(data_bytes: bytes, filename_local: str):
            st.info("Cette fonction d'upload est un stub. Remplace-la par ta logique réelle.")
            return True

        success = upload_stub(json_bytes, f"{filename}.json")
        st.success("Upload OK (stub).") if success else st.error("Échec de l'upload (stub).")

st.markdown("---")
total_selected = sum(1 for v in st.session_state.selected_keys.values() if v)
st.write(f"Total : {len(TEMPLATE)} clés — {total_selected} sélectionnées.")
