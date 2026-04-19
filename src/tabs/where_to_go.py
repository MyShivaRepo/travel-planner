import streamlit as st

import database as db
from llm_api import generate_pois, generate_activities


def render():
    st.header("Where to Go")

    api_key = st.session_state.get("api_key", "")

    # ── Formulaire de nouvelle destination ────────────────────────────────────
    st.subheader("Nouvelle destination")
    col1, col2 = st.columns([3, 2])
    with col1:
        nom = st.text_input("Nom", placeholder="ex : Paris, Toscane, Japon...")
    with col2:
        type_dest = st.selectbox("Type", ["Pays", "Région", "Ville"])

    col_poi, col_act = st.columns(2)
    with col_poi:
        nb_pois = st.slider("Nombre de POIs", min_value=3, max_value=20, value=8)
    with col_act:
        nb_activities = st.slider("Nombre d'activités", min_value=0, max_value=15, value=5)

    if st.button("Rechercher", type="primary"):
        if not nom.strip():
            st.warning("Veuillez saisir un nom de destination.")
            return
        if not api_key:
            st.error("Veuillez d'abord configurer votre clé API dans l'onglet Settings.")
            return

        provider = st.session_state.get("llm_provider")
        pois = []
        activities = []

        with st.spinner(f"Recherche des {nb_pois} POIs pour « {nom} »..."):
            try:
                pois = generate_pois(nom.strip(), type_dest, nb_pois, provider=provider, api_key=api_key)
            except Exception as e:
                st.error(f"Erreur lors de la génération des POIs : {e}")
                return

        if not pois:
            st.warning("Aucun POI retourné. Essayez une autre destination.")
            return

        if nb_activities > 0:
            with st.spinner(f"Recherche des {nb_activities} activités pour « {nom} »..."):
                try:
                    activities = generate_activities(
                        nom.strip(), type_dest, nb_activities,
                        provider=provider, api_key=api_key,
                    )
                except Exception as e:
                    st.warning(f"Activités non générées : {e}")

        dest_id = db.create_destination(nom.strip(), type_dest)
        db.bulk_create_pois(dest_id, pois)
        db.renumber_pois(dest_id)  # garantit des rangs séquentiels 1..N
        if activities:
            db.bulk_create_activities(dest_id, activities)
            db.renumber_activities(dest_id)
        st.success(
            f"{len(pois)} POIs et {len(activities)} activités générés pour « {nom} »."
        )
        st.rerun()

    # ── Tableau des destinations existantes ───────────────────────────────────
    st.divider()
    st.subheader("Destinations enregistrées")

    destinations = db.get_all_destinations()
    if not destinations:
        st.info("Aucune destination enregistrée. Utilisez le formulaire ci-dessus.")
        return

    for dest in destinations:
        nb_p = len(db.get_pois_for_destination(dest["id"]))
        nb_a = len(db.get_activities_for_destination(dest["id"]))
        col_nom, col_type, col_nb_p, col_nb_a, col_actions = st.columns([3, 2, 1, 1, 2])
        with col_nom:
            st.write(f"**{dest['nom']}**")
        with col_type:
            st.write(dest["type"])
        with col_nb_p:
            st.write(f"{nb_p} POIs")
        with col_nb_a:
            st.write(f"{nb_a} activités")
        with col_actions:
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("Visualiser", key=f"mod_{dest['id']}"):
                    st.session_state["selected_destination_id"] = dest["id"]
                    st.session_state.pop("selected_travel_id", None)
                    st.session_state["goto_page"] = "Destination"
                    st.rerun()
            with btn_col2:
                if st.button("Supprimer", key=f"del_{dest['id']}"):
                    db.delete_destination(dest["id"])
                    if st.session_state.get("selected_destination_id") == dest["id"]:
                        st.session_state.pop("selected_destination_id", None)
                    st.rerun()
