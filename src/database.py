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
                destination_id INTEGER NOT NULL UNIQUE,
                FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS travel_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                travel_id INTEGER NOT NULL,
                numero INTEGER NOT NULL,
                hotel_nom TEXT,
                hotel_adresse TEXT,
                restaurant_nom TEXT,
                restaurant_adresse TEXT,
                FOREIGN KEY (travel_id) REFERENCES travels(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS travel_day_pois (
                day_id INTEGER NOT NULL,
                poi_id INTEGER NOT NULL,
                PRIMARY KEY (day_id, poi_id),
                FOREIGN KEY (day_id) REFERENCES travel_days(id) ON DELETE CASCADE,
                FOREIGN KEY (poi_id) REFERENCES pois(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)


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

def save_travel(destination_id, days):
    with get_db() as conn:
        conn.execute("DELETE FROM travels WHERE destination_id = ?", (destination_id,))
        cur = conn.execute("INSERT INTO travels (destination_id) VALUES (?)", (destination_id,))
        travel_id = cur.lastrowid
        for day in days:
            day_cur = conn.execute(
                "INSERT INTO travel_days (travel_id, numero, hotel_nom, hotel_adresse, "
                "restaurant_nom, restaurant_adresse) VALUES (?, ?, ?, ?, ?, ?)",
                (travel_id, day["numero"], day.get("hotel_nom"), day.get("hotel_adresse"),
                 day.get("restaurant_nom"), day.get("restaurant_adresse")),
            )
            day_id = day_cur.lastrowid
            for poi_id in day.get("poi_ids", []):
                conn.execute(
                    "INSERT INTO travel_day_pois (day_id, poi_id) VALUES (?, ?)",
                    (day_id, poi_id),
                )


def get_travel(destination_id):
    with get_db() as conn:
        travel = conn.execute(
            "SELECT id FROM travels WHERE destination_id = ?", (destination_id,)
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
            days.append(day)
        return days
