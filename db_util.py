# db_util.py

import sqlite3
import os

# Constants
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cloudflare_manager.db')

def setup_database():
    """Initialize the database and set up tables if they don't exist."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Create zones table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zones (
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT,
            type TEXT,
            plan_name TEXT,
            name_servers TEXT,
            original_name_servers TEXT,
            created_on TEXT,
            modified_on TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            auth_code_from_directnic TEXT
        )
    ''')

    # Create table to track the database version and add the 'last_updated' column
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS db_version (
            version INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Check if there's a version in the db_version table; if not, insert version 1
    cursor.execute('SELECT COUNT(*) FROM db_version')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO db_version (version) VALUES (1)')

    conn.commit()
    conn.close()

def get_database_connection():
    """Get a connection to the SQLite database."""
    return sqlite3.connect(DATABASE_PATH)
