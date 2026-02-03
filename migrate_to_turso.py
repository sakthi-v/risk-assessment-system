"""
Database Migration Script: Local SQLite → Turso Cloud
Migrates all data from local database/risk_register.db to Turso
"""

import sqlite3
import json
from dotenv import load_dotenv
import os
import asyncio

# Load environment variables
load_dotenv()

async def migrate_to_turso():
    """Migrate all data from local SQLite to Turso"""
    
    print("🔄 Starting migration from Local SQLite to Turso...")
    
    # Import Turso client
    try:
        from libsql_client import create_client
    except ImportError:
        print("❌ Error: libsql-client not installed")
        print("Run: pip install libsql-client")
        return False
    
    # Get Turso credentials
    turso_url = os.getenv('TURSO_DATABASE_URL')
    turso_token = os.getenv('TURSO_AUTH_TOKEN')
    
    if not turso_url or not turso_token:
        print("❌ Error: Turso credentials not found in .env")
        print("Required: TURSO_DATABASE_URL and TURSO_AUTH_TOKEN")
        return False
    
    # Connect to local database
    local_db = 'database/risk_register.db'
    if not os.path.exists(local_db):
        print(f"❌ Error: Local database not found at {local_db}")
        return False
    
    local_conn = sqlite3.connect(local_db)
    local_conn.row_factory = sqlite3.Row
    local_cursor = local_conn.cursor()
    
    # Connect to Turso
    print("📡 Connecting to Turso...")
    turso_client = create_client(url=turso_url, auth_token=turso_token)
    
    try:
        # Get all table names
        local_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in local_cursor.fetchall()]
        
        print(f"📋 Found {len(tables)} tables to migrate: {', '.join(tables)}")
        
        for table_name in tables:
            print(f"\n🔄 Migrating table: {table_name}")
            
            # Get table schema
            local_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            create_sql = local_cursor.fetchone()[0]
            
            # Create table in Turso
            print(f"  ✓ Creating table structure...")
            await turso_client.execute(create_sql)
            
            # Get all data
            local_cursor.execute(f"SELECT * FROM {table_name}")
            rows = local_cursor.fetchall()
            
            if not rows:
                print(f"  ℹ️ No data in {table_name}")
                continue
            
            print(f"  📦 Migrating {len(rows)} rows...")
            
            # Get column names
            columns = [description[0] for description in local_cursor.description]
            placeholders = ','.join(['?' for _ in columns])
            insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
            
            # Insert data in batches
            migrated = 0
            for row in rows:
                try:
                    await turso_client.execute(insert_sql, list(row))
                    migrated += 1
                except Exception as e:
                    print(f"  ⚠️ Warning: Failed to insert row: {e}")
            
            print(f"  ✅ Migrated {migrated}/{len(rows)} rows")
        
        print("\n✅ Migration completed successfully!")
        print("\n📝 Next steps:")
        print("1. Verify data in Turso dashboard: https://turso.tech/app")
        print("2. Update .env: Set USE_TURSO=true")
        print("3. Test locally: streamlit run main_app.py")
        print("4. Deploy to Streamlit Cloud when ready")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        local_conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE MIGRATION: Local SQLite → Turso Cloud")
    print("=" * 60)
    
    confirm = input("\n⚠️ This will copy ALL data to Turso. Continue? (yes/no): ")
    
    if confirm.lower() == 'yes':
        success = asyncio.run(migrate_to_turso())
        if success:
            print("\n🎉 Migration successful!")
        else:
            print("\n❌ Migration failed. Check errors above.")
    else:
        print("❌ Migration cancelled.")
