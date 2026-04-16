import streamlit as st
import streamlit.components.v1 as components
import folium
import pandas as pd

import database as db
from llm_api import generate_travel, generate_additional_poi, generate_additional_activity
from routing import compute_segment_metrics

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
    dest_id = st.session_state.get("selected_destination_id")
    if not dest_id:
        st.info("Sélectionnez une destination depuis l'onglet « Where to Go ».")
        return

    dest = db.get_destination(dest_id)
    if not dest:
        st.warning("Destination introuvable.")
        return

    pois = db.get_pois_for_destination(dest_id)
    activities = db.get_activities_for_destination(dest_id)
    api_key = st.session_state.get("api_key", "")
    provider = st.session_state.get("llm_provider")

    # ── Ligne compacte : titre + bouton Générer ─────────────────────────────
    col_dest, col_gen = st.columns([4, 2])
    with col_dest:
        st.markdown(
            f"**{dest['nom']}** ({dest['type']}) — "
            f"{len(pois)} POIs — {len(activities)} activités"
        )
    with col_gen:
        if pois and st.button("Générer le voyage", type="primary", use_container_width=True):
            if not api_key:
                st.error("Configurez votre clé API dans Settings.")
            else:
                _generate_voyage(dest, pois, activities, api_key, provider)

    # ── Sous-onglets ─────────────────────────────────────────────────────────
    sub_tab_pois, sub_tab_acts, sub_tab_map = st.tabs(["POIs", "Activités", "Carte"])

    with sub_tab_pois:
        _render_table(dest_id, dest, pois, api_key, provider)

    with sub_tab_acts:
        _render_activities(dest_id, dest, activities, api_key, provider)

    with sub_tab_map:
        _render_map(pois, activities)


