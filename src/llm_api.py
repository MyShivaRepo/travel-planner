import json
import os
import re

PROVIDERS = {
    "Anthropic / Claude": {
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
        "env_key": "ANTHROPIC_API_KEY",
    },
    "OpenAI / ChatGPT": {
        "models": ["gpt-4o", "gpt-4o-mini"],
        "env_key": "OPENAI_API_KEY",
    },
    "Google / Gemini": {
        "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
        "env_key": "GOOGLE_API_KEY",
    },
}

SYSTEM_POI = (
    "Tu es un expert en voyages et tourisme. "
    "Réponds UNIQUEMENT en JSON valide, sans texte avant ou après. "
    'Le JSON doit avoir la structure : {"pois": [{"rang": int, "nom": str, '
    '"type": str, "description": str, "latitude": float, "longitude": float}, ...]}'
)

SYSTEM_TRAVEL = (
    "Tu es un expert en planification de voyages. "
    "Réponds UNIQUEMENT en JSON valide, sans texte avant ou après. "
    'Le JSON doit avoir la structure : {"jours": [{"numero": int, '
    '"poi_noms": [str], "hotel_nom": str, "hotel_adresse": str, '
    '"hotel_latitude": float, "hotel_longitude": float, '
    '"restaurant_nom": str, "restaurant_adresse": str, '
    '"restaurant_latitude": float, "restaurant_longitude": float}, ...]}'
)


def _extract_json(text):
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return json.loads(match.group())
    raise json.JSONDecodeError("Aucun JSON trouvé dans la réponse.", text, 0)


# ── Anthropic ────────────────────────────────────────────────────────────────

def _anthropic_call(api_key, model, system, user_msg):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return next((b.text for b in response.content if b.type == "text"), "")


def _anthropic_test(api_key, model):
    import anthropic
    try:
        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model=model, max_tokens=10,
            messages=[{"role": "user", "content": "Dis bonjour."}],
        )
        return True, "Clé API valide."
    except anthropic.AuthenticationError:
        return False, "Clé API invalide."
    except anthropic.RateLimitError:
        return False, "Quota API dépassé."
    except anthropic.APITimeoutError:
        return False, "Timeout de la requête API."
    except anthropic.APIConnectionError:
        return False, "Erreur réseau : impossible de joindre l'API."


# ── OpenAI ───────────────────────────────────────────────────────────────────

def _openai_call(api_key, model, system, user_msg):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )
    return response.choices[0].message.content or ""


def _openai_test(api_key, model):
    from openai import OpenAI, AuthenticationError, RateLimitError, APITimeoutError, APIConnectionError
    try:
        client = OpenAI(api_key=api_key)
        client.chat.completions.create(
            model=model, max_tokens=10,
            messages=[{"role": "user", "content": "Dis bonjour."}],
        )
        return True, "Clé API valide."
    except AuthenticationError:
        return False, "Clé API invalide."
    except RateLimitError:
        return False, "Quota API dépassé."
    except APITimeoutError:
        return False, "Timeout de la requête API."
    except APIConnectionError:
        return False, "Erreur réseau : impossible de joindre l'API."


# ── Google Gemini ────────────────────────────────────────────────────────────

def _google_call(api_key, model, system, user_msg):
    from google import genai
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=user_msg,
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
        ),
    )
    return response.text or ""


def _google_test(api_key, model):
    from google import genai
    try:
        client = genai.Client(api_key=api_key)
        client.models.generate_content(
            model=model,
            contents="Dis bonjour.",
        )
        return True, "Clé API valide."
    except Exception as e:
        msg = str(e).lower()
        if "api_key" in msg or "401" in msg or "403" in msg:
            return False, "Clé API invalide."
        if "429" in msg:
            return False, "Quota API dépassé."
        return False, f"Erreur : {e}"


# ── Dispatch ─────────────────────────────────────────────────────────────────

_CALL = {
    "Anthropic / Claude": _anthropic_call,
    "OpenAI / ChatGPT": _openai_call,
    "Google / Gemini": _google_call,
}

_TEST = {
    "Anthropic / Claude": _anthropic_test,
    "OpenAI / ChatGPT": _openai_test,
    "Google / Gemini": _google_test,
}


def _resolve(provider=None, api_key=None, model=None):
    if not provider:
        raise ValueError("Aucun fournisseur LLM sélectionné. Configurez-le dans Settings.")
    info = PROVIDERS[provider]
    key = api_key or os.environ.get(info["env_key"], "")
    if not key:
        raise ValueError(f"Clé API manquante pour {provider}.")
    mdl = model or info["models"][0]
    return provider, key, mdl


def test_api_key(provider, api_key, model=None):
    try:
        provider, key, mdl = _resolve(provider, api_key, model)
        return _TEST[provider](key, mdl)
    except Exception as e:
        return False, f"Erreur : {e}"


def _llm_call(provider, api_key, model, system, user_msg,
              fallback_provider=None, fallback_api_key=None, fallback_model=None):
    provider, key, mdl = _resolve(provider, api_key, model)
    try:
        return _CALL[provider](key, mdl, system, user_msg)
    except Exception as primary_error:
        if not fallback_provider or not fallback_api_key:
            raise
        try:
            fb_provider, fb_key, fb_mdl = _resolve(fallback_provider, fallback_api_key, fallback_model)
            return _CALL[fb_provider](fb_key, fb_mdl, system, user_msg)
        except Exception:
            # Le fallback a aussi échoué, on remonte l'erreur primaire
            raise primary_error


