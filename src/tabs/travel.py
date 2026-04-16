import streamlit as st
import streamlit.components.v1 as components
import folium

import pandas as pd

import database as db
from routing import get_route, format_duration, format_distance, compute_segment_metrics
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

TRANSPORT_MODES = [
    "à pied", "en vélo",
    "voiture personnelle", "voiture de location", "taxi",
    "bus", "métro", "train", "bateau", "avion",
]

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
    ors_key = st.session_state.get("ors_api_key", "")
    gmaps_key = st.session_state.get("gmaps_api_key", "")

    for day in days:
        segments = day.get("segments", [])

        # Agrégats du jour
        total_dist = sum((s.get("distance_km") or 0) for s in segments)
        total_dur = sum((s.get("duration_h") or 0) for s in segments)
        total_budget = sum((s.get("budget") or 0) for s in segments)
        total_budget += (day.get("hotel_budget") or 0) + (day.get("restaurant_budget") or 0)

        header = (
            f"Jour {day['numero']} — {format_distance(total_dist)} — "
            f"{format_duration(total_dur)} — {total_budget:.0f} €"
        )

        with st.expander(header, expanded=True):
            # 1. Liste des POIs à visiter (classés par rang)
            st.markdown("**Liste des POIs à visiter** *(classés par leur Rang)*")
            if day["pois"]:
                sorted_pois = sorted(day["pois"], key=lambda p: p.get("rang", 999))
                for poi in sorted_pois:
                    st.markdown(f"- {poi['nom']} (rang {poi['rang']})")
            else:
                st.markdown("*Aucun POI prévu ce jour.*")

            # 2. Liste des Activités à réaliser (classées par rang)
            st.markdown("**Liste des Activités à réaliser** *(classées par leur Rang)*")
            activities = day.get("activities", [])
            if activities:
                sorted_acts = sorted(activities, key=lambda a: a.get("rang", 999))
                for act in sorted_acts:
                    st.markdown(f"- {act['nom']} (rang {act['rang']})")
            else:
                st.markdown("*Aucune activité prévue ce jour.*")

            # 3. Liste des segments (tableau avec édition du mode inline)
            if segments:
                st.markdown("**Liste des segments**")
                # En-têtes
                h1, h2, h3, h4, h5 = st.columns([3, 2, 1.2, 1.2, 1])
                h1.markdown("**From > To**")
                h2.markdown("**Mode**")
                h3.markdown("**Distance**")
                h4.markdown("**Durée**")
                h5.markdown("**Budget**")

                for seg in segments:
                    c1, c2, c3, c4, c5 = st.columns([3, 2, 1.2, 1.2, 1])
                    c1.write(f"{seg['from_name']} > {seg['to_name']}")
                    current_mode = seg.get("transport_mode", "voiture")
                    idx = TRANSPORT_MODES.index(current_mode) if current_mode in TRANSPORT_MODES else 2
                    with c2:
                        new_mode = st.selectbox(
                            "Mode",
                            TRANSPORT_MODES,
                            index=idx,
                            key=f"seg_mode_{seg['id']}",
                            label_visibility="collapsed",
                        )
                    c3.write(format_distance(seg.get("distance_km") or 0))
                    c4.write(format_duration(seg.get("duration_h") or 0))
                    budget_val = seg.get("budget")
                    c5.write(f"{budget_val:.0f} €" if budget_val is not None else "—")

                    # Recalculer distance/durée si le mode a changé
                    if new_mode != current_mode:
                        if (seg.get("from_latitude") and seg.get("from_longitude")
                                and seg.get("to_latitude") and seg.get("to_longitude")):
                            new_dist, new_dur = compute_segment_metrics(
                                new_mode,
                                [(seg["from_latitude"], seg["from_longitude"]),
                                 (seg["to_latitude"], seg["to_longitude"])],
                                ors_key, gmaps_key,
                            )
                        else:
                            new_dist, new_dur = None, None
                        db.update_segment_mode(seg["id"], new_mode, new_dist, new_dur)
                        st.rerun()

            # 3. Logistique du soir
            st.markdown("**Logistique du soir**")
            hotel_line = f"- **Hôtel** : {day.get('hotel_nom', 'Non défini')}"
            if day.get("hotel_adresse"):
                hotel_line += f" — {day['hotel_adresse']}"
            if day.get("hotel_budget"):
                hotel_line += f" — **{day['hotel_budget']:.0f} €** / nuit"
            st.markdown(hotel_line)
            resto_line = f"- **Restaurant** : {day.get('restaurant_nom', 'Non défini')}"
            if day.get("restaurant_adresse"):
                resto_line += f" — {day['restaurant_adresse']}"
            if day.get("restaurant_budget"):
                resto_line += f" — **{day['restaurant_budget']:.0f} €** / personne"
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
        for act in day.get("activities", []):
            all_coords.append((act["latitude"], act["longitude"]))

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

    # Construire le dictionnaire : nom du point → label court (Jn / POIx / Actx / Resto Jn)
    name_to_label = {}
    for day in days:
        n = day["numero"]
        if day.get("hotel_nom"):
            name_to_label[day["hotel_nom"]] = f"J{n}"
        if day.get("restaurant_nom"):
            name_to_label[day["restaurant_nom"]] = f"Resto J{n}"
        for poi in day.get("pois", []):
            name_to_label[poi["nom"]] = f"POI{poi['rang']}"
        for act in day.get("activities", []):
            name_to_label[act["nom"]] = f"Act{act['rang']}"

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
                # route_data vient des APIs de routage : distance en mètres, durée en secondes
                dist_km = route_data["distance"] / 1000.0
                dur_h = route_data["duration"] / 3600.0
                total_duration += dur_h
                total_distance += dist_km
                tooltip = (
                    f'From "{from_label}" to "{to_label}" : {seg_mode} '
                    f"({format_distance(dist_km)}, {format_duration(dur_h)})"
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
                tooltip=f"J{jour_num} — POI{poi['rang']} {poi['nom']}",
                icon=folium.DivIcon(
                    html=f'<div style="background-color:red;color:white;border-radius:50%;'
                         f'width:24px;height:24px;text-align:center;line-height:24px;'
                         f'font-size:12px;font-weight:bold;border:2px solid darkred;">'
                         f'{poi["rang"]}</div>',
                    icon_size=(24, 24),
                    icon_anchor=(12, 12),
                ),
            ).add_to(m)

        # Activités orange numérotées
        for act in day.get("activities", []):
            folium.Marker(
                location=[act["latitude"], act["longitude"]],
                popup=folium.Popup(
                    f"<b>Jour {jour_num} — {act['nom']}</b><br>"
                    f"<i>{act['type']}</i><br>"
                    f"{act.get('description', '') or ''}",
                    max_width=300,
                ),
                tooltip=f"J{jour_num} — Act{act['rang']} {act['nom']}",
                icon=folium.DivIcon(
                    html=f'<div style="background-color:orange;color:white;border-radius:50%;'
                         f'width:24px;height:24px;text-align:center;line-height:24px;'
                         f'font-size:12px;font-weight:bold;border:2px solid #cc8400;">'
                         f'{act["rang"]}</div>',
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
