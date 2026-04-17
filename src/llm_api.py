import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import requests

# Préfixe utilisé pour signaler qu'une URL "fournisseur" est un fallback
# de recherche Google (URL LLM jugée invalide à la validation HTTP).
GOOGLE_SEARCH_URL_PREFIX = "https://www.google.com/search?q="

PROVIDERS = {
    "Anthropic / Claude": {
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
    },
    "OpenAI / ChatGPT": {
        "models": ["gpt-4o", "gpt-4o-mini"],
    },
    "Google / Gemini": {
        "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
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
    "Le JSON doit avoir la structure : "
    '{"jours": [{'
    '"numero": int, '
    '"poi_noms": [str], '
    '"activity_noms": [str], '
    '"hotel_nom": str, "hotel_adresse": str, "hotel_latitude": float, "hotel_longitude": float, '
    '"hotel_budget": float (euros/nuit), '
    '"restaurant_nom": str, "restaurant_adresse": str, "restaurant_latitude": float, "restaurant_longitude": float, '
    '"restaurant_budget": float (euros/personne), '
    '"segments": [{'
    '"from_name": str, "from_latitude": float, "from_longitude": float, '
    '"to_name": str, "to_latitude": float, "to_longitude": float, '
    '"transport_mode": str (un de : "à pied", "en vélo", "voiture personnelle", '
    '"voiture de location", "taxi", "bus", "métro", "train", "bateau", "avion"), '
    '"budget": float (coût estimé du segment en euros, 0 pour à pied/vélo)'
    '}]'
    '}]}'
)


def _extract_json(text):
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return json.loads(match.group())
    raise json.JSONDecodeError("Aucun JSON trouvé dans la réponse.", text, 0)


# ── Validation & fallback des URLs "fournisseur" des Activités ──────────────

def _search_url(activity_name, destination_name):
    """URL de recherche Google pour une activité donnée."""
    q = quote(f"{activity_name} {destination_name}".strip())
    return f"{GOOGLE_SEARCH_URL_PREFIX}{q}"


def _is_url_valid(url, timeout=3):
    """Vérifie qu'une URL renvoie un statut HTTP OK (200-399)."""
    if not url or url.startswith(GOOGLE_SEARCH_URL_PREFIX):
        return False
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            stream=True,  # on ne télécharge que les headers
            headers={"User-Agent": "Mozilla/5.0 (compatible; TravelPlanner/1.0)"},
        )
        resp.close()
        return 200 <= resp.status_code < 400
    except Exception:
        return False


def _sanitize_activity_urls(activities, destination_name):
    """Pour chaque activité, valide l'URL fournisseur ; remplace les URLs
    cassées par une URL de recherche Google (détectable via le préfixe)."""
    def _fix(act):
        url = act.get("fournisseur_url")
        if not _is_url_valid(url):
            act["fournisseur_url"] = _search_url(act.get("nom", ""), destination_name)
        return act

    with ThreadPoolExecutor(max_workers=5) as ex:
        return list(ex.map(_fix, activities))


# ── Anthropic ────────────────────────────────────────────────────────────────

