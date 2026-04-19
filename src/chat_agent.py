"""Agent conversationnel pour l'onglet Chat.

Utilise le function-calling / tool-use des 3 providers LLM (Anthropic,
OpenAI, Google) pour traduire les intentions utilisateur en appels aux
fonctions existantes de la base et de l'API LLM. Chaque provider a son
propre format de messages et de tools — le dispatch est fait dans
`chat_turn`. Modèles légers (Haiku / gpt-4o-mini / gemini-flash) pour
contenir les coûts de tokens.
"""
import json

import streamlit as st

import database as db
from llm_api import (
    generate_pois,
    generate_activities,
    generate_travel,
    generate_additional_poi,
    generate_additional_activity,
)
from routing import compute_segment_metrics


# Modèles légers par provider pour le chat (tool-use uniquement).
CHAT_MODELS = {
    "Anthropic / Claude": "claude-haiku-4-5-20251001",
    "OpenAI / ChatGPT": "gpt-4o-mini",
    "Google / Gemini": "gemini-2.5-flash",
}


SYSTEM_PROMPT = """Tu es l'assistant conversationnel de l'application Travel Planner.

Ton rôle : aider l'utilisateur à créer et enrichir ses voyages via la discussion.
Tu disposes d'outils (tools) pour interagir avec la base de données.

Principes :
- Utilise TOUJOURS les outils pour agir — ne prétends jamais avoir fait une action sans tool.
- Avant de créer une destination, appelle `list_destinations` pour vérifier qu'elle n'existe pas.
- Pour identifier une destination par son nom, sois tolérant (l'utilisateur peut écrire « Japon » ou « le Japon »).
- Pour les opérations destructives (`delete_destination`, `delete_poi`, `delete_activity`, `generate_travel` sur un voyage existant), demande confirmation avant d'agir.
- Quand l'utilisateur n'est pas précis sur les quantités, propose des valeurs par défaut (8 POIs, 5 activités) et demande confirmation ou ajuste.
- Après une action réussie, résume brièvement (2-3 lignes max) et suggère la suite naturelle (ex: « Vous pouvez voir le résultat dans l'onglet Destination »).
- Pour les questions générales (climat, visa, meilleure saison…), réponds directement sans tool.
- Réponds en français, naturel et concis. Évite les longues listes sauf si demandé.
"""


# ── Définition des tools (schéma Anthropic) ──────────────────────────────────

TOOLS = [
    {
        "name": "list_destinations",
        "description": "Liste toutes les destinations enregistrées (nom, type, nombre de POIs, nombre d'activités).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "describe_destination",
        "description": "Décrit en détail une destination existante : POIs et activités avec leurs rangs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nom": {"type": "string", "description": "Nom de la destination."}
            },
            "required": ["nom"],
        },
    },
    {
        "name": "create_destination",
        "description": (
            "Crée une nouvelle destination et génère ses POIs et activités via le LLM principal. "
            "À utiliser uniquement si la destination n'existe pas déjà (vérifier avec list_destinations)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nom": {"type": "string"},
                "type": {"type": "string", "enum": ["Pays", "Région", "Ville"]},
                "nb_pois": {
                    "type": "integer",
                    "minimum": 3,
                    "maximum": 20,
                    "description": "Nombre de POIs (défaut 8).",
                },
                "nb_activities": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 15,
                    "description": "Nombre d'activités (défaut 5).",
                },
            },
            "required": ["nom", "type"],
        },
    },
    {
        "name": "delete_destination",
        "description": "Supprime une destination et tout son contenu (POIs, activités, voyage). DESTRUCTIF — demander confirmation avant.",
        "input_schema": {
            "type": "object",
            "properties": {"nom": {"type": "string"}},
            "required": ["nom"],
        },
    },
    {
        "name": "add_poi",
        "description": "Ajoute un nouveau POI à une destination via le LLM. Le commentaire sert d'indice (ex: 'un musée', 'un site naturel').",
        "input_schema": {
            "type": "object",
            "properties": {
                "destination_nom": {"type": "string"},
                "commentaire": {"type": "string", "description": "Description du POI souhaité (optionnel)."},
            },
            "required": ["destination_nom"],
        },
    },
    {
        "name": "delete_poi",
        "description": "Supprime un POI d'une destination (recherche par nom, insensible à la casse, correspondance partielle acceptée).",
        "input_schema": {
            "type": "object",
            "properties": {
                "destination_nom": {"type": "string"},
                "poi_nom": {"type": "string"},
            },
            "required": ["destination_nom", "poi_nom"],
        },
    },
    {
        "name": "add_activity",
        "description": "Ajoute une nouvelle activité à une destination via le LLM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "destination_nom": {"type": "string"},
                "commentaire": {"type": "string", "description": "Description de l'activité souhaitée (optionnel)."},
            },
            "required": ["destination_nom"],
        },
    },
    {
        "name": "delete_activity",
        "description": "Supprime une activité d'une destination (recherche par nom, correspondance partielle acceptée).",
        "input_schema": {
            "type": "object",
            "properties": {
                "destination_nom": {"type": "string"},
                "activity_nom": {"type": "string"},
            },
            "required": ["destination_nom", "activity_nom"],
        },
    },
    {
        "name": "generate_travel",
        "description": (
            "Génère un voyage jour par jour pour une destination : hôtels, restaurants, segments de transport. "
            "Si un voyage existe déjà, il est remplacé — demander confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"destination_nom": {"type": "string"}},
            "required": ["destination_nom"],
        },
    },
]


