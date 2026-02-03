"""
Simple Database Migration to Turso - Run from Streamlit Cloud
Migrates all tables and data from local SQLite to Turso cloud database
"""
import sqlite3
import os
from database_manager import get_database_connection

def migrate_local_to_turso():
    """Migrate local SQLite database to Turso"""
    
    print("=" * 60)
    print("DATABASE MIGRATION: Local SQLite -> Turso Cloud")
    print("=" * 60)
    
    # Connect to local database
    local_db_path = "database/risk_register.db"
    
    if not os.path.exists(local_db_path):
        print(f"❌ Local database not found: {local_db_path}")
        return False
    
    print(f"\n>> Reading from: {local_db_path}")
    local_conn = sqlite3.connect(local_db_path)
    local_cursor = local_conn.cursor()
    
    # Connect to Turso (via database_manager with USE_TURSO=true)
    print(f">> Connecting to Turso...")
    turso_conn = get_database_connection()
    turso_cursor = turso_conn.cursor()
    
    # Get all tables
    local_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in local_cursor.fetchall()]
    
    print(f"\n>> Found {len(tables)} tables to migrate")
    print("-" * 60)
    
    total_rows = 0
    
    for table in tables:
        print(f"\n>> Migrating table: {table}")
        
        # Get table schema
        local_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
        create_sql = local_cursor.fetchone()[0]
        
        # Create table in Turso (drop if exists)
        try:
            turso_cursor.execute(f"DROP TABLE IF EXISTS {table}")
            turso_cursor.execute(create_sql)
            print(f"  ✅ Created table structure")
        except Exception as e:
            print(f"  ⚠️ Table creation warning: {e}")
        
        # Get all data
        local_cursor.execute(f"SELECT * FROM {table}")
        rows = local_cursor.fetchall()
        
        if not rows:
            print(f"  ℹ️ No data to migrate")
            continue
        
        # Get column names
        local_cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in local_cursor.fetchall()]
        
        # Insert data
        placeholders = ",".join(["?" for _ in columns])
        insert_sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        
        migrated = 0
        failed = 0
        
        for row in rows:
            try:
                turso_cursor.execute(insert_sql, row)
                migrated += 1
            except Exception as e:
                failed += 1
                if failed <= 3:  # Show first 3 errors only
                    print(f"  ⚠️ Row error: {e}")
        
        total_rows += migrated
        print(f"  ✅ Migrated {migrated}/{len(rows)} rows" + (f" ({failed} failed)" if failed > 0 else ""))
    
    # Commit and close
    turso_conn.commit()
    local_conn.close()
    turso_conn.close()
    
    print("\n" + "=" * 60)
    print(f"✅ MIGRATION COMPLETED!")
    print(f">> Total rows migrated: {total_rows}")
    print(f">> Tables migrated: {len(tables)}")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    # Ensure USE_TURSO is set
    if os.getenv('USE_TURSO', 'false').lower() != 'true':
        print("❌ ERROR: USE_TURSO must be set to 'true' in .env file")
        print("Please update .env file: USE_TURSO=true")
        exit(1)
    
    success = migrate_local_to_turso()
    
    if success:
        print("\n✅ Migration successful! You can now use Turso database.")
        print("💡 Remember to set USE_TURSO=true in Streamlit Cloud secrets")
    else:
        print("\n❌ Migration failed. Check errors above.")
