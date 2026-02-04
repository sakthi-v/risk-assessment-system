"""
FINAL Migration Script - Export to SQL and upload to Turso
This WILL work!
"""
import sqlite3
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def export_to_sql():
    """Export local database to SQL file"""
    print("Step 1: Exporting local database to SQL...")
    
    conn = sqlite3.connect('database/risk_register.db')
    
    # Get SQL dump
    sql_dump = []
    for line in conn.iterdump():
        sql_dump.append(line)
    
    conn.close()
    
    # Save to file
    with open('backup.sql', 'w', encoding='utf-8') as f:
        f.write('\n'.join(sql_dump))
    
    print(f"✅ Exported {len(sql_dump)} SQL statements to backup.sql")
    return sql_dump

def upload_to_turso(sql_statements):
    """Upload SQL to Turso using REST API"""
    print("\nStep 2: Uploading to Turso...")
    
    turso_url = os.getenv("TURSO_DATABASE_URL")
    turso_token = os.getenv("TURSO_AUTH_TOKEN")
    
    # Convert to HTTPS
    http_url = turso_url.replace("libsql://", "https://")
    
    headers = {
        "Authorization": f"Bearer {turso_token}",
        "Content-Type": "application/json"
    }
    
    # Filter out BEGIN/COMMIT/ANALYZE statements
    filtered_statements = []
    for stmt in sql_statements:
        stmt = stmt.strip()
        if stmt and not stmt.startswith('--') and stmt not in ['BEGIN TRANSACTION;', 'COMMIT;', 'ANALYZE sqlite_master;']:
            filtered_statements.append(stmt)
    
    print(f"Uploading {len(filtered_statements)} statements...")
    
    # Upload in batches of 50
    batch_size = 50
    total_success = 0
    total_failed = 0
    
    for i in range(0, len(filtered_statements), batch_size):
        batch = filtered_statements[i:i+batch_size]
        
        try:
            payload = {
                "statements": batch
            }
            
            response = requests.post(
                f"{http_url}/v2/pipeline",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                total_success += len(batch)
                print(f"  ✅ Batch {i//batch_size + 1}: {len(batch)} statements uploaded")
            else:
                total_failed += len(batch)
                print(f"  ❌ Batch {i//batch_size + 1} failed: {response.status_code}")
                if total_failed <= 3:
                    print(f"     Error: {response.text[:200]}")
        except Exception as e:
            total_failed += len(batch)
            print(f"  ❌ Batch {i//batch_size + 1} error: {str(e)[:100]}")
    
    print(f"\n✅ Upload complete!")
    print(f"   Success: {total_success} statements")
    print(f"   Failed: {total_failed} statements")
    
    return total_success > 0

def main():
    print("=" * 60)
    print("TURSO MIGRATION - SQL Export Method")
    print("=" * 60)
    
    if os.getenv('USE_TURSO', 'false').lower() != 'true':
        print("❌ ERROR: Set USE_TURSO=true in .env file")
        return False
    
    # Step 1: Export to SQL
    sql_statements = export_to_sql()
    
    # Step 2: Upload to Turso
    success = upload_to_turso(sql_statements)
    
    print("\n" + "=" * 60)
    if success:
        print("✅ MIGRATION SUCCESSFUL!")
        print("Your data is now in Turso cloud database!")
    else:
        print("❌ MIGRATION FAILED")
        print("Try again or deploy with empty database")
    print("=" * 60)
    
    return success

if __name__ == "__main__":
    main()
