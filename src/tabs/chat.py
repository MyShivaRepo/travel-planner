import streamlit as st

from chat_agent import chat_turn


def render():
    st.header("💬 Chat")
    st.caption(
        "Décrivez votre voyage en langage naturel. L'assistant peut créer des destinations, "
        "ajouter/supprimer des POIs ou activités, et générer des voyages — les résultats "
        "apparaissent automatiquement dans les autres onglets."
    )

    from chat_agent import CHAT_MODELS

    llm_provider = st.session_state.get("llm_provider")
    llm_api_key = st.session_state.get("api_key", "")

    if llm_provider not in CHAT_MODELS:
        st.warning(
            f"Provider « {llm_provider} » non supporté par le chat. "
            f"Choisissez un provider dans Settings : {', '.join(CHAT_MODELS.keys())}."
        )
        return
    if not llm_api_key:
        st.warning("Configurez votre clé API dans l'onglet Settings.")
        return

    # ── États de session ─────────────────────────────────────────────────────
    # Reset automatique de l'historique si le provider change (les formats
    # natifs ne sont pas compatibles entre Anthropic / OpenAI / Google).
    if st.session_state.get("chat_provider") and st.session_state["chat_provider"] != llm_provider:
        st.info(
            f"Provider changé ({st.session_state['chat_provider']} → {llm_provider}) : "
            "historique de chat réinitialisé."
        )
        st.session_state["chat_history"] = []
        st.session_state["chat_agent_messages"] = []
    st.session_state["chat_provider"] = llm_provider

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []  # [(role, content_markdown)]
    if "chat_agent_messages" not in st.session_state:
        st.session_state["chat_agent_messages"] = []  # historique agent (format provider)

    # Indicateur du modèle utilisé
    st.caption(f"Modèle : `{CHAT_MODELS[llm_provider]}`")

    # ── Barre d'outils : reset ───────────────────────────────────────────────
    col_title, col_reset = st.columns([6, 1])
    with col_reset:
        if st.button("🗑️ Effacer", use_container_width=True, key="chat_reset"):
            st.session_state["chat_history"] = []
            st.session_state["chat_agent_messages"] = []
            st.rerun()

    # ── Message d'accueil si historique vide ─────────────────────────────────
    if not st.session_state["chat_history"]:
        with st.chat_message("assistant"):
            st.markdown(
                "Bonjour ! Je suis votre assistant de planification. Quelques exemples :\n\n"
                "- *« Je veux partir 5 jours au Japon, on aime la nature et la gastronomie »*\n"
                "- *« Ajoute un musée d'art moderne à Rome »*\n"
                "- *« Supprime le Mont Fuji du Japon »*\n"
                "- *« Planifie le voyage au Japon »*\n"
                "- *« Quelles destinations ai-je déjà enregistrées ? »*\n"
                "- *« Quelle est la meilleure saison pour la Toscane ? »*"
            )

    # ── Affichage de l'historique ────────────────────────────────────────────
    for entry in st.session_state["chat_history"]:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])

    # ── Input utilisateur ────────────────────────────────────────────────────
    user_input = st.chat_input("Parlez-moi de votre voyage…")
    if not user_input:
        return

    # Affichage immédiat du message utilisateur
    st.session_state["chat_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Appel de l'agent
    with st.chat_message("assistant"):
        with st.spinner("L'assistant réfléchit…"):
            try:
                reply, new_messages, tool_execs = chat_turn(
                    user_input,
                    st.session_state["chat_agent_messages"],
                    llm_provider,
                    llm_api_key,
                )
            except Exception as e:
                err_msg = f"❌ Erreur : {type(e).__name__} — {e}"
                st.error(err_msg)
                st.session_state["chat_history"].append({"role": "assistant", "content": err_msg})
                return

        # Résumé compact des tools exécutés
        if tool_execs:
            summary_lines = []
            for tname, _, tresult in tool_execs:
                icon = "✓" if tresult.get("success") else "✗"
                summary_lines.append(f"{icon} `{tname}`")
            summary = "*🔧 Actions : " + " • ".join(summary_lines) + "*"
            full_reply = f"{summary}\n\n{reply}"
        else:
            full_reply = reply

        st.markdown(full_reply)

    # Persistance
    st.session_state["chat_history"].append({"role": "assistant", "content": full_reply})
    st.session_state["chat_agent_messages"] = new_messages
    # Un rerun léger met à jour les autres onglets (ex: selected_destination_id)
    st.rerun()
