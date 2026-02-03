"""
Alternative Migration Script - Uses HTTP instead of WebSocket
Try this if WebSocket gives 505 errors
"""
import sqlite3
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def migrate_via_http():
    """Migrate using Turso HTTP API instead of WebSocket"""
    
    print("=" * 60)
    print("DATABASE MIGRATION: Local SQLite -> Turso Cloud (HTTP)")
    print("=" * 60)
    
    # Get Turso credentials
    turso_url = os.getenv("TURSO_DATABASE_URL")
    turso_token = os.getenv("TURSO_AUTH_TOKEN")
    
    # Convert wss:// to https://
    http_url = turso_url.replace("libsql://", "https://").replace(":443", "")
    
    print(f"\n>> Connecting to: {http_url}")
    
    # Connect to local database
    local_db = "database/risk_register.db"
    if not os.path.exists(local_db):
        print(f"ERROR: {local_db} not found!")
        return False
    
    local_conn = sqlite3.connect(local_db)
    local_cursor = local_conn.cursor()
    
    # Get all tables
    local_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in local_cursor.fetchall()]
    
    print(f"\n>> Found {len(tables)} tables to migrate")
    print("-" * 60)
    
    headers = {
        "Authorization": f"Bearer {turso_token}",
        "Content-Type": "application/json"
    }
    
    total_rows = 0
    
    for table in tables:
        print(f"\n>> Migrating table: {table}")
        
        # Get table schema
        local_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
        create_sql = local_cursor.fetchone()[0]
        
        # Drop and create table via HTTP
        try:
            # Drop table
            drop_payload = {
                "statements": [f"DROP TABLE IF EXISTS {table}"]
            }
            response = requests.post(f"{http_url}/v2/pipeline", headers=headers, json=drop_payload, timeout=30)
            
            # Create table
            create_payload = {
                "statements": [create_sql]
            }
            response = requests.post(f"{http_url}/v2/pipeline", headers=headers, json=create_payload, timeout=30)
            
            if response.status_code == 200:
                print(f"  ✅ Created table structure")
            else:
                print(f"  ⚠️ Table creation: {response.status_code} - {response.text[:100]}")
        except Exception as e:
            print(f"  ⚠️ Table creation error: {e}")
        
        # Get all data
        local_cursor.execute(f"SELECT * FROM {table}")
        rows = local_cursor.fetchall()
        
        if not rows:
            print(f"  ℹ️ No data to migrate")
            continue
        
        # Get column names
        local_cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in local_cursor.fetchall()]
        
        # Insert data in batches of 10
        migrated = 0
        failed = 0
        batch_size = 10
        
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            statements = []
            
            for row in batch:
                # Escape values
                values = []
                for val in row:
                    if val is None:
                        values.append("NULL")
                    elif isinstance(val, str):
                        # Escape single quotes
                        escaped = val.replace("'", "''")
                        values.append(f"'{escaped}'")
                    else:
                        values.append(str(val))
                
                insert_sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(values)})"
                statements.append(insert_sql)
            
            # Send batch
            try:
                payload = {"statements": statements}
                response = requests.post(f"{http_url}/v2/pipeline", headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    migrated += len(batch)
                else:
                    failed += len(batch)
                    if failed <= 3:
                        print(f"  ⚠️ Batch error: {response.status_code}")
            except Exception as e:
                failed += len(batch)
                if failed <= 3:
                    print(f"  ⚠️ Batch error: {e}")
        
        total_rows += migrated
        print(f"  ✅ Migrated {migrated}/{len(rows)} rows" + (f" ({failed} failed)" if failed > 0 else ""))
    
    local_conn.close()
    
    print("\n" + "=" * 60)
    print(f"✅ MIGRATION COMPLETED!")
    print(f">> Total rows migrated: {total_rows}")
    print(f">> Tables migrated: {len(tables)}")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    if os.getenv('USE_TURSO', 'false').lower() != 'true':
        print("ERROR: USE_TURSO must be set to 'true' in .env file")
        exit(1)
    
    success = migrate_via_http()
    
    if success:
        print("\n✅ Migration successful!")
    else:
        print("\n❌ Migration failed.")
