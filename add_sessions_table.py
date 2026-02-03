"""
Add sessions table to database for permanent session storage
Run this once to create the table
"""

import sqlite3
import os
from database_manager import get_database_connection

def add_sessions_table():
    """Add sessions table to store session data permanently"""
    
    conn = get_database_connection()
    cursor = conn.cursor()
    
    # Create sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT UNIQUE NOT NULL,
            session_data TEXT NOT NULL,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    
    print("✅ Sessions table created successfully!")

if __name__ == "__main__":
    add_sessions_table()
