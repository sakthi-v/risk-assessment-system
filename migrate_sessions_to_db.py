"""
Migrate old session files to database
Run this once to import all existing sessions from files to database
"""

import json
from pathlib import Path
from database_manager import get_database_connection

def migrate_sessions_to_database():
    """Migrate all session JSON files to database"""
    
    sessions_dir = Path("sessions")
    
    if not sessions_dir.exists():
        print("❌ No sessions folder found")
        return
    
    # Get all session files
    session_files = list(sessions_dir.glob("session_*.json"))
    
    if not session_files:
        print("❌ No session files found")
        return
    
    print(f"Found {len(session_files)} session files")
    
    # Create sessions table if not exists
    conn = get_database_connection()
    cursor = conn.cursor()
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
    
    # Migrate each file
    migrated = 0
    skipped = 0
    
    for session_file in session_files:
        try:
            # Read session file
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            session_name = session_file.stem  # filename without .json
            
            # Insert into database
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (session_name, session_data, updated_date)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (session_name, json.dumps(session_data, ensure_ascii=False)))
            
            migrated += 1
            print(f"Migrated: {session_name}")
            
        except Exception as e:
            print(f"Skipped {session_file.name}: {e}")
            skipped += 1
    
    conn.commit()
    conn.close()
    
    print(f"\nMigration complete!")
    print(f"Migrated: {migrated} sessions")
    print(f"Skipped: {skipped} sessions")
    print(f"\nOld files are still in sessions/ folder (safe to delete after verification)")

if __name__ == "__main__":
    print("=" * 60)
    print("SESSION MIGRATION: Files to Database")
    print("=" * 60)
    migrate_sessions_to_database()
