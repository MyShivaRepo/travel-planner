import streamlit as st

import database as db
from tabs import settings, where_to_go, destination, travel, chat

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Travel Planner",
    page_icon="🗺️",
    layout="wide",
)

# ── CSS : réduire les marges et masquer le menu Deploy ───────────────────────
st.markdown("""
    <style>
        .block-container { padding-top: 2.5rem !important; padding-bottom: 0rem !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 0px; }
        .stTabs [data-baseweb="tab"] { padding: 4px 16px; }
        /* Masquer le bouton « Deploy » natif de Streamlit (inutile en auto-hébergement Docker) */
        [data-testid="stAppDeployButton"] { display: none !important; }
        /* Masquer le menu hamburger et la décoration du header */
        [data-testid="stMainMenu"] { display: none !important; }
        header[data-testid="stHeader"] [data-testid="stDecoration"] { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# ── Initialisation base de données ───────────────────────────────────────────
db.init_db()

# ── Charger les settings depuis la DB au démarrage ──────────────────────────
if "api_key" not in st.session_state:
    saved_key = db.get_setting("api_key")
    st.session_state["api_key"] = saved_key or ""
if "llm_provider" not in st.session_state:
    saved_provider = db.get_setting("llm_provider")
    st.session_state["llm_provider"] = saved_provider or "Anthropic / Claude"
if "fallback_provider" not in st.session_state:
    st.session_state["fallback_provider"] = db.get_setting("fallback_provider") or ""
if "fallback_api_key" not in st.session_state:
    st.session_state["fallback_api_key"] = db.get_setting("fallback_api_key") or ""
if "ors_api_key" not in st.session_state:
    st.session_state["ors_api_key"] = db.get_setting("ors_api_key") or ""
if "gmaps_api_key" not in st.session_state:
    st.session_state["gmaps_api_key"] = db.get_setting("gmaps_api_key") or ""

# ── Navigation horizontale compacte ──────────────────────────────────────────
PAGES = ["Settings", "Where to Go", "Destination", "Travel", "💬 Chat"]

if "goto_page" in st.session_state:
    st.session_state["nav_radio"] = st.session_state.pop("goto_page")
if "nav_radio" not in st.session_state:
    st.session_state["nav_radio"] = "Where to Go"

# Titre + navigation sur une seule ligne
col_title, col_nav = st.columns([1, 3])
with col_title:
    st.markdown("#### 🗺️ Travel Planner")
with col_nav:
    current = st.radio(
        "Navigation",
        PAGES,
        horizontal=True,
        label_visibility="collapsed",
        key="nav_radio",
    )

st.session_state["current_page"] = current

# ── Rendu de la page active ──────────────────────────────────────────────────
if current == "Settings":
    settings.render()
elif current == "Where to Go":
    where_to_go.render()
elif current == "Destination":
    destination.render()
elif current == "Travel":
    travel.render()
elif current == "💬 Chat":
    chat.render()
