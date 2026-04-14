import streamlit as st

import database as db


def render():
    st.header("Travel")

    dest_id = st.session_state.get("selected_destination_id")
    if not dest_id:
        st.info("Sélectionnez une destination et générez un voyage depuis l'onglet « Destination ».")
        return

    dest = db.get_destination(dest_id)
    if not dest:
        st.warning("Destination introuvable.")
        return

    days = db.get_travel(dest_id)
    if not days:
        st.info(
            f"Aucun voyage planifié pour « {dest['nom']} ». "
            "Rendez-vous dans l'onglet « Destination » pour en générer un."
        )
        return

    st.subheader(f"Voyage : {dest['nom']} ({dest['type']})")

    for day in days:
        with st.expander(f"Jour {day['numero']}", expanded=True):
            # POI du jour
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
