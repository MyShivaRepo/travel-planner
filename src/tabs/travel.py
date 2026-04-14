import streamlit as st
import streamlit.components.v1 as components
import folium

import database as db
from routing import get_route, format_duration, format_distance

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

    travel = db.get_travel(dest_id)
    if not travel:
        st.info(
            f"Aucun voyage planifié pour « {dest['nom']} ». "
            "Rendez-vous dans l'onglet « Destination » pour en générer un."
        )
        return

    days = travel["days"]
    transport_mode = travel["transport_mode"]

    st.markdown(
        f"**Voyage : {dest['nom']}** ({dest['type']}) — {len(days)} jours — "
        f"Transport : *{transport_mode}*"
    )

    sub_tab_table, sub_tab_map = st.tabs(["Tableau", "Carte"])

    with sub_tab_table:
        _render_table(days)

    with sub_tab_map:
        _render_map(days, transport_mode)


def _render_table(days):
    for day in days:
        with st.expander(f"Jour {day['numero']}", expanded=True):
            if day["pois"]:
                st.markdown("**Sites à visiter :**")
                for poi in day["pois"]:
                    st.markdown(f"- {poi['rang']}. **{poi['nom']}** ({poi['type']}) — {poi['description'] or ''}")
            else:
                st.markdown("*Aucun site prévu ce jour.*")

            st.markdown("---")

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


def _build_day_path(day, next_day=None):
    """
    Construit la liste ordonnée des étapes d'une journée :
    hôtel matin → POIs (ordre rang) → restaurant → hôtel suivant (ou même hôtel le dernier jour).
    Retourne une liste de tuples (type, nom, lat, lon).
    """
    path = []
    if day.get("hotel_latitude") and day.get("hotel_longitude"):
        path.append(("hotel_start", day.get("hotel_nom", "Hôtel"),
                     day["hotel_latitude"], day["hotel_longitude"]))

    for poi in day.get("pois", []):
        path.append(("poi", poi["nom"], poi["latitude"], poi["longitude"]))

    if day.get("restaurant_latitude") and day.get("restaurant_longitude"):
        path.append(("restaurant", day.get("restaurant_nom", "Restaurant"),
                     day["restaurant_latitude"], day["restaurant_longitude"]))

    # Retour à l'hôtel du soir (= hôtel du jour suivant si existe, sinon même hôtel)
    if next_day and next_day.get("hotel_latitude") and next_day.get("hotel_longitude"):
        path.append(("hotel_end", next_day.get("hotel_nom", "Hôtel"),
                     next_day["hotel_latitude"], next_day["hotel_longitude"]))
    elif day.get("hotel_latitude") and day.get("hotel_longitude"):
        path.append(("hotel_end", day.get("hotel_nom", "Hôtel"),
                     day["hotel_latitude"], day["hotel_longitude"]))

    return path


def _render_map(days, transport_mode):
    all_coords = []

    # Collecter toutes les coordonnées pour centrer la carte
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

    # Parcours complet par jour, segment par segment
    for i, day in enumerate(days):
        day_color = DAY_COLORS[i % len(DAY_COLORS)]
        next_day = days[i + 1] if i + 1 < len(days) else None
        path = _build_day_path(day, next_day)

        if len(path) < 2:
            continue

        # Router chaque segment individuellement (A → B)
        for j in range(len(path) - 1):
            seg_start = path[j]
            seg_end = path[j + 1]
            seg_coords = [(seg_start[2], seg_start[3]), (seg_end[2], seg_end[3])]

            route_data = get_route(seg_coords, transport_mode, ors_key) if ors_key else None

            if route_data:
                use_real_routing = True
                total_duration += route_data["duration"]
                total_distance += route_data["distance"]
                tooltip = (
                    f"Jour {day['numero']} : {seg_start[1]} → {seg_end[1]} — "
                    f"{format_distance(route_data['distance'])}, "
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
                # Fallback : ligne droite pour ce segment uniquement
                folium.PolyLine(
                    seg_coords,
                    color=day_color,
                    weight=3,
                    opacity=0.6,
                    dash_array="8",
                    tooltip=f"Jour {day['numero']} : {seg_start[1]} → {seg_end[1]} (ligne directe)",
                ).add_to(m)

    # Marqueurs (hôtels, restaurants, POIs)
    for day in days:
        jour_num = day["numero"]

        # Hôtel bleu avec icône lit
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

        # Restaurant vert avec icône fourchette
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

        # POIs en rouge avec numéro de rang
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
            f"Itinéraire total ({transport_mode}) : "
            f"{format_distance(total_distance)} — {format_duration(total_duration)}"
        )
    elif not ors_key:
        st.caption(
            "Tracés en lignes droites. Pour afficher les vrais itinéraires, "
            "configurez une clé OpenRouteService dans Settings."
        )
    elif transport_mode in ("train", "bateau", "transport public"):
        st.caption(
            f"Mode « {transport_mode} » non supporté par OpenRouteService — "
            f"affichage en lignes droites."
        )

    # Rendu carte plein viewport
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
