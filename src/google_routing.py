"""Module de routage via Google Maps Directions API pour les transports publics.

Supporte : métro, train, bus, tramway, walking, bicycling, driving.
"""
import math
import requests

GMAPS_BASE_URL = "https://maps.googleapis.com/maps/api/directions/json"

# Mapping mode (app) → paramètres Google Directions
MODE_TO_GMAPS = {
    "métro":   {"mode": "transit", "transit_mode": "subway"},
    "train":   {"mode": "transit", "transit_mode": "train|rail"},
    "bus":     {"mode": "transit", "transit_mode": "bus"},
}


def _decode_polyline(encoded):
    """Décode un polyline Google Maps en liste de [lat, lon]."""
    points = []
    index = 0
    lat = 0
    lng = 0
    while index < len(encoded):
        result = 0
        shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        result = 0
        shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        points.append([lat / 1e5, lng / 1e5])
    return points


def get_transit_route(coords, transport_mode, api_key, timeout=10):
    """
    Calcule le tracé transit (métro/train/bus) entre 2 points via Google Maps.

    Args:
        coords: liste de [lat, lon] (exactement 2 points : origin, destination)
        transport_mode: "métro", "train" ou "bus"
        api_key: clé API Google Maps
    Returns:
        dict {geometry, duration, distance} ou None.
    """
    if not api_key or len(coords) < 2 or transport_mode not in MODE_TO_GMAPS:
        return None

    params_mode = MODE_TO_GMAPS[transport_mode]
    params = {
        "origin": f"{coords[0][0]},{coords[0][1]}",
        "destination": f"{coords[-1][0]},{coords[-1][1]}",
        "mode": params_mode["mode"],
        "key": api_key,
    }
    if "transit_mode" in params_mode:
        params["transit_mode"] = params_mode["transit_mode"]

    try:
        resp = requests.get(GMAPS_BASE_URL, params=params, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("status") != "OK":
            return None
        route = data["routes"][0]
        leg = route["legs"][0]
        geom = _decode_polyline(route["overview_polyline"]["points"])
        return {
            "geometry": geom,
            "duration": leg["duration"]["value"],  # secondes
            "distance": leg["distance"]["value"],  # mètres
        }
    except Exception:
        return None


def test_gmaps_key(api_key):
    """Test simple : Paris → Lyon en train."""
    try:
        result = get_transit_route(
            [(48.8566, 2.3522), (45.7640, 4.8357)],
            "train", api_key,
        )
        if result:
            return True, "Clé Google Maps valide."
        # Essayer avec une requête plus basique pour distinguer clé invalide vs pas de transit disponible
        resp = requests.get(
            GMAPS_BASE_URL,
            params={
                "origin": "48.8566,2.3522", "destination": "45.7640,4.8357",
                "mode": "driving", "key": api_key,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "REQUEST_DENIED":
            return False, f"Clé refusée : {data.get('error_message', '')}"
        if data.get("status") == "OK":
            return True, "Clé valide (mais transit indisponible sur ce trajet test)."
        return False, f"Réponse inattendue : {data.get('status')}"
    except Exception as e:
        return False, f"Erreur : {e}"


# ── Great-circle pour avion ──────────────────────────────────────────────────

EARTH_RADIUS_KM = 6371.0
AVG_PLANE_SPEED_KMH = 800.0


def _haversine_km(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def great_circle_route(coords, n_points=60):
    """
    Calcule un tracé great-circle entre 2 points (utile pour avion).

    Args:
        coords: [(lat1, lon1), (lat2, lon2)]
        n_points: nombre de points intermédiaires

    Returns:
        dict {geometry, duration, distance} avec distance en mètres,
        duration estimée à la vitesse avion moyenne (~800 km/h).
    """
    if len(coords) < 2:
        return None
    lat1, lon1 = coords[0]
    lat2, lon2 = coords[-1]

    d_km = _haversine_km(lat1, lon1, lat2, lon2)
    if d_km < 0.01:
        return None

    # Interpolation sphérique (slerp)
    phi1, lam1 = math.radians(lat1), math.radians(lon1)
    phi2, lam2 = math.radians(lat2), math.radians(lon2)
    d_rad = d_km / EARTH_RADIUS_KM

    geometry = []
    for i in range(n_points + 1):
        f = i / n_points
        if d_rad == 0:
            geometry.append([lat1, lon1])
            continue
        a = math.sin((1 - f) * d_rad) / math.sin(d_rad)
        b = math.sin(f * d_rad) / math.sin(d_rad)
        x = a * math.cos(phi1) * math.cos(lam1) + b * math.cos(phi2) * math.cos(lam2)
        y = a * math.cos(phi1) * math.sin(lam1) + b * math.cos(phi2) * math.sin(lam2)
        z = a * math.sin(phi1) + b * math.sin(phi2)
        lat = math.degrees(math.atan2(z, math.sqrt(x * x + y * y)))
        lon = math.degrees(math.atan2(y, x))
        geometry.append([lat, lon])

    duration_sec = (d_km / AVG_PLANE_SPEED_KMH) * 3600
    return {
        "geometry": geometry,
        "duration": duration_sec,
        "distance": d_km * 1000,
    }
