import sqlite3
import pandas as pd
from datetime import datetime
import os

class EHRManager:
    def __init__(self, db_path="nebula_records.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Creates the database and table if they don't exist."""
        # Check if DB exists, if not, it will be created
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        # Create the table for storing vitals
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vitals_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bed_id TEXT,
                timestamp DATETIME,
                hr INTEGER,
                spo2 INTEGER,
                bp TEXT,
                temp REAL,
                news_score INTEGER,
                status TEXT
            )
        ''')
        
        # Create an index to make loading graphs faster
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_bed_id ON vitals_log (bed_id);
        ''')
        
        conn.commit()
        conn.close()

    def log_vitals(self, bed_id, hr, spo2, bp, temp, score, status):
        """Saves a new reading to the database."""
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO vitals_log (bed_id, timestamp, hr, spo2, bp, temp, news_score, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (bed_id, datetime.now(), hr, spo2, bp, temp, score, status))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"EHR Save Error: {e}")

    def get_patient_history(self, bed_id):
        """Retrieves all recorded vitals for a specific bed."""
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            # Get the last 50 records so the graph doesn't get too crowded
            query = "SELECT * FROM vitals_log WHERE bed_id = ? ORDER BY timestamp DESC LIMIT 50"
            df = pd.read_sql_query(query, conn, params=(bed_id,))
            conn.close()
            return df
        except Exception as e:
            print(f"EHR Retrieval Error: {e}")
            return pd.DataFrame()