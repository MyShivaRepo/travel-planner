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

    # Sélection du fournisseur
    current_idx = provider_names.index(st.session_state["llm_provider"]) if st.session_state["llm_provider"] in provider_names else 0
    provider = st.selectbox(
        "Fournisseur LLM",
        provider_names,
        index=current_idx,
        key="provider_select",
    )

    # Clé API
    st.text_input(
        f"Clé API ({provider})",
        type="password",
        help=f"Votre clé API pour {provider}.",
        key="api_key_input",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Enregistrer", type="primary"):
            key = st.session_state["api_key_input"].strip()
            st.session_state["api_key"] = key
            st.session_state["llm_provider"] = provider
            db.set_setting("api_key", key)
            db.set_setting("llm_provider", provider)
            if key:
                st.success(f"Clé API enregistrée pour {provider}.")
            else:
                st.warning("Clé API effacée.")

    with col2:
        if st.button("Tester la clé"):
            key = st.session_state["api_key_input"].strip()
            if not key:
                st.warning("Veuillez saisir une clé API.")
            else:
                with st.spinner("Test de la clé API..."):
                    ok, msg = test_api_key(provider, key)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
