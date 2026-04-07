import json
import os

import anthropic
import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Préparation de Voyage – POI Finder",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ Préparation de Voyage – Points d'Intérêt")
st.markdown(
    "Entrez une destination et le nombre de sites incontournables souhaités. "
    "L'application génère la liste avec coordonnées GPS et une carte interactive."
)

# ── Session state init ────────────────────────────────────────────────────────
if "pois" not in st.session_state:
    st.session_state.pois = None
if "dest_label" not in st.session_state:
    st.session_state.dest_label = ""

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Paramètres")
    destination = st.text_input(
        "Destination",
        placeholder="ex : Paris, Provence, Japon…",
    )
    nb_pois = st.slider("Nombre de POI", min_value=3, max_value=20, value=8)
    api_key = st.text_input(
        "Clé API Anthropic (optionnel)",
        type="password",
        help="Laissez vide pour utiliser la variable d'environnement ANTHROPIC_API_KEY",
    )
    go = st.button("🔍 Générer les POI", type="primary", use_container_width=True)

    if st.session_state.pois:
        st.divider()
        st.success(
            f"**{st.session_state.dest_label}**\n\n"
            f"{len(st.session_state.pois)} POI générés"
        )
        if st.button("🗑️ Effacer les résultats", use_container_width=True):
            st.session_state.pois = None
            st.session_state.dest_label = ""
            st.rerun()

# ── Structured-output schema ──────────────────────────────────────────────────
POI_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "destination_label": {
                "type": "string",
                "description": "Nom complet et formaté de la destination",
            },
            "pois": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rank": {
                            "type": "integer",
                            "description": "Rang du site (1 = le plus incontournable)",
                        },
                        "name": {"type": "string", "description": "Nom du site"},
                        "category": {
                            "type": "string",
                            "description": "Catégorie (Monument, Musée, Nature, Gastronomie, etc.)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Description courte en 1-2 phrases",
                        },
                        "latitude": {
                            "type": "number",
                            "description": "Latitude décimale WGS84",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Longitude décimale WGS84",
                        },
                        "address": {
                            "type": "string",
                            "description": "Adresse ou localisation approximative",
                        },
                    },
                    "required": [
                        "rank",
                        "name",
                        "category",
                        "description",
                        "latitude",
                        "longitude",
                        "address",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["destination_label", "pois"],
        "additionalProperties": False,
    },
}

# ── Category → colour mapping for map markers ─────────────────────────────────
CATEGORY_COLORS = {
    "Monument": "red",
    "Musée": "blue",
    "Nature": "green",
    "Gastronomie": "orange",
    "Plage": "cadetblue",
    "Parc": "darkgreen",
    "Château": "darkred",
    "Église": "purple",
    "Marché": "beige",
    "Sport": "darkblue",
}

DEFAULT_COLOR = "gray"


def get_marker_color(category: str) -> str:
    for key, color in CATEGORY_COLORS.items():
        if key.lower() in category.lower():
            return color
    return DEFAULT_COLOR


def compute_zoom(lat_min, lat_max, lon_min, lon_max) -> int:
    """Calcule le niveau de zoom Leaflet adapté à l'étendue géographique des POI."""
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


# ── API call (only when button clicked) ──────────────────────────────────────
if go:
    if not destination.strip():
        st.warning("Veuillez saisir une destination.")
        st.stop()

    key = api_key.strip() or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        st.error(
            "Clé API introuvable. Renseignez-la dans la barre latérale "
            "ou définissez la variable d'environnement `ANTHROPIC_API_KEY`."
        )
        st.stop()

    client = anthropic.Anthropic(api_key=key)

    with st.spinner(f"Recherche des {nb_pois} POI pour « {destination} »…"):
        try:
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                system=(
                    "Tu es un expert en voyages et tourisme. "
                    "Réponds uniquement en JSON valide, sans texte supplémentaire."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Liste les {nb_pois} sites touristiques incontournables "
                            f"de « {destination} ». "
                            "Pour chaque site fournis : rang, nom, catégorie, description courte, "
                            "latitude et longitude précises (WGS84), adresse ou localisation. "
                            "Trie du plus emblématique au moins emblématique."
                        ),
                    }
                ],
                output_config={"format": POI_SCHEMA},
            )
        except anthropic.APIError as exc:
            st.error(f"Erreur API Anthropic : {exc}")
            st.stop()

    raw_text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        st.error("La réponse de Claude n'est pas un JSON valide.")
        st.code(raw_text)
        st.stop()

    pois = data.get("pois", [])
    if not pois:
        st.warning("Aucun POI retourné. Essayez une autre destination.")
        st.stop()

    # ── Persist in session state so reruns keep the results ──────────────────
    st.session_state.pois = pois
    st.session_state.dest_label = data.get("destination_label", destination)

# ── Display results (from session state — survives reruns) ────────────────────
if st.session_state.pois:
    pois = st.session_state.pois
    dest_label = st.session_state.dest_label

    tab_table, tab_map = st.tabs(["📋 Tableau des POI", "🗺️ Carte interactive"])

    # ── Table ─────────────────────────────────────────────────────────────────
    with tab_table:
        df = pd.DataFrame(pois)[
            ["rank", "name", "category", "description", "latitude", "longitude", "address"]
        ].rename(
            columns={
                "rank": "#",
                "name": "Site",
                "category": "Catégorie",
                "description": "Description",
                "latitude": "Latitude",
                "longitude": "Longitude",
                "address": "Adresse",
            }
        )
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn(width="small"),
                "Latitude": st.column_config.NumberColumn(format="%.5f"),
                "Longitude": st.column_config.NumberColumn(format="%.5f"),
            },
        )

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Télécharger CSV",
            data=csv,
            file_name=f"pois_{dest_label.replace(' ', '_')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # ── Map ───────────────────────────────────────────────────────────────────
    with tab_map:

        lats = [p["latitude"]  for p in pois]
        lons = [p["longitude"] for p in pois]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        zoom = compute_zoom(min(lats), max(lats), min(lons), max(lons))

        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom)

        for poi in pois:
            color = get_marker_color(poi["category"])
            popup_html = (
                f"<b>{poi['rank']}. {poi['name']}</b><br>"
                f"<i>{poi['category']}</i><br>"
                f"{poi['description']}<br>"
                f"<small>{poi['address']}</small>"
            )
            folium.Marker(
                location=[poi["latitude"], poi["longitude"]],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"{poi['rank']}. {poi['name']}",
                icon=folium.Icon(color=color, icon="info-sign"),
            ).add_to(m)

        components.html(m._repr_html_(), height=600, scrolling=False)