# ── Résolution des destinations par nom ──────────────────────────────────────

def _find_destination(nom):
    """Cherche une destination par nom. Match exact d'abord, puis partiel."""
    if not nom:
        return None
    nom_clean = nom.lower().strip()
    destinations = db.get_all_destinations()
    for d in destinations:
        if d["nom"].lower().strip() == nom_clean:
            return d
    for d in destinations:
        if nom_clean in d["nom"].lower() or d["nom"].lower() in nom_clean:
            return d
    return None


# ── Exécution des tools ──────────────────────────────────────────────────────

def execute_tool(name, args, llm_provider, llm_api_key):
    """Exécute un tool et retourne un dict sérialisable.

    Utilise le LLM configuré par l'utilisateur (`llm_provider`) pour les
    tools qui invoquent la génération (create_destination, add_poi, …).
    """
    try:
        if name == "list_destinations":
            destinations = db.get_all_destinations()
            result = []
            for d in destinations:
                pois = db.get_pois_for_destination(d["id"])
                acts = db.get_activities_for_destination(d["id"])
                result.append({
                    "nom": d["nom"],
                    "type": d["type"],
                    "nb_pois": len(pois),
                    "nb_activities": len(acts),
                })
            return {"success": True, "destinations": result}

        if name == "describe_destination":
            dest = _find_destination(args["nom"])
            if not dest:
                return {"success": False, "error": f"Destination « {args['nom']} » introuvable."}
            pois = db.get_pois_for_destination(dest["id"])
            acts = db.get_activities_for_destination(dest["id"])
            return {
                "success": True,
                "destination": {"nom": dest["nom"], "type": dest["type"]},
                "pois": [{"rang": p["rang"], "nom": p["nom"], "type": p["type"]} for p in pois],
                "activities": [{"rang": a["rang"], "nom": a["nom"], "type": a["type"]} for a in acts],
            }

        if name == "create_destination":
            nom = args["nom"].strip()
            type_dest = args["type"]
            nb_pois = args.get("nb_pois", 8)
            nb_acts = args.get("nb_activities", 5)

            if _find_destination(nom):
                return {
                    "success": False,
                    "error": f"La destination « {nom} » existe déjà. Utilise describe_destination.",
                }

            pois = generate_pois(nom, type_dest, nb_pois, provider=llm_provider, api_key=llm_api_key)
            if not pois:
                return {"success": False, "error": "Aucun POI n'a pu être généré."}

            acts = []
            if nb_acts > 0:
                try:
                    acts = generate_activities(nom, type_dest, nb_acts, provider=llm_provider, api_key=llm_api_key)
                except Exception as e:
                    # On crée quand même la destination avec les POIs
                    pass

            dest_id = db.create_destination(nom, type_dest)
            db.bulk_create_pois(dest_id, pois)
            db.renumber_pois(dest_id)  # garantit rangs séquentiels 1..N
            if acts:
                db.bulk_create_activities(dest_id, acts)
                db.renumber_activities(dest_id)

            # Pré-sélectionner la destination pour que l'onglet Destination s'ouvre dessus
            st.session_state["selected_destination_id"] = dest_id

            return {
                "success": True,
                "message": f"Destination « {nom} » créée avec {len(pois)} POIs et {len(acts)} activités.",
                "destination_id": dest_id,
            }

        if name == "delete_destination":
            dest = _find_destination(args["nom"])
            if not dest:
                return {"success": False, "error": f"Destination « {args['nom']} » introuvable."}
            db.delete_destination(dest["id"])
            if st.session_state.get("selected_destination_id") == dest["id"]:
                st.session_state.pop("selected_destination_id", None)
            return {"success": True, "message": f"Destination « {dest['nom']} » supprimée."}

        if name == "add_poi":
            dest = _find_destination(args["destination_nom"])
            if not dest:
                return {"success": False, "error": f"Destination « {args['destination_nom']} » introuvable."}
            existing = db.get_pois_for_destination(dest["id"])
            new_poi = generate_additional_poi(
                dest["nom"],
                [{"nom": p["nom"]} for p in existing],
                commentaire=args.get("commentaire", ""),
                provider=llm_provider,
                api_key=llm_api_key,
            )
            if not new_poi or not new_poi.get("nom"):
                return {"success": False, "error": "Aucun POI n'a pu être généré."}
            next_rang = (max((p["rang"] for p in existing), default=0) + 1) if existing else 1
            db.create_poi(
                dest["id"], next_rang, new_poi["nom"], new_poi.get("type", ""),
                new_poi.get("description", ""),
                new_poi.get("latitude", 0.0), new_poi.get("longitude", 0.0),
            )
            db.renumber_pois(dest["id"])
            return {"success": True, "message": f"POI « {new_poi['nom']} » ajouté à {dest['nom']}."}

        if name == "delete_poi":
            dest = _find_destination(args["destination_nom"])
            if not dest:
                return {"success": False, "error": f"Destination « {args['destination_nom']} » introuvable."}
            query = args["poi_nom"].lower().strip()
            for p in db.get_pois_for_destination(dest["id"]):
                if query == p["nom"].lower() or query in p["nom"].lower():
                    db.delete_poi(p["id"])
                    return {"success": True, "message": f"POI « {p['nom']} » supprimé."}
            return {"success": False, "error": f"Aucun POI « {args['poi_nom']} » dans {dest['nom']}."}

        if name == "add_activity":
            dest = _find_destination(args["destination_nom"])
            if not dest:
                return {"success": False, "error": f"Destination « {args['destination_nom']} » introuvable."}
            existing = db.get_activities_for_destination(dest["id"])
            new_act = generate_additional_activity(
                dest["nom"],
                [{"nom": a["nom"]} for a in existing],
                commentaire=args.get("commentaire", ""),
                provider=llm_provider,
                api_key=llm_api_key,
            )
            if not new_act or not new_act.get("nom"):
                return {"success": False, "error": "Aucune activité n'a pu être générée."}
            next_rang = (max((a["rang"] for a in existing), default=0) + 1) if existing else 1
            db.create_activity(
                dest["id"], next_rang, new_act["nom"], new_act.get("type", ""),
                new_act.get("description", ""),
                new_act.get("latitude", 0.0), new_act.get("longitude", 0.0),
                new_act.get("fournisseur_url"),
            )
            db.renumber_activities(dest["id"])
            return {"success": True, "message": f"Activité « {new_act['nom']} » ajoutée à {dest['nom']}."}

        if name == "delete_activity":
            dest = _find_destination(args["destination_nom"])
            if not dest:
                return {"success": False, "error": f"Destination « {args['destination_nom']} » introuvable."}
            query = args["activity_nom"].lower().strip()
            for a in db.get_activities_for_destination(dest["id"]):
                if query == a["nom"].lower() or query in a["nom"].lower():
                    db.delete_activity(a["id"])
                    return {"success": True, "message": f"Activité « {a['nom']} » supprimée."}
            return {"success": False, "error": f"Aucune activité « {args['activity_nom']} » dans {dest['nom']}."}

        if name == "generate_travel":
            dest = _find_destination(args["destination_nom"])
            if not dest:
                return {"success": False, "error": f"Destination « {args['destination_nom']} » introuvable."}
            pois = db.get_pois_for_destination(dest["id"])
            if not pois:
                return {"success": False, "error": f"Aucun POI dans « {dest['nom']} ». Impossible de générer."}
            acts = db.get_activities_for_destination(dest["id"])

            pois_api = [
                {"nom": p["nom"], "type": p["type"], "latitude": p["latitude"], "longitude": p["longitude"]}
                for p in pois
            ]
            acts_api = [
                {"nom": a["nom"], "type": a["type"], "latitude": a["latitude"], "longitude": a["longitude"]}
                for a in acts
            ]

            jours = generate_travel(
                dest["nom"], pois_api, activities=acts_api,
                provider=llm_provider, api_key=llm_api_key,
            )
            if not jours:
                return {"success": False, "error": "Aucun planning généré."}

            poi_name_to_id = {p["nom"].lower(): p["id"] for p in pois}
            act_name_to_id = {a["nom"].lower(): a["id"] for a in acts}
            ors_key = st.session_state.get("ors_api_key", "")
            gmaps_key = st.session_state.get("gmaps_api_key", "")

            days_for_db = []
            for j in jours:
                poi_ids = [poi_name_to_id[n.lower()] for n in j.get("poi_noms", []) if n.lower() in poi_name_to_id]
                act_ids = [act_name_to_id[n.lower()] for n in j.get("activity_noms", []) if n.lower() in act_name_to_id]
                segments = []
                for seg in j.get("segments", []):
                    seg_mode = seg.get("transport_mode", "voiture personnelle")
                    lat1, lon1 = seg.get("from_latitude"), seg.get("from_longitude")
                    lat2, lon2 = seg.get("to_latitude"), seg.get("to_longitude")
                    dist_km = dur_h = None
                    if lat1 and lon1 and lat2 and lon2:
                        dist_km, dur_h = compute_segment_metrics(
                            seg_mode, [(lat1, lon1), (lat2, lon2)], ors_key, gmaps_key,
                        )
                    segments.append({
                        "from_name": seg.get("from_name", ""),
                        "from_latitude": lat1, "from_longitude": lon1,
                        "to_name": seg.get("to_name", ""),
                        "to_latitude": lat2, "to_longitude": lon2,
                        "transport_mode": seg_mode,
                        "distance_km": dist_km, "duration_h": dur_h,
                        "budget": seg.get("budget"),
                    })
                days_for_db.append({
                    "numero": j["numero"],
                    "hotel_nom": j.get("hotel_nom", ""), "hotel_adresse": j.get("hotel_adresse", ""),
                    "hotel_latitude": j.get("hotel_latitude"), "hotel_longitude": j.get("hotel_longitude"),
                    "hotel_budget": j.get("hotel_budget"),
                    "restaurant_nom": j.get("restaurant_nom", ""), "restaurant_adresse": j.get("restaurant_adresse", ""),
                    "restaurant_latitude": j.get("restaurant_latitude"),
                    "restaurant_longitude": j.get("restaurant_longitude"),
                    "restaurant_budget": j.get("restaurant_budget"),
                    "poi_ids": poi_ids, "activity_ids": act_ids,
                    "segments": segments,
                })

            travel_id = db.save_travel(dest["id"], days_for_db)
            st.session_state["selected_destination_id"] = dest["id"]
            st.session_state["selected_travel_id"] = travel_id
            return {
                "success": True,
                "message": f"Voyage de {len(jours)} jours généré pour « {dest['nom']} ».",
                "nb_days": len(jours),
            }

        return {"success": False, "error": f"Tool inconnu : {name}"}

    except Exception as e:
        return {"success": False, "error": f"Exception : {type(e).__name__} — {e}"}


