import streamlit as st

import database as db
from tabs import settings, where_to_go, destination, travel

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Travel Planner",
    page_icon="🗺️",
    layout="wide",
)

# ── Initialisation base de données ───────────────────────────────────────────
db.init_db()

# ── Charger les settings depuis la DB au démarrage ──────────────────────────
if "api_key" not in st.session_state:
    saved_key = db.get_setting("api_key")
    st.session_state["api_key"] = saved_key or ""
if "llm_provider" not in st.session_state:
    saved_provider = db.get_setting("llm_provider")
    st.session_state["llm_provider"] = saved_provider or "Anthropic / Claude"

# ── Navigation horizontale ───────────────────────────────────────────────────
st.title("🗺️ Travel Planner")

PAGES = ["Settings", "Where to Go", "Destination", "Travel"]

# Navigation programmatique : si un bouton a demandé un changement de page
if "goto_page" in st.session_state:
    st.session_state["nav_radio"] = st.session_state.pop("goto_page")

# Initialiser nav_radio si pas encore défini
if "nav_radio" not in st.session_state:
    st.session_state["nav_radio"] = "Where to Go"

current = st.radio(
    "Navigation",
    PAGES,
    horizontal=True,
    label_visibility="collapsed",
    key="nav_radio",
)

st.divider()

# ── Rendu de la page active ──────────────────────────────────────────────────
if current == "Settings":
    settings.render()
elif current == "Where to Go":
    where_to_go.render()
elif current == "Destination":
    destination.render()
elif current == "Travel":
    travel.render()
