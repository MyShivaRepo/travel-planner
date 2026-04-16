import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "/data/travel_planner.db")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn):
    """Ajoute les colonnes manquantes sans perdre de données."""
    cursor = conn.execute("PRAGMA table_info(travel_days)")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    for col, col_type in [("hotel_latitude", "REAL"), ("hotel_longitude", "REAL"),
                          ("restaurant_latitude", "REAL"), ("restaurant_longitude", "REAL"),
                          ("hotel_budget", "REAL"), ("restaurant_budget", "REAL")]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE travel_days ADD COLUMN {col} {col_type}")

    # Colonnes métriques sur segments
    cursor = conn.execute("PRAGMA table_info(segments)")
    existing_seg_cols = {row["name"] for row in cursor.fetchall()}
    # Legacy: ajouter colonnes en m/sec si besoin (pour anciennes bases)
    for col, col_type in [("distance_m", "REAL"), ("duration_sec", "REAL"), ("budget", "REAL")]:
        if col not in existing_seg_cols and existing_seg_cols:
            conn.execute(f"ALTER TABLE segments ADD COLUMN {col} {col_type}")
            existing_seg_cols.add(col)
    # Nouvelles colonnes en unités spec (km + heures)
    for col, col_type in [("distance_km", "REAL"), ("duration_h", "REAL")]:
        if col not in existing_seg_cols and existing_seg_cols:
            conn.execute(f"ALTER TABLE segments ADD COLUMN {col} {col_type}")
            existing_seg_cols.add(col)
    # Migration des données m/sec → km/h si non déjà fait
    rows = conn.execute(
        "SELECT id, distance_m, duration_sec, distance_km, duration_h FROM segments"
    ).fetchall()
    for r in rows:
        need_dist = r["distance_km"] is None and r["distance_m"] is not None
        need_dur = r["duration_h"] is None and r["duration_sec"] is not None
        if need_dist or need_dur:
            conn.execute(
                "UPDATE segments SET distance_km = ?, duration_h = ? WHERE id = ?",
                (
                    (r["distance_m"] / 1000.0) if need_dist else r["distance_km"],
                    (r["duration_sec"] / 3600.0) if need_dur else r["duration_h"],
                    r["id"],
                ),
            )

    # Colonne fournisseur_url sur activities
    cursor = conn.execute("PRAGMA table_info(activities)")
    existing_act_cols = {row["name"] for row in cursor.fetchall()}
    if existing_act_cols and "fournisseur_url" not in existing_act_cols:
        conn.execute("ALTER TABLE activities ADD COLUMN fournisseur_url TEXT")

    # Colonnes hotel_id et restaurant_id sur travel_days (pour relation à hotels/restaurants)
    cursor = conn.execute("PRAGMA table_info(travel_days)")
    td_cols = {row["name"] for row in cursor.fetchall()}
    if td_cols and "hotel_id" not in td_cols:
        conn.execute("ALTER TABLE travel_days ADD COLUMN hotel_id INTEGER")
    if td_cols and "restaurant_id" not in td_cols:
        conn.execute("ALTER TABLE travel_days ADD COLUMN restaurant_id INTEGER")

    # Ajout transport_mode dans travels
    cursor = conn.execute("PRAGMA table_info(travels)")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    if "transport_mode" not in existing_cols:
        conn.execute("ALTER TABLE travels ADD COLUMN transport_mode TEXT DEFAULT 'voiture'")

    # Multi-voyages : retirer UNIQUE sur destination_id, ajouter nom + created_at
    sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='travels'"
    ).fetchone()
    if sql_row and "UNIQUE" in sql_row["sql"].upper():
        # Recréer la table sans UNIQUE et avec les nouvelles colonnes
        conn.executescript("""
            PRAGMA foreign_keys = OFF;
            CREATE TABLE travels_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination_id INTEGER NOT NULL,
                transport_mode TEXT DEFAULT 'voiture',
                nom TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
            );
            INSERT INTO travels_new (id, destination_id, transport_mode)
                SELECT id, destination_id, transport_mode FROM travels;
            DROP TABLE travels;
            ALTER TABLE travels_new RENAME TO travels;
            PRAGMA foreign_keys = ON;
        """)
    else:
        cursor = conn.execute("PRAGMA table_info(travels)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        if "nom" not in existing_cols:
            conn.execute("ALTER TABLE travels ADD COLUMN nom TEXT")
        if "created_at" not in existing_cols:
            conn.execute("ALTER TABLE travels ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS destinations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('Pays', 'Région', 'Ville'))
            );

            CREATE TABLE IF NOT EXISTS pois (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination_id INTEGER NOT NULL,
                rang INTEGER NOT NULL,
                nom TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS travels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination_id INTEGER NOT NULL,
                transport_mode TEXT DEFAULT 'voiture',
                nom TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS travel_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                travel_id INTEGER NOT NULL,
                numero INTEGER NOT NULL,
                hotel_nom TEXT,
                hotel_adresse TEXT,
                hotel_latitude REAL,
                hotel_longitude REAL,
                hotel_budget REAL,
                restaurant_nom TEXT,
                restaurant_adresse TEXT,
                restaurant_latitude REAL,
                restaurant_longitude REAL,
                restaurant_budget REAL,
                FOREIGN KEY (travel_id) REFERENCES travels(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS travel_day_pois (
                day_id INTEGER NOT NULL,
                poi_id INTEGER NOT NULL,
                PRIMARY KEY (day_id, poi_id),
                FOREIGN KEY (day_id) REFERENCES travel_days(id) ON DELETE CASCADE,
                FOREIGN KEY (poi_id) REFERENCES pois(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_id INTEGER NOT NULL,
                ordre INTEGER NOT NULL,
                from_name TEXT,
                from_latitude REAL,
                from_longitude REAL,
                to_name TEXT,
                to_latitude REAL,
                to_longitude REAL,
                transport_mode TEXT NOT NULL DEFAULT 'voiture',
                distance_km REAL,
                duration_h REAL,
                budget REAL,
                FOREIGN KEY (day_id) REFERENCES travel_days(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination_id INTEGER NOT NULL,
                rang INTEGER NOT NULL,
                nom TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                fournisseur_url TEXT,
                FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS travel_day_activities (
                day_id INTEGER NOT NULL,
                activity_id INTEGER NOT NULL,
                PRIMARY KEY (day_id, activity_id),
                FOREIGN KEY (day_id) REFERENCES travel_days(id) ON DELETE CASCADE,
                FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS hotels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination_id INTEGER NOT NULL,
                nom TEXT NOT NULL,
                adresse TEXT,
                latitude REAL,
                longitude REAL,
                budget REAL,
                FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS restaurants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination_id INTEGER NOT NULL,
                nom TEXT NOT NULL,
                adresse TEXT,
                latitude REAL,
                longitude REAL,
                budget REAL,
                FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
            );
        """)
        _migrate(conn)


# ── Settings ─────────────────────────────────────────────────────────────────

def get_setting(key):
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key, value):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# ── Destinations CRUD ────────────────────────────────────────────────────────

def get_all_destinations():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM destinations ORDER BY id").fetchall()]


def get_destination(dest_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM destinations WHERE id = ?", (dest_id,)).fetchone()
        return dict(row) if row else None


def create_destination(nom, type_dest):
    with get_db() as conn:
        cur = conn.execute("INSERT INTO destinations (nom, type) VALUES (?, ?)", (nom, type_dest))
        return cur.lastrowid


def delete_destination(dest_id):
    with get_db() as conn:
        conn.execute("DELETE FROM destinations WHERE id = ?", (dest_id,))


# ── POI CRUD ─────────────────────────────────────────────────────────────────

def get_pois_for_destination(dest_id):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pois WHERE destination_id = ? ORDER BY rang", (dest_id,)
        ).fetchall()]


def create_poi(destination_id, rang, nom, type_poi, description, latitude, longitude):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO pois (destination_id, rang, nom, type, description, latitude, longitude) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (destination_id, rang, nom, type_poi, description, latitude, longitude),
        )
        return cur.lastrowid


def update_poi(poi_id, rang, nom, type_poi, description, latitude, longitude):
    with get_db() as conn:
        conn.execute(
            "UPDATE pois SET rang=?, nom=?, type=?, description=?, latitude=?, longitude=? WHERE id=?",
            (rang, nom, type_poi, description, latitude, longitude, poi_id),
        )


def delete_poi(poi_id):
    with get_db() as conn:
        row = conn.execute("SELECT destination_id FROM pois WHERE id = ?", (poi_id,)).fetchone()
        dest_id = row["destination_id"] if row else None
        conn.execute("DELETE FROM pois WHERE id = ?", (poi_id,))
    if dest_id is not None:
        renumber_pois(dest_id)


def renumber_pois(destination_id):
    """Renumérote les rangs des POIs de 1 à N, en préservant l'ordre."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id FROM pois WHERE destination_id = ? ORDER BY rang, id",
            (destination_id,),
        ).fetchall()
        for idx, r in enumerate(rows, start=1):
            conn.execute("UPDATE pois SET rang = ? WHERE id = ?", (idx, r["id"]))


def bulk_create_pois(destination_id, pois_list):
    with get_db() as conn:
        conn.executemany(
            "INSERT INTO pois (destination_id, rang, nom, type, description, latitude, longitude) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(destination_id, p["rang"], p["nom"], p["type"], p["description"],
              p["latitude"], p["longitude"]) for p in pois_list],
        )


# ── Activity CRUD ────────────────────────────────────────────────────────────

def get_activities_for_destination(dest_id):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM activities WHERE destination_id = ? ORDER BY rang", (dest_id,)
        ).fetchall()]


def create_activity(destination_id, rang, nom, type_act, description, latitude, longitude, fournisseur_url=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO activities (destination_id, rang, nom, type, description, latitude, longitude, fournisseur_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (destination_id, rang, nom, type_act, description, latitude, longitude, fournisseur_url),
        )
        return cur.lastrowid


def update_activity(activity_id, rang, nom, type_act, description, latitude, longitude, fournisseur_url=None):
    with get_db() as conn:
        conn.execute(
            "UPDATE activities SET rang=?, nom=?, type=?, description=?, latitude=?, longitude=?, fournisseur_url=? WHERE id=?",
            (rang, nom, type_act, description, latitude, longitude, fournisseur_url, activity_id),
        )


def delete_activity(activity_id):
    with get_db() as conn:
        row = conn.execute("SELECT destination_id FROM activities WHERE id = ?", (activity_id,)).fetchone()
        dest_id = row["destination_id"] if row else None
        conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
    if dest_id is not None:
        renumber_activities(dest_id)


def renumber_activities(destination_id):
    """Renumérote les rangs des activités de 1 à N, en préservant l'ordre."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id FROM activities WHERE destination_id = ? ORDER BY rang, id",
            (destination_id,),
        ).fetchall()
        for idx, r in enumerate(rows, start=1):
            conn.execute("UPDATE activities SET rang = ? WHERE id = ?", (idx, r["id"]))


def bulk_create_activities(destination_id, activities_list):
    with get_db() as conn:
        conn.executemany(
            "INSERT INTO activities (destination_id, rang, nom, type, description, latitude, longitude, fournisseur_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(destination_id, a["rang"], a["nom"], a["type"], a.get("description", ""),
              a["latitude"], a["longitude"], a.get("fournisseur_url")) for a in activities_list],
        )


# ── Hôtel / Restaurant CRUD (avec déduplication par nom + destination) ──────

def get_or_create_hotel(destination_id, nom, adresse=None, latitude=None, longitude=None, budget=None):
    """Crée un hôtel ou retourne son id s'il existe déjà (même nom + destination)."""
    if not nom:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM hotels WHERE destination_id = ? AND nom = ?",
            (destination_id, nom),
        ).fetchone()
        if row:
            # Mise à jour optionnelle des attributs manquants (p.ex. si un autre jour a plus d'info)
            conn.execute(
                "UPDATE hotels SET adresse = COALESCE(?, adresse), "
                "latitude = COALESCE(?, latitude), longitude = COALESCE(?, longitude), "
                "budget = COALESCE(?, budget) WHERE id = ?",
                (adresse, latitude, longitude, budget, row["id"]),
            )
            return row["id"]
        cur = conn.execute(
            "INSERT INTO hotels (destination_id, nom, adresse, latitude, longitude, budget) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (destination_id, nom, adresse, latitude, longitude, budget),
        )
        return cur.lastrowid


def get_or_create_restaurant(destination_id, nom, adresse=None, latitude=None, longitude=None, budget=None):
    """Crée un restaurant ou retourne son id s'il existe déjà (même nom + destination)."""
    if not nom:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM restaurants WHERE destination_id = ? AND nom = ?",
            (destination_id, nom),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE restaurants SET adresse = COALESCE(?, adresse), "
                "latitude = COALESCE(?, latitude), longitude = COALESCE(?, longitude), "
                "budget = COALESCE(?, budget) WHERE id = ?",
                (adresse, latitude, longitude, budget, row["id"]),
            )
            return row["id"]
        cur = conn.execute(
            "INSERT INTO restaurants (destination_id, nom, adresse, latitude, longitude, budget) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (destination_id, nom, adresse, latitude, longitude, budget),
        )
        return cur.lastrowid


