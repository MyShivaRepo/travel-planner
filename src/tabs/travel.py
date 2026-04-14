import streamlit as st
import streamlit.components.v1 as components
import folium

import database as db
from routing import get_route, format_duration, format_distance

TRANSPORT_MODES = ["à pied", "en vélo", "voiture", "train", "bus", "bateau"]

# Couleurs par jour pour distinguer les trajectoires
DAY_COLORS = ["blue", "red", "green", "purple", "orange", "darkred", "darkblue",
              "darkgreen", "cadetblue", "pink", "gray", "black"]


def render():
    dest_id = st.session_state.get("selected_destination_id")
    if not dest_id:
        st.info("Sélectionnez une destination et générez un voyage depuis l'onglet « Destination ».")
        return

    dest = db.get_destination(dest_id)
    if not dest:
        st.warning("Destination introuvable.")
        return

    # ── Liste des voyages pour cette destination ────────────────────────────
    travels_list = db.list_travels(dest_id)
    if not travels_list:
        st.info(
            f"Aucun voyage planifié pour « {dest['nom']} ». "
            "Rendez-vous dans l'onglet « Destination » pour en générer un."
        )
        return

    # Déterminer le voyage sélectionné
    selected_id = st.session_state.get("selected_travel_id")
    ids = [t["id"] for t in travels_list]
    if selected_id not in ids:
        selected_id = ids[0]  # plus récent
        st.session_state["selected_travel_id"] = selected_id

    # ── Sélecteur de voyage + actions ────────────────────────────────────────
    def _label(t):
        date = (t.get("created_at") or "")[:16].replace("T", " ")
        base = t.get("nom") or f"Voyage #{t['id']}"
        return f"{base} — {t['transport_mode']} — {date}"

    col_sel, col_del = st.columns([5, 1])
    with col_sel:
        choice = st.selectbox(
            "Voyage",
            travels_list,
            index=ids.index(selected_id),
            format_func=_label,
            key="travel_selector",
            label_visibility="collapsed",
        )
        if choice["id"] != selected_id:
            st.session_state["selected_travel_id"] = choice["id"]
            st.rerun()
    with col_del:
        if st.button("Supprimer", key="del_travel"):
            db.delete_travel(selected_id)
            st.session_state.pop("selected_travel_id", None)
            st.rerun()

    # ── Chargement du voyage sélectionné ────────────────────────────────────
    travel = db.get_travel_by_id(selected_id)
    if not travel:
        st.warning("Voyage introuvable.")
        return

    days = travel["days"]
    transport_mode = travel["transport_mode"]

    st.markdown(
        f"**{dest['nom']}** ({dest['type']}) — {len(days)} jours — "
        f"Mode préféré : *{transport_mode}*"
    )

    sub_tab_table, sub_tab_map = st.tabs(["Tableau", "Carte"])

    with sub_tab_table:
        _render_table(days)

    with sub_tab_map:
        _render_map(days)


def _render_table(days):
    for day in days:
        with st.expander(f"Jour {day['numero']}", expanded=True):
            if day["pois"]:
                st.markdown("**Sites à visiter :**")
                for poi in day["pois"]:
                    st.markdown(f"- {poi['rang']}. **{poi['nom']}** ({poi['type']}) — {poi['description'] or ''}")
            else:
                st.markdown("*Aucun site prévu ce jour.*")

            col_hotel, col_resto = st.columns(2)
            with col_hotel:
                st.markdown("**Hôtel**")
                st.markdown(f"{day.get('hotel_nom', 'Non défini')}")
                if day.get("hotel_adresse"):
                    st.caption(day["hotel_adresse"])
            with col_resto:
                st.markdown("**Restaurant**")
                st.markdown(f"{day.get('restaurant_nom', 'Non défini')}")
                if day.get("restaurant_adresse"):
                    st.caption(day["restaurant_adresse"])

            # ── Segments ─────────────────────────────────────────────────────
            segments = day.get("segments", [])
            if segments:
                st.markdown("**Trajets (segments) :**")
                for seg in segments:
                    c1, c2 = st.columns([4, 2])
                    with c1:
                        st.markdown(
                            f"- **{seg['from_name']}** → **{seg['to_name']}**"
                        )
                    with c2:
                        current_mode = seg.get("transport_mode", "voiture")
                        idx = TRANSPORT_MODES.index(current_mode) if current_mode in TRANSPORT_MODES else 2
                        new_mode = st.selectbox(
                            "Mode",
                            TRANSPORT_MODES,
                            index=idx,
                            key=f"seg_mode_{seg['id']}",
                            label_visibility="collapsed",
                        )
                        if new_mode != current_mode:
                            db.update_segment_mode(seg["id"], new_mode)
                            st.rerun()


