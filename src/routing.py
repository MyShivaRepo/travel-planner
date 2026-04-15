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
    "bus": "driving-car",
    # Train / métro : pas de profil ORS → routés via Google Maps Directions
    # (si clé configurée). Sinon fallback driving-car.
    "train": "driving-car",
    "métro": "driving-car",
    # Rétrocompatibilité avec les anciens voyages en base :
    "voiture": "driving-car",
    "vélo": "cycling-regular",
    "transport public": "driving-car",
    "mixte": "driving-car",
    # Modes sans équivalent routier (lignes droites) :
    "bateau": None,
    "avion": None,
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


def haversine_m(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau en mètres."""
    import math
    R = 6371000  # mètres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# Vitesses moyennes (km/h) pour estimer la durée en fallback
MODE_AVG_SPEED_KMH = {
    "à pied": 5,
    "en vélo": 15,
    "voiture personnelle": 70,
    "voiture de location": 70,
    "taxi": 40,
    "bus": 25,
    "métro": 35,
    "train": 100,
    "bateau": 30,
    "avion": 800,
}


def compute_segment_metrics(mode, coords, ors_key, gmaps_key):
    """
    Retourne (distance_m, duration_sec) pour un segment.

    Tente d'abord le vrai routage (ORS / Google Maps / great-circle).
    Si indisponible, fallback sur la distance à vol d'oiseau et une durée
    estimée à partir de la vitesse moyenne du mode.
    """
    if len(coords) < 2:
        return None, None

    # Essayer le vrai routage
    route_data = None
    if mode == "avion":
        from google_routing import great_circle_route
        route_data = great_circle_route(coords)
    elif mode in {"métro", "train"} and gmaps_key:
        from google_routing import get_transit_route
        route_data = get_transit_route(coords, mode, gmaps_key)
        if not route_data and ors_key:
            route_data = get_route(coords, mode, ors_key)
    elif mode == "bateau":
        route_data = None  # toujours fallback haversine
    elif ors_key:
        route_data = get_route(coords, mode, ors_key)

    if route_data:
        return route_data["distance"], route_data["duration"]

    # Fallback : haversine + vitesse moyenne du mode
    dist_m = haversine_m(coords[0][0], coords[0][1], coords[-1][0], coords[-1][1])
    speed_kmh = MODE_AVG_SPEED_KMH.get(mode, 50)
    duration_sec = (dist_m / 1000 / speed_kmh) * 3600
    return dist_m, duration_sec


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