def get_hotel(hotel_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM hotels WHERE id = ?", (hotel_id,)).fetchone()
        return dict(row) if row else None


def get_restaurant(restaurant_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)).fetchone()
        return dict(row) if row else None


# ── Travel CRUD ──────────────────────────────────────────────────────────────

def save_travel(destination_id, days, transport_mode="voiture", nom=None):
    """Crée un voyage (remplace le précédent pour la destination). Retourne son id.

    Une destination a au plus 1 voyage (relation 1-1) : les anciens sont supprimés.
    Les hôtels et restaurants sont déduplicqués au sein de la destination : un même
    hôtel/restaurant référencé par plusieurs jours n'est stocké qu'une seule fois.
    """
    with get_db() as conn:
        conn.execute("DELETE FROM travels WHERE destination_id = ?", (destination_id,))
        # Nettoyer les hôtels/restaurants de cette destination (on les recrée avec le nouveau voyage)
        conn.execute("DELETE FROM hotels WHERE destination_id = ?", (destination_id,))
        conn.execute("DELETE FROM restaurants WHERE destination_id = ?", (destination_id,))
        cur = conn.execute(
            "INSERT INTO travels (destination_id, transport_mode, nom) VALUES (?, ?, ?)",
            (destination_id, transport_mode, nom),
        )
        travel_id = cur.lastrowid
        for day in days:
            # Créer ou récupérer l'hôtel (dédupliqué par nom au sein de la destination)
            hotel_id = None
            if day.get("hotel_nom"):
                row = conn.execute(
                    "SELECT id FROM hotels WHERE destination_id = ? AND nom = ?",
                    (destination_id, day["hotel_nom"]),
                ).fetchone()
                if row:
                    hotel_id = row["id"]
                else:
                    hcur = conn.execute(
                        "INSERT INTO hotels (destination_id, nom, adresse, latitude, longitude, budget) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (destination_id, day["hotel_nom"], day.get("hotel_adresse"),
                         day.get("hotel_latitude"), day.get("hotel_longitude"), day.get("hotel_budget")),
                    )
                    hotel_id = hcur.lastrowid

            restaurant_id = None
            if day.get("restaurant_nom"):
                row = conn.execute(
                    "SELECT id FROM restaurants WHERE destination_id = ? AND nom = ?",
                    (destination_id, day["restaurant_nom"]),
                ).fetchone()
                if row:
                    restaurant_id = row["id"]
                else:
                    rcur = conn.execute(
                        "INSERT INTO restaurants (destination_id, nom, adresse, latitude, longitude, budget) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (destination_id, day["restaurant_nom"], day.get("restaurant_adresse"),
                         day.get("restaurant_latitude"), day.get("restaurant_longitude"), day.get("restaurant_budget")),
                    )
                    restaurant_id = rcur.lastrowid

            day_cur = conn.execute(
                "INSERT INTO travel_days (travel_id, numero, hotel_id, restaurant_id, "
                "hotel_nom, hotel_adresse, hotel_latitude, hotel_longitude, hotel_budget, "
                "restaurant_nom, restaurant_adresse, restaurant_latitude, restaurant_longitude, restaurant_budget) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (travel_id, day["numero"], hotel_id, restaurant_id,
                 day.get("hotel_nom"), day.get("hotel_adresse"),
                 day.get("hotel_latitude"), day.get("hotel_longitude"), day.get("hotel_budget"),
                 day.get("restaurant_nom"), day.get("restaurant_adresse"),
                 day.get("restaurant_latitude"), day.get("restaurant_longitude"),
                 day.get("restaurant_budget")),
            )
            day_id = day_cur.lastrowid
            for poi_id in day.get("poi_ids", []):
                conn.execute(
                    "INSERT INTO travel_day_pois (day_id, poi_id) VALUES (?, ?)",
                    (day_id, poi_id),
                )
            for act_id in day.get("activity_ids", []):
                conn.execute(
                    "INSERT INTO travel_day_activities (day_id, activity_id) VALUES (?, ?)",
                    (day_id, act_id),
                )
            for idx, seg in enumerate(day.get("segments", [])):
                conn.execute(
                    "INSERT INTO segments (day_id, ordre, from_name, from_latitude, from_longitude, "
                    "to_name, to_latitude, to_longitude, transport_mode, "
                    "distance_km, duration_h, budget) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (day_id, idx,
                     seg.get("from_name"), seg.get("from_latitude"), seg.get("from_longitude"),
                     seg.get("to_name"), seg.get("to_latitude"), seg.get("to_longitude"),
                     seg.get("transport_mode", transport_mode),
                     seg.get("distance_km"), seg.get("duration_h"), seg.get("budget")),
                )
        return travel_id


