"""
Cloud Migration Script - Run this from Streamlit Cloud to migrate local data to Turso
"""
import sqlite3
import libsql_client
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def migrate_to_turso():
    """Migrate local SQLite database to Turso cloud database"""
    
    # Connect to Turso
    turso_url = os.getenv("TURSO_DATABASE_URL")
    turso_token = os.getenv("TURSO_AUTH_TOKEN")
    
    print(f"Connecting to Turso: {turso_url}")
    turso_client = libsql_client.create_client(url=turso_url, auth_token=turso_token)
    
    # Local database path
    local_db = "database/risk_register.db"
    
    if not os.path.exists(local_db):
        print(f"❌ Local database not found: {local_db}")
        return
    
    local_conn = sqlite3.connect(local_db)
    local_cursor = local_conn.cursor()
    
    print("\n📊 Starting migration...\n")
    
    # Get all tables
    local_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in local_cursor.fetchall()]
    
    for table in tables:
        print(f"📋 Migrating table: {table}")
        
        # Get table schema
        local_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
        create_sql = local_cursor.fetchone()[0]
        
        # Create table in Turso
        try:
            await turso_client.execute(f"DROP TABLE IF EXISTS {table}")
            await turso_client.execute(create_sql)
            print(f"  ✅ Created table structure")
        except Exception as e:
            print(f"  ⚠️ Table creation: {e}")
        
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
        for row in rows:
            try:
                await turso_client.execute(insert_sql, list(row))
                migrated += 1
            except Exception as e:
                print(f"  ⚠️ Row error: {e}")
        
        print(f"  ✅ Migrated {migrated}/{len(rows)} rows\n")
    
    local_conn.close()
    print("✅ Migration completed!")

if __name__ == "__main__":
    asyncio.run(migrate_to_turso())