def _render_table(dest_id, dest, pois, api_key, provider):
    if not pois:
        st.info("Aucun POI pour cette destination.")
    else:
        # Tri par clic sur en-tête
        HEADERS = [
            ("#", "rang", 0.5), ("Nom", "nom", 2), ("Type", "type", 1.5),
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

    # Champ Commentaire + bouton Ajouter (via LLM)
    st.divider()
    commentaire = st.text_input(
        "Commentaire (facultatif)",
        placeholder="Ex : un site historique, un parc urbain, un musée d'art moderne...",
        key=f"poi_commentaire_{dest_id}",
        help="Précise au système le POI que tu souhaites ; il en tiendra compte lors de l'ajout.",
    )
    if st.button("Ajouter un POI"):
        if not api_key:
            st.error("Configurez votre clé API dans Settings.")
        else:
            spinner_msg = "Recherche d'un nouveau POI..."
            if commentaire and commentaire.strip():
                spinner_msg = f"Recherche d'un POI correspondant à : « {commentaire.strip()} »..."
            with st.spinner(spinner_msg):
                try:
                    existing = [{"nom": p["nom"]} for p in pois]
                    new_poi = generate_additional_poi(
                        dest["nom"], existing,
                        commentaire=commentaire,
                        provider=provider, api_key=api_key,
                    )
                except Exception as e:
                    st.error(f"Erreur lors de la génération : {e}")
                    new_poi = None

            if new_poi and new_poi.get("nom"):
                # Nouveau rang = dernier existant + 1 (plus fiable que len(...)+1 en cas de rangs non séquentiels)
                next_rang = (max((p["rang"] for p in pois), default=0) + 1) if pois else 1
                db.create_poi(
                    dest_id, next_rang, new_poi["nom"], new_poi.get("type", ""),
                    new_poi.get("description", ""),
                    new_poi.get("latitude", 0.0), new_poi.get("longitude", 0.0),
                )
                db.renumber_pois(dest_id)
                st.success(f"POI ajouté : {new_poi['nom']}")
                st.rerun()
            elif new_poi is not None:
                st.warning("Aucun nouveau POI trouvé.")


def _render_activities(dest_id, dest, activities, api_key, provider):
    if not activities:
        st.info("Aucune activité pour cette destination.")
    else:
        # Tri par clic sur en-tête (même pattern que POIs)
        HEADERS_ACT = [
            ("#", "rang", 0.5), ("Nom", "nom", 1.8), ("Type", "type", 1.3),
            ("Description", "description", 2.5), ("Lat.", "latitude", 0.9),
            ("Lon.", "longitude", 0.9), ("Fournisseur", "fournisseur_url", 1.2),
        ]
        if "sort_key_act" not in st.session_state:
            st.session_state["sort_key_act"] = "rang"
            st.session_state["sort_asc_act"] = True

        header_cols = st.columns([h[2] for h in HEADERS_ACT] + [1.5])
        for i, (label, key, _) in enumerate(HEADERS_ACT):
            arrow = ""
            if st.session_state["sort_key_act"] == key:
                arrow = " ▲" if st.session_state["sort_asc_act"] else " ▼"
            with header_cols[i]:
                if st.button(f"{label}{arrow}", key=f"sort_act_{key}", use_container_width=True):
                    if st.session_state["sort_key_act"] == key:
                        st.session_state["sort_asc_act"] = not st.session_state["sort_asc_act"]
                    else:
                        st.session_state["sort_key_act"] = key
                        st.session_state["sort_asc_act"] = True
                    st.rerun()
        with header_cols[-1]:
            st.markdown("**Actions**")

        sort_key = st.session_state["sort_key_act"]
        sort_asc = st.session_state["sort_asc_act"]
        sorted_acts = sorted(activities,
                              key=lambda a: (a.get(sort_key) is None, a.get(sort_key) or ""),
                              reverse=not sort_asc)

        for act in sorted_acts:
            cols = st.columns([h[2] for h in HEADERS_ACT] + [1.5])
            cols[0].write(str(act["rang"]))
            cols[1].write(f"**{act['nom']}**")
            cols[2].write(act["type"])
            cols[3].write(act["description"] or "")
            cols[4].write(f"{act['latitude']:.4f}")
            cols[5].write(f"{act['longitude']:.4f}")
            url = act.get("fournisseur_url") or ""
            if url:
                cols[6].markdown(f"[lien]({url})")
            else:
                cols[6].write("—")
            with cols[7]:
                a1, a2 = st.columns(2)
                with a1:
                    if st.button("Modifier", key=f"edit_act_{act['id']}"):
                        st.session_state[f"editing_act_{act['id']}"] = True
                        st.rerun()
                with a2:
                    if st.button("Supprimer", key=f"del_act_{act['id']}"):
                        db.delete_activity(act["id"])
                        st.rerun()

            if st.session_state.get(f"editing_act_{act['id']}"):
                with st.expander(f"Modifier « {act['nom']} »", expanded=True):
                    with st.form(key=f"form_edit_act_{act['id']}"):
                        e_rang = st.number_input("Rang", value=act["rang"], min_value=1)
                        e_nom = st.text_input("Nom", value=act["nom"])
                        e_type = st.text_input("Type", value=act["type"])
                        e_desc = st.text_area("Description", value=act["description"] or "")
                        e_lat = st.number_input("Latitude", value=act["latitude"], format="%.6f")
                        e_lon = st.number_input("Longitude", value=act["longitude"], format="%.6f")
                        e_url = st.text_input("URL fournisseur", value=act.get("fournisseur_url") or "")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.form_submit_button("Enregistrer"):
                                db.update_activity(act["id"], e_rang, e_nom, e_type, e_desc,
                                                    e_lat, e_lon, e_url or None)
                                st.session_state.pop(f"editing_act_{act['id']}", None)
                                st.rerun()
                        with c2:
                            if st.form_submit_button("Annuler"):
                                st.session_state.pop(f"editing_act_{act['id']}", None)
                                st.rerun()

    # ── Champ Commentaire + bouton Ajouter ─────────────────────────────────
    st.divider()
    commentaire = st.text_input(
        "Commentaire (facultatif)",
        placeholder="Ex : une activité en plein air, ou quelque chose pour enfants...",
        key=f"act_commentaire_{dest_id}",
        help="Précise au système l'activité que tu souhaites ; il en tiendra compte lors de l'ajout.",
    )
    if st.button("Ajouter une Activité"):
        if not api_key:
            st.error("Configurez votre clé API dans Settings.")
        else:
            spinner_msg = "Recherche d'une nouvelle activité..."
            if commentaire and commentaire.strip():
                spinner_msg = f"Recherche d'une activité correspondant à : « {commentaire.strip()} »..."
            with st.spinner(spinner_msg):
                try:
                    existing = [{"nom": a["nom"]} for a in activities]
                    new_act = generate_additional_activity(
                        dest["nom"], existing,
                        commentaire=commentaire,
                        provider=provider, api_key=api_key,
                    )
                except Exception as e:
                    st.error(f"Erreur lors de la génération : {e}")
                    new_act = None

            if new_act and new_act.get("nom"):
                next_rang = (max((a["rang"] for a in activities), default=0) + 1) if activities else 1
                db.create_activity(
                    dest_id, next_rang, new_act["nom"], new_act.get("type", ""),
                    new_act.get("description", ""),
                    new_act.get("latitude", 0.0), new_act.get("longitude", 0.0),
                    new_act.get("fournisseur_url"),
                )
                db.renumber_activities(dest_id)
                st.success(f"Activité ajoutée : {new_act['nom']}")
                st.rerun()
            elif new_act is not None:
                st.warning("Aucune nouvelle activité trouvée.")


def _render_map(pois, activities=None):
    activities = activities or []
    if not pois and not activities:
        st.info("Aucun POI ni activité à afficher sur la carte.")
        return

    all_points = [(p["latitude"], p["longitude"]) for p in pois] + \
                 [(a["latitude"], a["longitude"]) for a in activities]
    lats = [p[0] for p in all_points]
    lons = [p[1] for p in all_points]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    zoom = _compute_zoom(min(lats), max(lats), min(lons), max(lons))

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom)
    for poi in pois:
        popup_html = (
            f"<b>{poi['rang']}. {poi['nom']}</b><br>"
            f"<i>{poi['type']}</i><br>"
            f"{poi['description'] or ''}"
        )
        folium.Marker(
            location=[poi["latitude"], poi["longitude"]],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"POI{poi['rang']}. {poi['nom']}",
            icon=folium.DivIcon(
                html=f'<div style="background-color:red;color:white;border-radius:50%;'
                     f'width:24px;height:24px;text-align:center;line-height:24px;'
                     f'font-size:12px;font-weight:bold;border:2px solid darkred;">'
                     f'{poi["rang"]}</div>',
                icon_size=(24, 24),
                icon_anchor=(12, 12),
            ),
        ).add_to(m)

    for act in activities:
        popup_html = (
            f"<b>{act['rang']}. {act['nom']}</b><br>"
            f"<i>{act['type']}</i><br>"
            f"{act.get('description', '') or ''}"
        )
        folium.Marker(
            location=[act["latitude"], act["longitude"]],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"Act{act['rang']}. {act['nom']}",
            icon=folium.DivIcon(
                html=f'<div style="background-color:orange;color:white;border-radius:50%;'
                     f'width:24px;height:24px;text-align:center;line-height:24px;'
                     f'font-size:12px;font-weight:bold;border:2px solid #cc8400;">'
                     f'{act["rang"]}</div>',
                icon_size=(24, 24),
                icon_anchor=(12, 12),
            ),
        ).add_to(m)

    # Carte qui occupe tout le viewport disponible
    map_html = m._repr_html_()
    fullscreen_html = f"""
    <style>
        html, body {{ margin: 0; padding: 0; height: 100%; overflow: hidden; }}
        .folium-map {{ width: 100% !important; height: 100% !important; }}
    </style>
    {map_html}
    <script>
        // Envoie la hauteur souhaitée au parent Streamlit
        function resizeMap() {{
            var maps = document.querySelectorAll('.folium-map');
            maps.forEach(function(m) {{
                m.style.height = '100%';
                m.style.width = '100%';
            }});
        }}
        resizeMap();
        window.addEventListener('resize', resizeMap);
    </script>
    """
    # Hauteur initiale large, le CSS parent ajustera
    components.html(fullscreen_html, height=2000, scrolling=False)

    # CSS pour forcer l'iframe à occuper tout l'espace restant du viewport
    st.markdown("""
        <style>
            /* Cibler toutes les iframes de composants HTML dans les tabs */
            .stTabs [data-baseweb="tab-panel"] iframe {
                height: calc(100vh - 180px) !important;
                min-height: 300px;
            }
            /* Supprimer le padding sous l'iframe */
            .stTabs [data-baseweb="tab-panel"] .element-container:has(iframe) {
                margin-bottom: 0 !important;
                padding-bottom: 0 !important;
            }
        </style>
    """, unsafe_allow_html=True)


