import streamlit as st
import streamlit.components.v1 as components
import folium

import database as db
from routing import get_route, format_duration, format_distance
from google_routing import get_transit_route, great_circle_route


# Modes routés par Google Maps Directions (transit)
TRANSIT_MODES = {"métro", "train"}

# Modes routés en great-circle (avion)
PLANE_MODES = {"avion"}

# Modes pour lesquels on laisse une ligne droite pointillée
STRAIGHT_LINE_MODES = {"bateau"}


def _get_segment_route(mode, coords, ors_key, gmaps_key):
    """Dispatche le calcul de route selon le mode de transport."""
    if mode in PLANE_MODES:
        return great_circle_route(coords), "great-circle"
    if mode in TRANSIT_MODES and gmaps_key:
        result = get_transit_route(coords, mode, gmaps_key)
        if result:
            return result, "transit"
        # Fallback ORS driving si Google Maps échoue
        if ors_key:
            return get_route(coords, mode, ors_key), "ors-fallback"
        return None, None
    if mode in STRAIGHT_LINE_MODES:
        return None, None
    if ors_key:
        return get_route(coords, mode, ors_key), "ors"
    return None, None

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

    # ── Chargement du voyage le plus récent ─────────────────────────────────
    travels_list = db.list_travels(dest_id)
    if not travels_list:
        st.info(
            f"Aucun voyage planifié pour « {dest['nom']} ». "
            "Rendez-vous dans l'onglet « Destination » pour en générer un."
        )
        return

    travel = db.get_travel_by_id(travels_list[0]["id"])
    if not travel:
        st.warning("Voyage introuvable.")
        return

    days = travel["days"]

    st.markdown(
        f"**{dest['nom']}** ({dest['type']}) — {len(days)} jours"
    )

    sub_tab_table, sub_tab_map = st.tabs(["Tableau", "Carte"])

    with sub_tab_table:
        _render_table(days)

    with sub_tab_map:
        _render_map(days)


def _render_table(days):
    for day in days:
        with st.expander(f"Jour {day['numero']}", expanded=True):
            # 1. Liste des sites à visiter (classés par rang)
            st.markdown("**Liste des sites à visiter** *(classés par leur Rang)*")
            if day["pois"]:
                sorted_pois = sorted(day["pois"], key=lambda p: p.get("rang", 999))
                for poi in sorted_pois:
                    st.markdown(f"- {poi['nom']} (rang {poi['rang']})")
            else:
                st.markdown("*Aucun site prévu ce jour.*")

            # 2. Liste des segments
            segments = day.get("segments", [])
            if segments:
                st.markdown("**Liste des segments**")
                for seg in segments:
                    c1, c2 = st.columns([5, 2])
                    with c1:
                        st.markdown(
                            f"- {seg['from_name']} > {seg['to_name']} :"
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

            # 3. Logistique du soir
            st.markdown("**Logistique du soir**")
            hotel_line = f"- **Hôtel** : {day.get('hotel_nom', 'Non défini')}"
            if day.get("hotel_adresse"):
                hotel_line += f" — {day['hotel_adresse']}"
            st.markdown(hotel_line)
            resto_line = f"- **Restaurant** : {day.get('restaurant_nom', 'Non défini')}"
            if day.get("restaurant_adresse"):
                resto_line += f" — {day['restaurant_adresse']}"
            st.markdown(resto_line)


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

    # Construire le dictionnaire : nom du point → label court (Jn / POIx / Resto Jn)
    name_to_label = {}
    for day in days:
        n = day["numero"]
        if day.get("hotel_nom"):
            name_to_label[day["hotel_nom"]] = f"J{n}"
        if day.get("restaurant_nom"):
            name_to_label[day["restaurant_nom"]] = f"Resto J{n}"
        for poi in day.get("pois", []):
            name_to_label[poi["nom"]] = f"POI{poi['rang']}"

    def _label(name):
        return name_to_label.get(name, name)

    ors_key = st.session_state.get("ors_api_key", "")
    gmaps_key = st.session_state.get("gmaps_api_key", "")
    total_duration = 0
    total_distance = 0
    use_real_routing = False

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

            from_label = _label(seg["from_name"])
            to_label = _label(seg["to_name"])

            route_data, source = _get_segment_route(seg_mode, seg_coords, ors_key, gmaps_key)

            if route_data:
                use_real_routing = True
                total_duration += route_data["duration"]
                total_distance += route_data["distance"]
                tooltip = (
                    f'From "{from_label}" to "{to_label}" : {seg_mode} '
                    f"({format_distance(route_data['distance'])}, "
                    f"{format_duration(route_data['duration'])})"
                )
                folium.PolyLine(
                    route_data["geometry"],
                    color=day_color,
                    weight=4,
                    opacity=0.8,
                    tooltip=tooltip,
                ).add_to(m)
            else:
                folium.PolyLine(
                    seg_coords,
                    color=day_color,
                    weight=3,
                    opacity=0.6,
                    dash_array="8",
                    tooltip=f'From "{from_label}" to "{to_label}" : {seg_mode} (ligne directe)',
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