# ── Boucle d'échange ─────────────────────────────────────────────────────────

# ── Adaptateurs de schéma de tools par provider ─────────────────────────────

def _tools_for_anthropic():
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in TOOLS
    ]


def _tools_for_openai():
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOLS
    ]


def _clean_schema_for_google(schema):
    """Google genai.types.Schema accepte un sous-ensemble de JSON Schema.
    On retire les clés non supportées (minimum, maximum, additionalProperties…)."""
    allowed = {"type", "description", "enum", "properties", "required", "items", "format", "nullable"}
    if not isinstance(schema, dict):
        return schema
    cleaned = {}
    for k, v in schema.items():
        if k not in allowed:
            continue
        if k == "properties" and isinstance(v, dict):
            cleaned[k] = {pk: _clean_schema_for_google(pv) for pk, pv in v.items()}
        elif k == "items" and isinstance(v, dict):
            cleaned[k] = _clean_schema_for_google(v)
        else:
            cleaned[k] = v
    return cleaned


def _tools_for_google():
    from google.genai import types
    return [types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=_clean_schema_for_google(t["input_schema"]),
        )
        for t in TOOLS
    ])]


# ── Helper : notifier la progression (callback optionnel) ───────────────────

def _notify(progress_callback, phase, name, args=None, result=None):
    """Appelle progress_callback s'il est fourni, sans propager ses éventuelles erreurs."""
    if progress_callback is None:
        return
    try:
        progress_callback(phase, name, args, result)
    except Exception:
        pass