def _generate_voyage(dest, pois, activities, api_key, provider):
    with st.spinner("Génération du voyage jour par jour..."):
        try:
            pois_for_api = [
                {"nom": p["nom"], "type": p["type"],
                 "latitude": p["latitude"], "longitude": p["longitude"]}
                for p in pois
            ]
            activities_for_api = [
                {"nom": a["nom"], "type": a["type"],
                 "latitude": a["latitude"], "longitude": a["longitude"]}
                for a in activities
            ]
            jours = generate_travel(dest["nom"], pois_for_api,
                                     activities=activities_for_api,
                                     provider=provider, api_key=api_key)
        except Exception as e:
            st.error(f"Erreur lors de la génération du voyage : {e}")
            return

    if not jours:
        st.warning("Aucun planning généré.")
        return

    poi_name_to_id = {p["nom"].lower(): p["id"] for p in pois}
    activity_name_to_id = {a["nom"].lower(): a["id"] for a in activities}
    ors_key = st.session_state.get("ors_api_key", "")
    gmaps_key = st.session_state.get("gmaps_api_key", "")

    days_for_db = []
    for jour in jours:
        poi_ids = []
        for nom in jour.get("poi_noms", []):
            pid = poi_name_to_id.get(nom.lower())
            if pid:
                poi_ids.append(pid)
        activity_ids = []
        for nom in jour.get("activity_noms", []):
            aid = activity_name_to_id.get(nom.lower())
            if aid:
                activity_ids.append(aid)
        # Segments générés par le LLM, avec calcul de distance/durée
        segments = []
        for seg in jour.get("segments", []):
            seg_mode = seg.get("transport_mode", "voiture personnelle")
            lat1, lon1 = seg.get("from_latitude"), seg.get("from_longitude")
            lat2, lon2 = seg.get("to_latitude"), seg.get("to_longitude")
            dist_km = duration_h = None
            if lat1 and lon1 and lat2 and lon2:
                dist_km, duration_h = compute_segment_metrics(
                    seg_mode, [(lat1, lon1), (lat2, lon2)], ors_key, gmaps_key,
                )
            segments.append({
                "from_name": seg.get("from_name", ""),
                "from_latitude": lat1,
                "from_longitude": lon1,
                "to_name": seg.get("to_name", ""),
                "to_latitude": lat2,
                "to_longitude": lon2,
                "transport_mode": seg_mode,
                "distance_km": dist_km,
                "duration_h": duration_h,
                "budget": seg.get("budget"),
            })

        days_for_db.append({
            "numero": jour["numero"],
            "hotel_nom": jour.get("hotel_nom", ""),
            "hotel_adresse": jour.get("hotel_adresse", ""),
            "hotel_latitude": jour.get("hotel_latitude"),
            "hotel_longitude": jour.get("hotel_longitude"),
            "hotel_budget": jour.get("hotel_budget"),
            "restaurant_nom": jour.get("restaurant_nom", ""),
            "restaurant_adresse": jour.get("restaurant_adresse", ""),
            "restaurant_latitude": jour.get("restaurant_latitude"),
            "restaurant_longitude": jour.get("restaurant_longitude"),
            "restaurant_budget": jour.get("restaurant_budget"),
            "poi_ids": poi_ids,
            "activity_ids": activity_ids,
            "segments": segments,
        })

    travel_id = db.save_travel(dest["id"], days_for_db)
    st.session_state["selected_travel_id"] = travel_id
    st.session_state["goto_page"] = "Travel"
    st.rerun()