def _get_fallback():
    """Récupère les paramètres du LLM de secours depuis session_state."""
    import streamlit as st
    fb_provider = st.session_state.get("fallback_provider")
    fb_key = st.session_state.get("fallback_api_key")
    if fb_provider and fb_key:
        return fb_provider, fb_key, None
    return None, None, None


def generate_pois(destination_nom, destination_type, nb_pois, provider=None, api_key=None, model=None):
    user_msg = (
        f"Liste les {nb_pois} sites touristiques incontournables "
        f"de « {destination_nom} » ({destination_type}). "
        "Pour chaque site fournis : rang, nom, type (Nature, Architecture, Histoire, "
        "Musée, Gastronomie, etc.), description courte, "
        "latitude et longitude précises (WGS84). "
        "Trie du plus emblématique au moins emblématique."
    )
    fb_p, fb_k, fb_m = _get_fallback()
    raw = _llm_call(provider, api_key, model, SYSTEM_POI, user_msg,
                     fallback_provider=fb_p, fallback_api_key=fb_k, fallback_model=fb_m)
    data = _extract_json(raw)
    return data.get("pois", [])


def generate_additional_poi(destination_nom, existing_pois, provider=None, api_key=None, model=None):
    existing_names = "\n".join(f"- {p['nom']}" for p in existing_pois)
    user_msg = (
        f"Pour la destination « {destination_nom} », voici les sites déjà retenus :\n"
        f"{existing_names}\n\n"
        "Propose UN SEUL nouveau site touristique incontournable qui n'est PAS dans cette liste. "
        "Fournis : rang, nom, type (Nature, Architecture, Histoire, Musée, Gastronomie, etc.), "
        "description courte, latitude et longitude précises (WGS84)."
    )
    system = (
        "Tu es un expert en voyages et tourisme. "
        "Réponds UNIQUEMENT en JSON valide, sans texte avant ou après. "
        'Le JSON doit avoir la structure : {"rang": int, "nom": str, '
        '"type": str, "description": str, "latitude": float, "longitude": float}'
    )
    fb_p, fb_k, fb_m = _get_fallback()
    raw = _llm_call(provider, api_key, model, system, user_msg,
                     fallback_provider=fb_p, fallback_api_key=fb_k, fallback_model=fb_m)
    data = _extract_json(raw)
    if "nom" in data:
        return data
    pois = data.get("pois", [])
    return pois[0] if pois else None


def generate_travel(destination_nom, pois, transport_mode="mixte", provider=None, api_key=None, model=None):
    pois_desc = "\n".join(
        f"- {p['nom']} ({p['type']}, lat:{p['latitude']}, lon:{p['longitude']})"
        for p in pois
    )
    transport_info = {
        "à pied": "Le voyageur se déplace À PIED : regroupe les POI très proches (rayon ~2-3 km/jour).",
        "vélo": "Le voyageur se déplace À VÉLO : rayon raisonnable 10-20 km/jour.",
        "voiture": "Le voyageur se déplace EN VOITURE : rayon 50-150 km/jour possible.",
        "train": "Le voyageur se déplace EN TRAIN : privilégie les POI accessibles par gares.",
        "bateau": "Le voyageur se déplace EN BATEAU : privilégie les POI accessibles par la mer/les canaux.",
        "transport public": "Le voyageur utilise les TRANSPORTS PUBLICS (métro, bus) : privilégie les POI desservis.",
        "mixte": "Le voyageur combine plusieurs modes selon la pertinence locale (à pied en ville, voiture sur routes, bateau si îles).",
    }.get(transport_mode, "Le voyageur adapte son mode de transport selon la destination.")

    user_msg = (
        f"Planifie un voyage jour par jour pour visiter « {destination_nom} ». "
        f"Voici les sites à visiter :\n{pois_desc}\n\n"
        f"Mode de transport : {transport_mode}.\n"
        f"{transport_info}\n\n"
        "Pour chaque jour, propose :\n"
        "- Les sites (poi_noms) à visiter ce jour-là (regroupe par proximité géographique "
        "compatible avec le mode de transport)\n"
        "- Un hôtel bien noté pour la nuit (hotel_nom, hotel_adresse, hotel_latitude, hotel_longitude)\n"
        "- Un restaurant bien noté pour le dîner (restaurant_nom, restaurant_adresse, restaurant_latitude, restaurant_longitude)\n"
        "IMPORTANT : chaque jour DOIT contenir les coordonnées GPS (latitude/longitude) "
        "de l'hôtel ET du restaurant. Ne jamais omettre ces champs.\n"
        "Optimise l'itinéraire pour minimiser les déplacements compte tenu du mode de transport."
    )
    fb_p, fb_k, fb_m = _get_fallback()
    raw = _llm_call(provider, api_key, model, SYSTEM_TRAVEL, user_msg,
                     fallback_provider=fb_p, fallback_api_key=fb_k, fallback_model=fb_m)
    data = _extract_json(raw)
    return data.get("jours", [])
