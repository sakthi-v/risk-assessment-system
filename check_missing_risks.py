"""
Check which risks exist in Turso database
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from database_manager import get_database_connection

# Missing risk IDs from cloud
missing_ids = ['RSK-008', 'RSK-011', 'RSK-013', 'RSK-019']

conn = get_database_connection()
cursor = conn.cursor()

print("=" * 60)
print("CHECKING MISSING RISKS IN TURSO DATABASE")
print("=" * 60)

for risk_id in missing_ids:
    cursor.execute("""
        SELECT risk_id, asset_name, treatment_decision, created_at, status, last_followup_date
        FROM risks 
        WHERE risk_id = ?
    """, (risk_id,))
    
    row = cursor.fetchone()
    if row:
        print(f"\n[FOUND] {risk_id} EXISTS:")
        print(f"   Asset: {row[1]}")
        print(f"   Decision: {row[2]}")
        print(f"   Created: {row[3]}")
        print(f"   Status: {row[4]}")
        print(f"   Last Follow-up: {row[5]}")
    else:
        print(f"\n[MISSING] {risk_id} NOT FOUND in database")

print("\n" + "=" * 60)
print("ALL RISKS IN DATABASE:")
print("=" * 60)

cursor.execute("""
    SELECT risk_id, asset_name, treatment_decision, created_at, status
    FROM risks 
    ORDER BY risk_id
""")

for row in cursor.fetchall():
    print(f"{row[0]} | {row[1][:30]:30} | {row[2]:10} | {row[3]} | {row[4] or 'Open'}")

conn.close()
