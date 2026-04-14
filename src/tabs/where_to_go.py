import streamlit as st
import pandas as pd

import database as db
from llm_api import generate_pois


def render():
    st.header("Where to Go")

    api_key = st.session_state.get("api_key", "")

    # ── Formulaire de nouvelle destination ────────────────────────────────────
    st.subheader("Nouvelle destination")
    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        nom = st.text_input("Nom", placeholder="ex : Paris, Toscane, Japon...")
    with col2:
        type_dest = st.selectbox("Type", ["Pays", "Région", "Ville"])
    with col3:
        nb_pois = st.slider("Nombre de POI", min_value=3, max_value=20, value=8)

    if st.button("Rechercher", type="primary"):
        if not nom.strip():
            st.warning("Veuillez saisir un nom de destination.")
            return
        if not api_key:
            st.error("Veuillez d'abord configurer votre clé API dans l'onglet Settings.")
            return

        with st.spinner(f"Recherche des {nb_pois} POI pour « {nom} »..."):
            try:
                provider = st.session_state.get("llm_provider")
                pois = generate_pois(nom.strip(), type_dest, nb_pois, provider=provider, api_key=api_key)
            except Exception as e:
                st.error(f"Erreur lors de la génération des POI : {e}")
                return

        if not pois:
            st.warning("Aucun POI retourné. Essayez une autre destination.")
            return

        dest_id = db.create_destination(nom.strip(), type_dest)
        db.bulk_create_pois(dest_id, pois)
        st.success(f"{len(pois)} POI générés pour « {nom} ».")
        st.rerun()

    # ── Tableau des destinations existantes ───────────────────────────────────
    st.divider()
    st.subheader("Destinations enregistrées")

    destinations = db.get_all_destinations()
    if not destinations:
        st.info("Aucune destination enregistrée. Utilisez le formulaire ci-dessus.")
        return

    for dest in destinations:
        nb = len(db.get_pois_for_destination(dest["id"]))
        col_nom, col_type, col_nb, col_actions = st.columns([3, 2, 1, 2])
        with col_nom:
            st.write(f"**{dest['nom']}**")
        with col_type:
            st.write(dest["type"])
        with col_nb:
            st.write(f"{nb} POI")
        with col_actions:
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("Visualiser", key=f"mod_{dest['id']}"):
                    st.session_state["selected_destination_id"] = dest["id"]
                    st.session_state["goto_page"] = "Destination"
                    st.rerun()
            with btn_col2:
                if st.button("Supprimer", key=f"del_{dest['id']}"):
                    db.delete_destination(dest["id"])
                    if st.session_state.get("selected_destination_id") == dest["id"]:
                        st.session_state.pop("selected_destination_id", None)
                    st.rerun()
