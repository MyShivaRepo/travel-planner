"""Module de routage via OpenRouteService (ORS).

Calcule les vrais tracés routiers entre points selon le mode de transport.
Pour les modes non supportés par ORS (train, bateau, transport public),
retourne None → l'appelant affichera des lignes droites.
"""
import requests

ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions"

# Mapping mode transport (app) → profil ORS
MODE_TO_ORS_PROFILE = {
    "à pied": "foot-walking",
    "en vélo": "cycling-regular",
    "voiture personnelle": "driving-car",
    "voiture de location": "driving-car",
    "taxi": "driving-car",
    "bus": "driving-car",  # ORS n'a pas de profil bus, on utilise driving-car
    # Rétrocompatibilité avec les anciens voyages en base :
    "voiture": "driving-car",
    "vélo": "cycling-regular",
    # Les modes suivants ne sont pas supportés par ORS :
    "métro": None,
    "train": None,
    "bateau": None,
    "avion": None,
    "transport public": None,
    "mixte": "driving-car",
}


def get_route(coords, transport_mode, api_key, timeout=10):
    """
    Calcule le tracé routier entre une liste de points.

    Args:
        coords: liste de [lat, lon]
        transport_mode: mode de transport (str)
        api_key: clé API ORS
        timeout: timeout HTTP en secondes

    Returns:
        dict avec "geometry" (liste de [lat, lon]) et "duration" (secondes)
        ou None si échec / mode non supporté.
    """
    if not api_key or len(coords) < 2:
        return None

    profile = MODE_TO_ORS_PROFILE.get(transport_mode)
    if not profile:
        return None

    # ORS attend [lon, lat] dans l'ordre inverse de lat/lon
    ors_coords = [[c[1], c[0]] for c in coords]

    url = f"{ORS_BASE_URL}/{profile}/geojson"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    # radiuses: -1 signifie "pas de limite" pour trouver le point routable le plus proche
    # (par défaut ORS limite à 350m ce qui échoue pour les POI en montagne, forêt, etc.)
    body = {
        "coordinates": ors_coords,
        "radiuses": [-1] * len(ors_coords),
    }

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        feature = features[0]
        # geometry GeoJSON : [lon, lat] → on remet en [lat, lon]
        geom = [[c[1], c[0]] for c in feature["geometry"]["coordinates"]]
        duration = feature["properties"]["summary"]["duration"]  # secondes
        distance = feature["properties"]["summary"]["distance"]  # mètres
        return {"geometry": geom, "duration": duration, "distance": distance}
    except Exception:
        return None


def format_duration(seconds):
    """Formate une durée en secondes en texte lisible."""
    if seconds is None:
        return ""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h{m:02d}"
    return f"{m} min"


def format_distance(meters):
    """Formate une distance en mètres en texte lisible."""
    if meters is None:
        return ""
    if meters < 1000:
        return f"{int(meters)} m"
    return f"{meters/1000:.1f} km"