def _anthropic_call(api_key, model, system, user_msg):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key, timeout=180.0)
    response = client.messages.create(
        model=model,
        max_tokens=16384,
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
    client = OpenAI(api_key=api_key, timeout=180.0)
    response = client.chat.completions.create(
        model=model,
        max_tokens=16384,
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
    if not api_key:
        raise ValueError(f"Clé API manquante pour {provider}.")
    mdl = model or info["models"][0]
    return provider, api_key, mdl


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


ACTIVITY_SCHEMA_FIELDS = (
    '{"rang": int, "nom": str, '
    '"type": str, "description": str, '
    '"latitude": float, "longitude": float, '
    '"fournisseur_url": str (URL complète du site web du prestataire proposant '
    'cette activité, ex: https://www.cooking-school-paris.com)}'
)


def generate_activities(destination_nom, destination_type, nb_activities, provider=None, api_key=None, model=None):
    system = (
        "Tu es un expert en voyages et tourisme. "
        "Réponds UNIQUEMENT en JSON valide, sans texte avant ou après. "
        'Le JSON doit avoir la structure : {"activities": [' + ACTIVITY_SCHEMA_FIELDS + ", ...]}"
    )
    user_msg = (
        f"Liste les {nb_activities} activités touristiques caractéristiques à réaliser "
        f"à « {destination_nom} » ({destination_type}). "
        "Pour chaque activité fournis : rang, nom, type (Sport, Culture, Cuisine, Bien-être, etc.), "
        "description courte, latitude et longitude précises (WGS84) d'un lieu où la réaliser, "
        "et fournisseur_url = URL complète du site web d'un prestataire réel proposant cette activité "
        "(par exemple le site d'une école de cuisine, d'un guide, d'un organisme de visite). "
        "Les activités doivent être DIFFÉRENTES des simples visites de sites (POI) : "
        "privilégie des expériences à faire (cours de cuisine, randonnée guidée, concert, spa, atelier, dégustation, etc.). "
        "Trie du plus emblématique au moins emblématique."
    )
    fb_p, fb_k, fb_m = _get_fallback()
    raw = _llm_call(provider, api_key, model, system, user_msg,
                     fallback_provider=fb_p, fallback_api_key=fb_k, fallback_model=fb_m)
    data = _extract_json(raw)
    activities = data.get("activities", [])
    return _sanitize_activity_urls(activities, destination_nom)


def generate_additional_activity(destination_nom, existing_activities, commentaire=None,
                                  provider=None, api_key=None, model=None):
    existing_names = "\n".join(f"- {a['nom']}" for a in existing_activities) or "(aucune)"
    system = (
        "Tu es un expert en voyages et tourisme. "
        "Réponds UNIQUEMENT en JSON valide, sans texte avant ou après. "
        'Le JSON doit avoir la structure : ' + ACTIVITY_SCHEMA_FIELDS
    )

    commentaire_clean = (commentaire or "").strip()

    if commentaire_clean:
        user_msg = (
            f"Destination : « {destination_nom} ».\n\n"
            f"⚠️ DEMANDE PRIORITAIRE DE L'UTILISATEUR : « {commentaire_clean} »\n\n"
            f"Tu DOIS proposer UNE SEULE nouvelle activité touristique qui :\n"
            f"1. Correspond EXACTEMENT à la demande de l'utilisateur ci-dessus (critère principal)\n"
            f"2. N'est PAS dans la liste suivante des activités déjà retenues :\n"
            f"{existing_names}\n\n"
            f"Fournis : rang, nom, type (Sport, Culture, Cuisine, Bien-être, etc.), "
            f"description courte, latitude et longitude précises (WGS84) d'un lieu où la réaliser, "
            f"et fournisseur_url = URL complète du site d'un prestataire réel proposant cette activité."
        )
    else:
        user_msg = (
            f"Pour la destination « {destination_nom} », voici les activités déjà retenues :\n"
            f"{existing_names}\n\n"
            "Propose UNE SEULE nouvelle activité touristique qui n'est PAS dans cette liste. "
            "Fournis : rang, nom, type (Sport, Culture, Cuisine, Bien-être, etc.), "
            "description courte, latitude et longitude précises (WGS84), et fournisseur_url "
            "(URL complète du site web d'un prestataire réel proposant cette activité)."
        )

    fb_p, fb_k, fb_m = _get_fallback()
    raw = _llm_call(provider, api_key, model, system, user_msg,
                     fallback_provider=fb_p, fallback_api_key=fb_k, fallback_model=fb_m)
    data = _extract_json(raw)
    if "nom" in data:
        return _sanitize_activity_urls([data], destination_nom)[0]
    activities = data.get("activities", [])
    if not activities:
        return None
    return _sanitize_activity_urls([activities[0]], destination_nom)[0]


def generate_additional_poi(destination_nom, existing_pois, commentaire=None,
                              provider=None, api_key=None, model=None):
    existing_names = "\n".join(f"- {p['nom']}" for p in existing_pois) or "(aucun)"
    system = (
        "Tu es un expert en voyages et tourisme. "
        "Réponds UNIQUEMENT en JSON valide, sans texte avant ou après. "
        'Le JSON doit avoir la structure : {"rang": int, "nom": str, '
        '"type": str, "description": str, "latitude": float, "longitude": float}'
    )
    commentaire_clean = (commentaire or "").strip()
    if commentaire_clean:
        user_msg = (
            f"Destination : « {destination_nom} ».\n\n"
            f"⚠️ DEMANDE PRIORITAIRE DE L'UTILISATEUR : « {commentaire_clean} »\n\n"
            f"Tu DOIS proposer UN SEUL nouveau site touristique (POI) qui :\n"
            f"1. Correspond EXACTEMENT à la demande de l'utilisateur ci-dessus (critère principal)\n"
            f"2. N'est PAS dans la liste suivante des sites déjà retenus :\n"
            f"{existing_names}\n\n"
            f"Fournis : rang, nom, type (Nature, Architecture, Histoire, Musée, Gastronomie, etc.), "
            f"description courte, latitude et longitude précises (WGS84)."
        )
    else:
        user_msg = (
            f"Pour la destination « {destination_nom} », voici les sites déjà retenus :\n"
            f"{existing_names}\n\n"
            "Propose UN SEUL nouveau site touristique incontournable qui n'est PAS dans cette liste. "
            "Fournis : rang, nom, type (Nature, Architecture, Histoire, Musée, Gastronomie, etc.), "
            "description courte, latitude et longitude précises (WGS84)."
        )
    fb_p, fb_k, fb_m = _get_fallback()
    raw = _llm_call(provider, api_key, model, system, user_msg,
                     fallback_provider=fb_p, fallback_api_key=fb_k, fallback_model=fb_m)
    data = _extract_json(raw)
    if "nom" in data:
        return data
    pois = data.get("pois", [])
    return pois[0] if pois else None


def generate_travel(destination_nom, pois, activities=None, provider=None, api_key=None, model=None):
    pois_desc = "\n".join(
        f"- {p['nom']} ({p['type']}, lat:{p['latitude']}, lon:{p['longitude']})"
        for p in pois
    )
    activities = activities or []
    activities_desc = "\n".join(
        f"- {a['nom']} ({a['type']}, lat:{a['latitude']}, lon:{a['longitude']})"
        for a in activities
    ) or "(aucune)"

    user_msg = (
        f"Planifie un voyage jour par jour pour visiter « {destination_nom} ». "
        f"Voici les POI à visiter :\n{pois_desc}\n\n"
        f"Voici les Activités à réaliser :\n{activities_desc}\n\n"
        "Pour chaque jour, propose :\n"
        "- Les POI (poi_noms) à visiter ce jour-là (regroupe par proximité géographique)\n"
        "- Les Activités (activity_noms) à réaliser ce jour-là (regroupe par proximité)\n"
        "- Un hôtel bien noté pour la nuit (hotel_nom, hotel_adresse, hotel_latitude, hotel_longitude, "
        "hotel_budget = prix estimé par nuit en euros)\n"
        "- Un restaurant bien noté pour le dîner (restaurant_nom, restaurant_adresse, restaurant_latitude, "
        "restaurant_longitude, restaurant_budget = prix estimé par personne en euros)\n"
        "- Une liste ORDONNÉE de segments (segments) représentant les déplacements de la journée : "
        "hôtel matin → (POIs et/ou Activités dans l'ordre) → hôtel soir (ou hôtel suivant). "
        "Les extrémités d'un segment sont UNIQUEMENT des hôtels, POIs ou Activités (JAMAIS le restaurant). "
        "Chaque segment a un from_name/from_latitude/from_longitude, un to_name/to_latitude/to_longitude, "
        "un transport_mode, et un budget estimé en euros "
        "(0 pour à pied/vélo ; prix d'un billet/course pour transports ; prix estimé du carburant pour voiture).\n\n"
        "CHOIX DU MODE DE TRANSPORT (OBLIGATOIRE, basé sur la DISTANCE RÉELLE entre from et to) :\n"
        "- distance < 1.5 km : 'à pied' (PRÉFÉRENCE ABSOLUE pour toute courte distance urbaine)\n"
        "- 1.5 à 5 km en ville : 'à pied', 'en vélo' ou 'métro' selon contexte\n"
        "- 5 à 30 km en ville/banlieue : 'métro', 'bus', 'taxi', 'voiture personnelle'\n"
        "- 30 à 500 km inter-villes : 'train' (si réseau ferroviaire dense) ou 'voiture personnelle'\n"
        "- > 500 km : 'avion' ou 'train' rapide (TGV, Shinkansen...)\n"
        "- traversée maritime obligatoire (île, lac sans pont) : 'bateau'\n\n"
        "RÈGLE CRITIQUE : pour un segment < 1.5 km, utilise TOUJOURS 'à pied'. "
        "Ne choisis JAMAIS 'train', 'métro', 'bus' ou 'voiture' pour un trajet de quelques centaines de mètres.\n\n"
        "IMPORTANT : les coordonnées GPS de l'hôtel, du restaurant et de chaque segment "
        "sont OBLIGATOIRES. Les budgets sont OBLIGATOIRES. Ne jamais omettre ces champs.\n"
        "Optimise l'itinéraire pour minimiser les déplacements."
    )
    fb_p, fb_k, fb_m = _get_fallback()
    raw = _llm_call(provider, api_key, model, SYSTEM_TRAVEL, user_msg,
                     fallback_provider=fb_p, fallback_api_key=fb_k, fallback_model=fb_m)
    data = _extract_json(raw)
    return data.get("jours", [])