# ── Implémentation par provider ─────────────────────────────────────────────

def _chat_turn_anthropic(user_message, history_messages, api_key, max_iterations, progress_callback=None):
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=180.0)
    messages = list(history_messages)
    messages.append({"role": "user", "content": user_message})
    tool_executions = []

    for _ in range(max_iterations):
        response = client.messages.create(
            model=CHAT_MODELS["Anthropic / Claude"],
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=_tools_for_anthropic(),
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "\n".join(
                b.text for b in response.content if getattr(b, "type", None) == "text"
            ).strip()
            return final_text or "(pas de réponse)", messages, tool_executions

        tool_results_content = []
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                _notify(progress_callback, "start", block.name, block.input)
                result = execute_tool(block.name, block.input, "Anthropic / Claude", api_key)
                tool_executions.append((block.name, block.input, result))
                _notify(progress_callback, "end", block.name, block.input, result)
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
        messages.append({"role": "user", "content": tool_results_content})

    return "L'assistant a atteint la limite d'itérations.", messages, tool_executions


def _chat_turn_openai(user_message, history_messages, api_key, max_iterations, progress_callback=None):
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=180.0)
    messages = list(history_messages)
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    messages.append({"role": "user", "content": user_message})
    tool_executions = []
    tools = _tools_for_openai()

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=CHAT_MODELS["OpenAI / ChatGPT"],
            max_tokens=2048,
            messages=messages,
            tools=tools,
        )
        msg = response.choices[0].message

        assistant_entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        messages.append(assistant_entry)

        if not msg.tool_calls:
            return (msg.content or "").strip() or "(pas de réponse)", messages, tool_executions

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            _notify(progress_callback, "start", tc.function.name, args)
            result = execute_tool(tc.function.name, args, "OpenAI / ChatGPT", api_key)
            tool_executions.append((tc.function.name, args, result))
            _notify(progress_callback, "end", tc.function.name, args, result)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "L'assistant a atteint la limite d'itérations.", messages, tool_executions


