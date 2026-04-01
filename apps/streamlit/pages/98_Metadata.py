import streamlit as st
import json
from utils.common import is_admin

if not is_admin():
    st.warning("Page réservée au mode ADMIN")
    st.stop()

#st.set_page_config(page_title="Metadata Builder", layout="wide")

def make_metadata_dict(name: str, template: str, constants: dict) -> dict:
    return {"name": name, "template": template, "constants": constants}

st.title("Générateur de fichiers — metadata (1 mesure = 1 fichier)")
st.write("Crée un fichier JSON de *metadata* (constantes par mesure).")


col_name, col_template = st.columns([2, 3])
with col_name:
    name = st.text_input("Nom de la mesure (champ `name`)", value="", placeholder="ex: heart_rate")
with col_template:
    template_field = st.text_input("Nom du template", value="", placeholder="ex: heart_rate.json")
    

st.markdown("---")


if "constants" not in st.session_state:
    # seed with empty well-known keys used in your example
    st.session_state.constants = {
        "cat_system": {"include": False, "value": "http://terminology.hl7.org/CodeSystem/observation-category"},
        "cat_code": {"include": False, "value": "vital-signs"},
        "cat_display": {"include": False, "value": "Vital Signs"},
        "cat_text": {"include": False, "value": ""},
        "code_system": {"include": False, "value": "http://loinc.org"},
        "code_code": {"include": False, "value": ""},
        "code_display": {"include": False, "value": ""},
        "code_text": {"include": False, "value": ""},
        "patient_id": {"include": False, "value": "1797fcc2-2d95-47d6-9045-c188d9e1d02a"},
        "device_id": {"include": False, "value": "c9dea642-a030-4484-8b17-3cc0d0fdb9b0"},
        # list fields
        "bodysite": {"include": False, "value": []},
        "method": {"include": False, "value": []},
        "note_text": {"include": False, "value": []},
        # ranges
        "range_low": {"include": False, "value": {"comparator": "", "value": "", "unit": ""}},
        "range_high": {"include": False, "value": {"comparator": "", "value": "", "unit": ""}},
        # components (list)
        "component": {"include": False, "value": []},
        # generic others
        "tag_system": {"include": False, "value": "http://phylcero.fr/fhir/StructureDefinition/observation-group"},
        "tag_code": {"include": False, "value": ""}
    }

    st.session_state.comp_counter = 0



if "comp_counter" not in st.session_state:
    st.session_state.comp_counter = 0