def _render_map(days):
    all_coords = []
    for day in days:
        if day.get("hotel_latitude") and day.get("hotel_longitude"):
            all_coords.append((day["hotel_latitude"], day["hotel_longitude"]))
        if day.get("restaurant_latitude") and day.get("restaurant_longitude"):
            all_coords.append((day["restaurant_latitude"], day["restaurant_longitude"]))
        for poi in day.get("pois", []):
            all_coords.append((poi["latitude"], poi["longitude"]))

    if not all_coords:
        st.warning(
            "Les coordonnées GPS ne sont pas disponibles. "
            "Regénérez le voyage pour obtenir la carte d'itinéraire."
        )
        return

    all_lats = [c[0] for c in all_coords]
    all_lons = [c[1] for c in all_coords]
    center_lat = sum(all_lats) / len(all_lats)
    center_lon = sum(all_lons) / len(all_lons)
    zoom = _zoom_from_span(max(max(all_lats) - min(all_lats), max(all_lons) - min(all_lons)))

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom)

    ors_key = st.session_state.get("ors_api_key", "")
    total_duration = 0
    total_distance = 0
    use_real_routing = False
    has_unsupported_mode = False

    # Tracer chaque segment selon SON mode de transport
    for i, day in enumerate(days):
        day_color = DAY_COLORS[i % len(DAY_COLORS)]
        for seg in day.get("segments", []):
            if not (seg.get("from_latitude") and seg.get("from_longitude")
                    and seg.get("to_latitude") and seg.get("to_longitude")):
                continue

            seg_coords = [(seg["from_latitude"], seg["from_longitude"]),
                          (seg["to_latitude"], seg["to_longitude"])]
            seg_mode = seg.get("transport_mode", "voiture")

            route_data = get_route(seg_coords, seg_mode, ors_key) if ors_key else None

            if route_data:
                use_real_routing = True
                total_duration += route_data["duration"]
                total_distance += route_data["distance"]
                tooltip = (
                    f"J{day['numero']} : {seg['from_name']} → {seg['to_name']} — "
                    f"{seg_mode} — {format_distance(route_data['distance'])}, "
                    f"{format_duration(route_data['duration'])}"
                )
                folium.PolyLine(
                    route_data["geometry"],
                    color=day_color,
                    weight=4,
                    opacity=0.8,
                    tooltip=tooltip,
                ).add_to(m)
            else:
                if seg_mode in ("train", "bateau"):
                    has_unsupported_mode = True
                folium.PolyLine(
                    seg_coords,
                    color=day_color,
                    weight=3,
                    opacity=0.6,
                    dash_array="8",
                    tooltip=f"J{day['numero']} : {seg['from_name']} → {seg['to_name']} — {seg_mode} (ligne directe)",
                ).add_to(m)

    # Marqueurs
    for day in days:
        jour_num = day["numero"]

        # Hôtel bleu
        if day.get("hotel_latitude") and day.get("hotel_longitude"):
            folium.Marker(
                location=[day["hotel_latitude"], day["hotel_longitude"]],
                popup=folium.Popup(
                    f"<b>Jour {jour_num} — Hôtel</b><br>"
                    f"<b>{day.get('hotel_nom', '')}</b><br>"
                    f"<i>{day.get('hotel_adresse', '')}</i>",
                    max_width=300,
                ),
                tooltip=f"J{jour_num} — {day.get('hotel_nom', 'Hôtel')}",
                icon=folium.Icon(color="blue", icon="bed", prefix="fa"),
            ).add_to(m)

        # Restaurant vert
        if day.get("restaurant_latitude") and day.get("restaurant_longitude"):
            folium.Marker(
                location=[day["restaurant_latitude"], day["restaurant_longitude"]],
                popup=folium.Popup(
                    f"<b>Jour {jour_num} — Restaurant</b><br>"
                    f"<b>{day.get('restaurant_nom', '')}</b><br>"
                    f"<i>{day.get('restaurant_adresse', '')}</i>",
                    max_width=300,
                ),
                tooltip=f"J{jour_num} — {day.get('restaurant_nom', 'Restaurant')}",
                icon=folium.Icon(color="green", icon="cutlery", prefix="fa"),
            ).add_to(m)

        # POIs rouges numérotés
        for poi in day.get("pois", []):
            folium.Marker(
                location=[poi["latitude"], poi["longitude"]],
                popup=folium.Popup(
                    f"<b>Jour {jour_num} — {poi['nom']}</b><br>"
                    f"<i>{poi['type']}</i><br>"
                    f"{poi.get('description', '')}",
                    max_width=300,
                ),
                tooltip=f"J{jour_num} — {poi['nom']}",
                icon=folium.DivIcon(
                    html=f'<div style="background-color:red;color:white;border-radius:50%;'
                         f'width:24px;height:24px;text-align:center;line-height:24px;'
                         f'font-size:12px;font-weight:bold;border:2px solid darkred;">'
                         f'{poi["rang"]}</div>',
                    icon_size=(24, 24),
                    icon_anchor=(12, 12),
                ),
            ).add_to(m)

    # Infos globales
    if use_real_routing and total_distance > 0:
        st.caption(
            f"Itinéraire réel (segments routables) : "
            f"{format_distance(total_distance)} — {format_duration(total_duration)}"
        )
    if has_unsupported_mode:
        st.caption(
            "Les segments en *train* ou *bateau* ne sont pas routables via OpenRouteService → "
            "affichés en lignes droites."
        )
    if not ors_key:
        st.caption(
            "Aucune clé OpenRouteService configurée → tracés en lignes droites. "
            "Configurez une clé dans Settings pour afficher les vrais itinéraires."
        )

    map_html = m._repr_html_()
    fullscreen_html = f"""
    <style>
        html, body {{ margin: 0; padding: 0; height: 100%; overflow: hidden; }}
        .folium-map {{ width: 100% !important; height: 100% !important; }}
    </style>
    {map_html}
    """
    components.html(fullscreen_html, height=2000, scrolling=False)

    st.markdown("""
        <style>
            .stTabs [data-baseweb="tab-panel"] iframe {
                height: calc(100vh - 200px) !important;
                min-height: 300px;
            }
        </style>
    """, unsafe_allow_html=True)


def _zoom_from_span(span):
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