def _chat_turn_google(user_message, history_messages, api_key, max_iterations, progress_callback=None):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    contents = list(history_messages)
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))
    tool_executions = []
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=_tools_for_google(),
    )

    for _ in range(max_iterations):
        response = client.models.generate_content(
            model=CHAT_MODELS["Google / Gemini"],
            contents=contents,
            config=config,
        )

        function_calls = []
        text_parts = []
        model_content = None
        if response.candidates:
            model_content = response.candidates[0].content
            for part in (model_content.parts or []):
                if getattr(part, "function_call", None):
                    function_calls.append(part.function_call)
                elif getattr(part, "text", None):
                    text_parts.append(part.text)

        if model_content is not None:
            contents.append(model_content)

        if not function_calls:
            final_text = "\n".join(text_parts).strip()
            return final_text or "(pas de réponse)", contents, tool_executions

        response_parts = []
        for fc in function_calls:
            args = dict(fc.args) if fc.args else {}
            _notify(progress_callback, "start", fc.name, args)
            result = execute_tool(fc.name, args, "Google / Gemini", api_key)
            tool_executions.append((fc.name, args, result))
            _notify(progress_callback, "end", fc.name, args, result)
            response_parts.append(types.Part.from_function_response(
                name=fc.name,
                response={"result": result},
            ))
        contents.append(types.Content(role="user", parts=response_parts))

    return "L'assistant a atteint la limite d'itérations.", contents, tool_executions


# ── Dispatcher ──────────────────────────────────────────────────────────────

_CHAT_TURN_BY_PROVIDER = {
    "Anthropic / Claude": _chat_turn_anthropic,
    "OpenAI / ChatGPT": _chat_turn_openai,
    "Google / Gemini": _chat_turn_google,
}


def chat_turn(user_message, history_messages, llm_provider, llm_api_key,
              max_iterations=10, progress_callback=None):
    """Un tour d'échange avec l'agent. Dispatche sur le provider configuré.

    Args:
        progress_callback: callable optionnel `f(phase, name, args, result)` où
            `phase` ∈ {"start", "end"}. Appelé avant et après chaque tool pour
            permettre à l'UI d'afficher un feedback progressif.

    Retourne (reply_text, new_history, tool_executions).
    """
    handler = _CHAT_TURN_BY_PROVIDER.get(llm_provider)
    if handler is None:
        raise ValueError(f"Provider non supporté par le chat : {llm_provider}")
    return handler(user_message, history_messages, llm_api_key, max_iterations, progress_callback)
