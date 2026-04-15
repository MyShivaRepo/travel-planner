import streamlit as st

import database as db
from llm_api import PROVIDERS, test_api_key


def render():
    st.header("Paramètres")

    provider_names = list(PROVIDERS.keys())

    # Charger les settings depuis la DB au premier affichage
    if "llm_provider" not in st.session_state:
        saved_provider = db.get_setting("llm_provider")
        st.session_state["llm_provider"] = saved_provider if saved_provider in provider_names else provider_names[0]
    if "api_key" not in st.session_state:
        saved_key = db.get_setting("api_key")
        st.session_state["api_key"] = saved_key or ""
    if "api_key_input" not in st.session_state:
        st.session_state["api_key_input"] = st.session_state["api_key"]

    # Fallback
    if "fallback_provider" not in st.session_state:
        saved_fb = db.get_setting("fallback_provider")
        st.session_state["fallback_provider"] = saved_fb if saved_fb in provider_names else ""
    if "fallback_api_key" not in st.session_state:
        saved_fb_key = db.get_setting("fallback_api_key")
        st.session_state["fallback_api_key"] = saved_fb_key or ""
    if "fallback_key_input" not in st.session_state:
        st.session_state["fallback_key_input"] = st.session_state["fallback_api_key"]

    # ── LLM Principal ────────────────────────────────────────────────────────
    st.subheader("LLM Principal")

    current_idx = provider_names.index(st.session_state["llm_provider"]) if st.session_state["llm_provider"] in provider_names else 0
    provider = st.selectbox(
        "Fournisseur",
        provider_names,
        index=current_idx,
        key="provider_select",
    )

    st.text_input(
        f"Clé API ({provider})",
        type="password",
        key="api_key_input",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Enregistrer", type="primary", key="save_primary"):
            key = st.session_state["api_key_input"].strip()
            st.session_state["api_key"] = key
            st.session_state["llm_provider"] = provider
            db.set_setting("api_key", key)
            db.set_setting("llm_provider", provider)
            st.success(f"LLM principal enregistré : {provider}")
    with col2:
        if st.button("Tester", key="test_primary"):
            key = st.session_state["api_key_input"].strip()
            if not key:
                st.warning("Veuillez saisir une clé API.")
            else:
                with st.spinner("Test..."):
                    ok, msg = test_api_key(provider, key)
                st.success(msg) if ok else st.error(msg)

    # ── LLM de Secours ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("LLM de Secours (fallback)")
    st.caption("Utilisé automatiquement si le LLM principal est indisponible (surcharge, timeout, erreur réseau).")

    fb_options = ["Aucun"] + provider_names
    current_fb = st.session_state.get("fallback_provider", "")
    fb_idx = fb_options.index(current_fb) if current_fb in fb_options else 0

    fb_provider = st.selectbox(
        "Fournisseur de secours",
        fb_options,
        index=fb_idx,
        key="fb_provider_select",
    )

    if fb_provider != "Aucun":
        st.text_input(
            f"Clé API ({fb_provider})",
            type="password",
            key="fallback_key_input",
        )

        col3, col4 = st.columns(2)
        with col3:
            if st.button("Enregistrer", type="primary", key="save_fallback"):
                fb_key = st.session_state["fallback_key_input"].strip()
                st.session_state["fallback_provider"] = fb_provider
                st.session_state["fallback_api_key"] = fb_key
                db.set_setting("fallback_provider", fb_provider)
                db.set_setting("fallback_api_key", fb_key)
                st.success(f"LLM de secours enregistré : {fb_provider}")
        with col4:
            if st.button("Tester", key="test_fallback"):
                fb_key = st.session_state["fallback_key_input"].strip()
                if not fb_key:
                    st.warning("Veuillez saisir une clé API.")
                else:
                    with st.spinner("Test..."):
                        ok, msg = test_api_key(fb_provider, fb_key)
                    st.success(msg) if ok else st.error(msg)
    else:
        # Effacer le fallback si "Aucun" est sélectionné
        if st.session_state.get("fallback_provider"):
            st.session_state["fallback_provider"] = ""
            st.session_state["fallback_api_key"] = ""
            db.set_setting("fallback_provider", "")
            db.set_setting("fallback_api_key", "")

    # ── API de routage (OpenRouteService) ────────────────────────────────────
    st.divider()
    st.subheader("API de routage (OpenRouteService)")
    st.caption(
        "Clé API optionnelle d'OpenRouteService pour calculer les vrais tracés routiers "
        "(à pied, vélo, voiture). Gratuit sur openrouteservice.org (2000 req/jour). "
        "Si vide, la carte affichera des lignes droites."
    )

    if "ors_api_key" not in st.session_state:
        st.session_state["ors_api_key"] = db.get_setting("ors_api_key") or ""
    if "ors_key_input" not in st.session_state:
        st.session_state["ors_key_input"] = st.session_state["ors_api_key"]

    st.text_input(
        "Clé API OpenRouteService",
        type="password",
        key="ors_key_input",
    )

    col_ors_save, col_ors_test = st.columns(2)
    with col_ors_save:
        if st.button("Enregistrer", type="primary", key="save_ors"):
            ors_key = st.session_state["ors_key_input"].strip()
            st.session_state["ors_api_key"] = ors_key
            db.set_setting("ors_api_key", ors_key)
            st.success("Clé ORS enregistrée." if ors_key else "Clé ORS effacée.")
    with col_ors_test:
        if st.button("Tester", key="test_ors"):
            ors_key = st.session_state["ors_key_input"].strip()
            if not ors_key:
                st.warning("Veuillez saisir une clé API.")
            else:
                from routing import get_route
                with st.spinner("Test de la clé ORS..."):
                    # Petit test : route Paris → Versailles à pied
                    test_coords = [(48.8566, 2.3522), (48.8049, 2.1204)]
                    result = get_route(test_coords, "à pied", ors_key)
                if result:
                    st.success("Clé ORS valide.")
                else:
                    st.error("Clé ORS invalide ou erreur API.")

    # ── API Google Maps Directions (transit : métro / train / bus) ───────────
    st.divider()
    st.subheader("API Google Maps Directions")
    st.caption(
        "Clé API Google Maps optionnelle pour calculer les itinéraires en transports publics "
        "(métro, train, bus) avec horaires réels. "
        "Activez l'API « Directions » sur console.cloud.google.com. "
        "Si vide, les segments métro/train suivront un tracé routier approximatif."
    )

    if "gmaps_api_key" not in st.session_state:
        st.session_state["gmaps_api_key"] = db.get_setting("gmaps_api_key") or ""
    if "gmaps_key_input" not in st.session_state:
        st.session_state["gmaps_key_input"] = st.session_state["gmaps_api_key"]

    st.text_input(
        "Clé API Google Maps",
        type="password",
        key="gmaps_key_input",
    )

    col_gm_save, col_gm_test = st.columns(2)
    with col_gm_save:
        if st.button("Enregistrer", type="primary", key="save_gmaps"):
            gm_key = st.session_state["gmaps_key_input"].strip()
            st.session_state["gmaps_api_key"] = gm_key
            db.set_setting("gmaps_api_key", gm_key)
            st.success("Clé Google Maps enregistrée." if gm_key else "Clé Google Maps effacée.")
    with col_gm_test:
        if st.button("Tester", key="test_gmaps"):
            gm_key = st.session_state["gmaps_key_input"].strip()
            if not gm_key:
                st.warning("Veuillez saisir une clé API.")
            else:
                from google_routing import test_gmaps_key
                with st.spinner("Test de la clé Google Maps..."):
                    ok, msg = test_gmaps_key(gm_key)
                st.success(msg) if ok else st.error(msg)