def list_travels(destination_id):
    """Liste tous les voyages d'une destination, du plus récent au plus ancien."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, nom, transport_mode, created_at FROM travels "
            "WHERE destination_id = ? ORDER BY id DESC",
            (destination_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_travel(travel_id):
    with get_db() as conn:
        conn.execute("DELETE FROM travels WHERE id = ?", (travel_id,))


def get_travel_by_id(travel_id):
    with get_db() as conn:
        travel = conn.execute(
            "SELECT id, destination_id, transport_mode, nom, created_at FROM travels WHERE id = ?",
            (travel_id,),
        ).fetchone()
        if not travel:
            return None
        travel_id = travel["id"]
        days_rows = conn.execute(
            "SELECT * FROM travel_days WHERE travel_id = ? ORDER BY numero", (travel_id,)
        ).fetchall()
        days = []
        for dr in days_rows:
            day = dict(dr)
            poi_rows = conn.execute(
                "SELECT p.* FROM pois p JOIN travel_day_pois tdp ON p.id = tdp.poi_id "
                "WHERE tdp.day_id = ? ORDER BY p.rang",
                (day["id"],),
            ).fetchall()
            day["pois"] = [dict(pr) for pr in poi_rows]
            act_rows = conn.execute(
                "SELECT a.* FROM activities a JOIN travel_day_activities tda ON a.id = tda.activity_id "
                "WHERE tda.day_id = ? ORDER BY a.rang",
                (day["id"],),
            ).fetchall()
            day["activities"] = [dict(ar) for ar in act_rows]
            seg_rows = conn.execute(
                "SELECT * FROM segments WHERE day_id = ? ORDER BY ordre",
                (day["id"],),
            ).fetchall()
            day["segments"] = [dict(s) for s in seg_rows]
            days.append(day)
        return {
            "id": travel["id"],
            "destination_id": travel["destination_id"],
            "days": days,
            "transport_mode": travel["transport_mode"] or "voiture",
            "nom": travel["nom"],
            "created_at": travel["created_at"],
        }


def update_segment_mode(segment_id, transport_mode, distance_km=None, duration_h=None):
    with get_db() as conn:
        conn.execute(
            "UPDATE segments SET transport_mode = ?, distance_km = ?, duration_h = ? WHERE id = ?",
            (transport_mode, distance_km, duration_h, segment_id),
        )


def get_segment(segment_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
        return dict(row) if row else None