with st.expander("Éditer `constants`", expanded=True):
    col_add, col_import = st.columns([2,2])
    with col_add:
        with st.form("add_constant"):
            new_key = st.text_input("Ajouter une clé dans constants (ex: code_code[0])", "")
            new_value = st.text_input("Valeur par défaut (optionnel)", "")
            add_sub = st.form_submit_button("Ajouter la clé")
            if add_sub and new_key:
                if new_key in st.session_state.constants:
                    st.warning("Clé déjà existante.")
                else:
                    st.session_state.constants[new_key] = {"include": True, "value": new_value}
                    st.success(f"Clé '{new_key}' ajoutée.")

    st.markdown("---")

    # Render editor
    cols = st.columns([2,3,3])
    with cols[0]:
        st.subheader("Champs simples")
        simple_keys = [k for k in st.session_state.constants.keys() if not any(x in k for x in ["[", "components", "bodysite", "method", "note_text", "range_low", "range_high"]) ]
        for k in simple_keys:
            item = st.session_state.constants[k]
            include = st.checkbox(f"Inclure `{k}`", value=item.get("include", False), key=f"incl_{k}")
            st.session_state.constants[k]["include"] = include
            if include:
                if isinstance(item.get("value"), list) or isinstance(item.get("value"), dict):
                    current_text = json.dumps(item.get("value"), ensure_ascii=False)
                    new_text = st.text_area(f"Valeur `{k}` (JSON)", value=current_text, key=f"val_{k}")
                    try:
                        parsed = json.loads(new_text)
                        st.session_state.constants[k]["value"] = parsed
                    except Exception:
                        st.session_state.constants[k]["value"] = new_text
                else:
                    st.session_state.constants[k]["value"] = st.text_input(f"Valeur `{k}`", value=item.get("value", ""), key=f"val_{k}")

    with cols[1]:
        st.subheader("Listes éditables")
        for list_key in ["bodysite", "method", "note_text"]:
            item = st.session_state.constants.get(list_key, {"include": False, "value": []})
            include = st.checkbox(f"Inclure `{list_key}`", value=item.get("include", False), key=f"incl_list_{list_key}")
            st.session_state.constants[list_key] = item
            st.session_state.constants[list_key]["include"] = include
            if include:
                # current list
                current = list(st.session_state.constants[list_key].get("value", []) or [])
                st.write(f"Éléments `{list_key}` (ajout / suppression)")
                new_item = st.text_input(f"Ajouter un élément à `{list_key}`", key=f"add_{list_key}")
                if st.button(f"Ajouter à {list_key}", key=f"btn_add_{list_key}"):
                    if new_item:
                        current.append(new_item)
                        st.session_state.constants[list_key]["value"] = current
                # display and allow removal
                for i, it in enumerate(current):
                    cols_rm = st.columns([4,1])
                    cols_rm[0].write(f"- {it}")
                    if cols_rm[1].button("Suppr", key=f"rm_{list_key}_{i}"):
                        current.pop(i)
                        st.session_state.constants[list_key]["value"] = current
                st.session_state.constants[list_key]["value"] = current

    with cols[2]:
        st.subheader("Ranges & Components")
        # ranges
        for rkey in ["range_low", "range_high"]:
            item = st.session_state.constants.get(rkey, {"include": False, "value": {"comparator":"", "value":"", "unit":""}})
            include = st.checkbox(f"Inclure `{rkey}`", value=item.get("include", False), key=f"incl_range_{rkey}")
            st.session_state.constants[rkey] = item
            st.session_state.constants[rkey]["include"] = include
            if include:
                comp = st.text_input(f"{rkey} comparator (ex: >, <, >=)", value=item["value"].get("comparator",""), key=f"{rkey}_comparator")
                val = st.text_input(f"{rkey} value", value=item["value"].get("value",""), key=f"{rkey}_value")
                unit = st.text_input(f"{rkey} unit", value=item["value"].get("unit",""), key=f"{rkey}_unit")
                st.session_state.constants[rkey]["value"] = {"comparator": comp, "value": val, "unit": unit}

        st.markdown("---")
        # components dynamic list

        st.write("Component (liste d'objets).")
        comps_item = st.session_state.constants.get("component", {"include": False, "value": []})
        include_comps = st.checkbox("Inclure `component`", value=comps_item.get("include", False), key="incl_components")
        # ensure key exists
        if "component" not in st.session_state.constants:
            st.session_state.constants["component"] = {"include": include_comps, "value": []}
        else:
            st.session_state.constants["component"]["include"] = include_comps

        if include_comps:
            comps = st.session_state.constants.get("component", {"include": False, "value": []})["value"] or []

            for idx, comp in enumerate(comps):
                st.markdown(f"**Component — index: {idx}**")

                available_fields = ["code_system", "code_code", "code_display", "code_text", "value_value", "value_unit", "inter_system", "inter_code", "inter_display"]
                sel = comp.get("_fields", available_fields)

                sel_fields = st.multiselect(f"Champs à inclure pour component {idx}", options=available_fields, default=sel, key=f"fields_{idx}")
                comp["_fields"] = sel_fields

                # inputs for selected fields
                cols1 = st.columns(3)
                if "code_system" in sel_fields:
                    comp["code_system"] = cols1[0].text_input(f"code_system[{idx}]", value=comp.get("code_system",""), key=f"cs_{idx}")
                if "code_code" in sel_fields:
                    comp["code_code"] = cols1[1].text_input(f"code_code[{idx}]", value=comp.get("code_code",""), key=f"cc_{idx}")
                if "code_display" in sel_fields:
                    comp["code_display"] = cols1[2].text_input(f"code_display[{idx}]", value=comp.get("code_display",""), key=f"cd_{idx}")
                # add code_text field
                if "code_text" in sel_fields:
                    comp["code_text"] = st.text_input(f"code_text[{idx}]", value=comp.get("code_text",""), key=f"ct_{idx}")

                dcols = st.columns([2,2,2])
                if "value_value" in sel_fields:
                    comp["value_value"] = dcols[0].text_input(f"value_value[{idx}]", value=comp.get("value_value",""), key=f"vv_{idx}")
                if "value_unit" in sel_fields:
                    comp["value_unit"] = dcols[1].text_input(f"value_unit[{idx}]", value=comp.get("value_unit",""), key=f"vu_{idx}")
                if "inter_system" in sel_fields:
                    comp["inter_system"] = dcols[2].text_input(f"inter_system[{idx}]", value=comp.get("inter_system",""), key=f"is_{idx}")

                if "inter_code" in sel_fields:
                    comp["inter_code"] = st.text_input(f"inter_code[{idx}]", value=comp.get("inter_code",""), key=f"ic_{idx}")
                if "inter_display" in sel_fields:
                    comp["inter_display"] = st.text_input(f"inter_display[{idx}]", value=comp.get("inter_display",""), key=f"idis_{idx}")

                rm_col = st.columns([1,4])
                # When deleting a component, update the stored list
                if rm_col[0].button(f"Supprimer component {idx}", key=f"rm_comp_{idx}"):
                    comps.pop(idx)

                    st.session_state.constants["component"]["value"] = comps
                    st.success(f"Component {idx} supprimé.")
                    
                st.markdown("---")

            add_col = st.columns([1,4])
            if add_col[0].button("Ajouter un component", key="btn_add_comp"):
                new_comp = {
                    "code_system": "",
                    "code_code": "",
                    "code_display": "",
                    "code_text": "",
                    "value_value": "",
                    "value_unit": "",
                    "inter_system": "",
                    "inter_code": "",
                    "inter_display": "",
                    "_fields": ["code_system", "code_code"]
                }
                comps.append(new_comp)
                st.session_state.constants["component"]["value"] = comps
                st.success("Component ajouté.")
                

            # persist
            st.session_state.constants["component"]["value"] = comps
        
