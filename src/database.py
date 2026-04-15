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
    for col, col_type in [("distance_m", "REAL"), ("duration_sec", "REAL"), ("budget", "REAL")]:
        if col not in existing_seg_cols and existing_seg_cols:
            conn.execute(f"ALTER TABLE segments ADD COLUMN {col} {col_type}")

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
                distance_m REAL,
                duration_sec REAL,
                budget REAL,
                FOREIGN KEY (day_id) REFERENCES travel_days(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
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
        conn.execute("DELETE FROM pois WHERE id = ?", (poi_id,))


def bulk_create_pois(destination_id, pois_list):
    with get_db() as conn:
        conn.executemany(
            "INSERT INTO pois (destination_id, rang, nom, type, description, latitude, longitude) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(destination_id, p["rang"], p["nom"], p["type"], p["description"],
              p["latitude"], p["longitude"]) for p in pois_list],
        )


# ── Travel CRUD ──────────────────────────────────────────────────────────────

def save_travel(destination_id, days, transport_mode="voiture", nom=None):
    """Crée un voyage (remplace le précédent pour la destination). Retourne son id.

    Une destination a au plus 1 voyage (relation 1-1) : les anciens sont supprimés.
    """
    with get_db() as conn:
        conn.execute("DELETE FROM travels WHERE destination_id = ?", (destination_id,))
        cur = conn.execute(
            "INSERT INTO travels (destination_id, transport_mode, nom) VALUES (?, ?, ?)",
            (destination_id, transport_mode, nom),
        )
        travel_id = cur.lastrowid
        for day in days:
            day_cur = conn.execute(
                "INSERT INTO travel_days (travel_id, numero, hotel_nom, hotel_adresse, "
                "hotel_latitude, hotel_longitude, hotel_budget, "
                "restaurant_nom, restaurant_adresse, restaurant_latitude, restaurant_longitude, restaurant_budget) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (travel_id, day["numero"], day.get("hotel_nom"), day.get("hotel_adresse"),
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
            for idx, seg in enumerate(day.get("segments", [])):
                conn.execute(
                    "INSERT INTO segments (day_id, ordre, from_name, from_latitude, from_longitude, "
                    "to_name, to_latitude, to_longitude, transport_mode, "
                    "distance_m, duration_sec, budget) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (day_id, idx,
                     seg.get("from_name"), seg.get("from_latitude"), seg.get("from_longitude"),
                     seg.get("to_name"), seg.get("to_latitude"), seg.get("to_longitude"),
                     seg.get("transport_mode", transport_mode),
                     seg.get("distance_m"), seg.get("duration_sec"), seg.get("budget")),
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


def update_segment_mode(segment_id, transport_mode, distance_m=None, duration_sec=None):
    with get_db() as conn:
        conn.execute(
            "UPDATE segments SET transport_mode = ?, distance_m = ?, duration_sec = ? WHERE id = ?",
            (transport_mode, distance_m, duration_sec, segment_id),
        )


def get_segment(segment_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
        return dict(row) if row else None
