import streamlit as st
import streamlit.components.v1 as components
import folium
import pandas as pd

import database as db
from llm_api import generate_travel

# ── Couleurs des marqueurs par type de POI ───────────────────────────────────
CATEGORY_COLORS = {
    "Monument": "red", "Musée": "blue", "Nature": "green",
    "Gastronomie": "orange", "Plage": "cadetblue", "Parc": "darkgreen",
    "Château": "darkred", "Église": "purple", "Architecture": "darkpurple",
    "Histoire": "darkblue", "Marché": "beige", "Sport": "lightblue",
}


def _marker_color(cat):
    for key, color in CATEGORY_COLORS.items():
        if key.lower() in cat.lower():
            return color
    return "gray"


def _compute_zoom(lat_min, lat_max, lon_min, lon_max):
    span = max(lat_max - lat_min, lon_max - lon_min)
    if span < 0.01:  return 15
    if span < 0.05:  return 14
    if span < 0.15:  return 13
    if span < 0.4:   return 12
    if span < 1.0:   return 11
    if span < 2.5:   return 10
    if span < 5.0:   return 9
    if span < 10.0:  return 8
    if span < 20.0:  return 7
    if span < 40.0:  return 6
    if span < 80.0:  return 5
    return 4


def render():
    st.header("Destination")

    dest_id = st.session_state.get("selected_destination_id")
    if not dest_id:
        st.info("Sélectionnez une destination depuis l'onglet « Where to Go ».")
        return

    dest = db.get_destination(dest_id)
    if not dest:
        st.warning("Destination introuvable.")
        return

    st.subheader(f"{dest['nom']} ({dest['type']})")

    pois = db.get_pois_for_destination(dest_id)

    # ── Sous-onglets ─────────────────────────────────────────────────────────
    sub_tab_table, sub_tab_map = st.tabs(["Tableau", "Carte"])

    # ── Sous-onglet Tableau ──────────────────────────────────────────────────
    with sub_tab_table:
        if not pois:
            st.info("Aucun POI pour cette destination.")
        else:
            # Tri par clic sur en-tête
            HEADERS = [
                ("Rang", "rang", 0.5), ("Nom", "nom", 2), ("Type", "type", 1.5),
                ("Description", "description", 3), ("Lat.", "latitude", 1), ("Lon.", "longitude", 1),
            ]
            if "sort_key" not in st.session_state:
                st.session_state["sort_key"] = "rang"
                st.session_state["sort_asc"] = True

            header_cols = st.columns([h[2] for h in HEADERS] + [1.5])
            for i, (label, key, _) in enumerate(HEADERS):
                arrow = ""
                if st.session_state["sort_key"] == key:
                    arrow = " ▲" if st.session_state["sort_asc"] else " ▼"
                with header_cols[i]:
                    if st.button(f"{label}{arrow}", key=f"sort_{key}", use_container_width=True):
                        if st.session_state["sort_key"] == key:
                            st.session_state["sort_asc"] = not st.session_state["sort_asc"]
                        else:
                            st.session_state["sort_key"] = key
                            st.session_state["sort_asc"] = True
                        st.rerun()
            with header_cols[-1]:
                st.markdown("**Actions**")

            sort_key = st.session_state["sort_key"]
            sort_asc = st.session_state["sort_asc"]
            sorted_pois = sorted(pois, key=lambda p: (p[sort_key] is None, p[sort_key]), reverse=not sort_asc)

            # Lignes du tableau
            for poi in sorted_pois:
                col_rang, col_nom, col_type, col_desc, col_lat, col_lon, col_actions = st.columns(
                    [0.5, 2, 1.5, 3, 1, 1, 1.5]
                )
                with col_rang:
                    st.write(str(poi["rang"]))
                with col_nom:
                    st.write(f"**{poi['nom']}**")
                with col_type:
                    st.write(poi["type"])
                with col_desc:
                    st.write(poi["description"] or "")
                with col_lat:
                    st.write(f"{poi['latitude']:.4f}")
                with col_lon:
                    st.write(f"{poi['longitude']:.4f}")
                with col_actions:
                    a1, a2 = st.columns(2)
                    with a1:
                        if st.button("Modifier", key=f"edit_poi_{poi['id']}"):
                            st.session_state[f"editing_poi_{poi['id']}"] = True
                            st.rerun()
                    with a2:
                        if st.button("Supprimer", key=f"del_poi_{poi['id']}"):
                            db.delete_poi(poi["id"])
                            st.rerun()

                # ── Formulaire de modification inline ────────────────────────
                if st.session_state.get(f"editing_poi_{poi['id']}"):
                    with st.expander(f"Modifier « {poi['nom']} »", expanded=True):
                        with st.form(key=f"form_edit_{poi['id']}"):
                            e_rang = st.number_input("Rang", value=poi["rang"], min_value=1)
                            e_nom = st.text_input("Nom", value=poi["nom"])
                            e_type = st.text_input("Type", value=poi["type"])
                            e_desc = st.text_area("Description", value=poi["description"] or "")
                            e_lat = st.number_input("Latitude", value=poi["latitude"], format="%.6f")
                            e_lon = st.number_input("Longitude", value=poi["longitude"], format="%.6f")
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.form_submit_button("Enregistrer"):
                                    db.update_poi(poi["id"], e_rang, e_nom, e_type, e_desc, e_lat, e_lon)
                                    st.session_state.pop(f"editing_poi_{poi['id']}", None)
                                    st.rerun()
                            with c2:
                                if st.form_submit_button("Annuler"):
                                    st.session_state.pop(f"editing_poi_{poi['id']}", None)
                                    st.rerun()

        # ── Bouton Ajouter ───────────────────────────────────────────────────
        st.divider()
        if st.session_state.get("adding_poi"):
            with st.form(key="form_add_poi"):
                st.subheader("Ajouter un POI")
                a_rang = st.number_input("Rang", value=len(pois) + 1, min_value=1)
                a_nom = st.text_input("Nom")
                a_type = st.text_input("Type", value="Nature")
                a_desc = st.text_area("Description")
                a_lat = st.number_input("Latitude", value=0.0, format="%.6f")
                a_lon = st.number_input("Longitude", value=0.0, format="%.6f")
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("Enregistrer"):
                        if a_nom.strip():
                            db.create_poi(dest_id, a_rang, a_nom.strip(), a_type, a_desc, a_lat, a_lon)
                            st.session_state["adding_poi"] = False
                            st.rerun()
                        else:
                            st.warning("Le nom est obligatoire.")
                with c2:
                    if st.form_submit_button("Annuler"):
                        st.session_state["adding_poi"] = False
                        st.rerun()
        else:
            if st.button("Ajouter un POI"):
                st.session_state["adding_poi"] = True
                st.rerun()

    # ── Sous-onglet Carte ────────────────────────────────────────────────────
    with sub_tab_map:
        if not pois:
            st.info("Aucun POI à afficher sur la carte.")
        else:
            lats = [p["latitude"] for p in pois]
            lons = [p["longitude"] for p in pois]
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)
            zoom = _compute_zoom(min(lats), max(lats), min(lons), max(lons))

            m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom)
            for poi in pois:
                color = _marker_color(poi["type"])
                popup_html = (
                    f"<b>{poi['rang']}. {poi['nom']}</b><br>"
                    f"<i>{poi['type']}</i><br>"
                    f"{poi['description'] or ''}"
                )
                folium.Marker(
                    location=[poi["latitude"], poi["longitude"]],
                    popup=folium.Popup(popup_html, max_width=280),
                    tooltip=f"{poi['rang']}. {poi['nom']}",
                    icon=folium.Icon(color=color, icon="info-sign"),
                ).add_to(m)

            components.html(m._repr_html_(), height=600, scrolling=False)

    # ── Bouton Générer le voyage ─────────────────────────────────────────────
    st.divider()
    api_key = st.session_state.get("api_key", "")
    if pois:
        if st.button("Générer le voyage", type="primary"):
            if not api_key:
                st.error("Veuillez configurer votre clé API dans l'onglet Settings.")
                return
            with st.spinner("Génération du voyage jour par jour..."):
                try:
                    pois_for_api = [
                        {"nom": p["nom"], "type": p["type"],
                         "latitude": p["latitude"], "longitude": p["longitude"]}
                        for p in pois
                    ]
                    provider = st.session_state.get("llm_provider")
                    jours = generate_travel(dest["nom"], pois_for_api, provider=provider, api_key=api_key)
                except Exception as e:
                    st.error(f"Erreur lors de la génération du voyage : {e}")
                    return

            if not jours:
                st.warning("Aucun planning généré.")
                return

            # Mapper poi_noms → poi_ids
            poi_name_to_id = {p["nom"].lower(): p["id"] for p in pois}
            days_for_db = []
            for jour in jours:
                poi_ids = []
                for nom in jour.get("poi_noms", []):
                    pid = poi_name_to_id.get(nom.lower())
                    if pid:
                        poi_ids.append(pid)
                days_for_db.append({
                    "numero": jour["numero"],
                    "hotel_nom": jour.get("hotel_nom", ""),
                    "hotel_adresse": jour.get("hotel_adresse", ""),
                    "restaurant_nom": jour.get("restaurant_nom", ""),
                    "restaurant_adresse": jour.get("restaurant_adresse", ""),
                    "poi_ids": poi_ids,
                })

            db.save_travel(dest_id, days_for_db)
            st.session_state["goto_page"] = "Travel"
            st.rerun()