# Build final constants dict from included items
def build_constants_dict():
    out = {}
    for k, meta in st.session_state.constants.items():
        if not meta.get("include", False):
            continue
        if k == "component":
            comps = meta.get("value", []) or []
            transformed = []
            for idx, comp in enumerate(comps):
                # only include selected fields (stored in _fields)
                fields = comp.get("_fields", [])
                item = {}
                for f in fields:
                    val = comp.get(f, "")
                    item[f"{f}[{idx}]"] = val

                transformed.append(item)
            out["component"] = transformed
        else:
            out[k] = meta.get("value")
    return out

actions = st.columns([1,1,2])
with actions[0]:
    if st.button("Prévisualiser JSON"):
        if not name:
            st.warning("Donne un nom pour la mesure (champ `name`).")
        else:
            metadata = make_metadata_dict(name, template_field, build_constants_dict())
            st.code(json.dumps(metadata, indent=2, ensure_ascii=False), language="json")

with actions[1]:
    metadata = make_metadata_dict(name, template_field, build_constants_dict())
    json_bytes = json.dumps(metadata, indent=2, ensure_ascii=False).encode("utf-8")
    st.download_button("Télécharger le fichier .json", data=json_bytes,
                       file_name=f"{name or 'metadata'}.json", mime="application/json")

with actions[2]:
    st.write("Uploader (stub)")
    if st.button("Uploader (stub)"):
        # replace by your own upload logic
        def upload_stub(bytes_data: bytes, filename_local: str):
            st.info("Upload stub appelé. Remplace `upload_stub` par ta fonction réelle.")
            return True
        ok = upload_stub(json_bytes, f"{name or 'metadata'}.json")
        if ok:
            st.success("Stub upload ok.")
        else:
            st.error("Echec du stub d'upload.")

st.markdown("---")
st.caption("Outil de développement")
