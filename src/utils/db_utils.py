import sqlite3
import os
from contextlib import contextmanager

class MetadataDB:
    def __init__(self, db_path="data/measurement_catalog.db"):
        self.db_path = db_path
        # Ordner erstellen, falls nicht vorhanden
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Erlaubt Zugriff auf Spalten per Name
        try:
            yield conn
        finally:
            conn.commit()
            conn.close()

    def _init_db(self):
        """Erstellt die Tabelle, falls sie noch nicht existiert."""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    folder_path TEXT NOT NULL UNIQUE,
                    duration_sec REAL,
                    vpp_max REAL,
                    rms_mean REAL,
                    thd_mean REAL,
                    comment TEXT
                )
            ''')

    def add_measurement(self, timestamp, folder_path, duration_sec, vpp_max, rms_mean, thd_mean, comment):
        """Fügt einen neuen Datensatz hinzu."""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO measurements 
                (timestamp, folder_path, duration_sec, vpp_max, rms_mean, thd_mean, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, folder_path, duration_sec, vpp_max, rms_mean, thd_mean, comment))

    def search_measurements(self, search_term=""):
        """Sucht nach Messungen (Datum oder Kommentar)."""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM measurements 
                WHERE comment LIKE ? OR timestamp LIKE ?
                ORDER BY timestamp DESC
            ''', (f'%{search_term}%', f'%{search_term}%'))
            return cursor.fetchall()