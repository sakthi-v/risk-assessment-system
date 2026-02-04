"""
Check next_followup_date for missing risks
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from database_manager import get_database_connection
from datetime import datetime, timezone, timedelta

# Missing risk IDs from cloud
missing_ids = ['RSK-008', 'RSK-011', 'RSK-013', 'RSK-019']

conn = get_database_connection()
cursor = conn.cursor()

print("=" * 80)
print("CHECKING FOLLOW-UP DATES FOR MISSING RISKS")
print("=" * 80)

# Get current date in IST
ist = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(ist)
cutoff_date = (now_ist - timedelta(days=5)).strftime('%Y-%m-%d')

print(f"\nCurrent IST Date: {now_ist.strftime('%Y-%m-%d')}")
print(f"Cutoff Date (5 days ago): {cutoff_date}")

for risk_id in missing_ids:
    cursor.execute("""
        SELECT risk_id, created_at, last_followup_date, next_followup_date, 
               followup_count, status, completion_percentage
        FROM risks 
        WHERE risk_id = ?
    """, (risk_id,))
    
    row = cursor.fetchone()
    if row:
        print(f"\n{row[0]}:")
        print(f"  Created: {row[1]}")
        print(f"  Last Follow-up: {row[2]}")
        print(f"  Next Follow-up: {row[3]}")
        print(f"  Follow-up Count: {row[4]}")
        print(f"  Status: {row[5]}")
        print(f"  Completion %: {row[6]}")
        
        # Check if it should be included
        created_str = str(row[1]).split()[0] if ' ' in str(row[1]) else str(row[1])
        
        if row[2] is None:  # No last follow-up
            if created_str <= cutoff_date:
                print(f"  -> SHOULD BE INCLUDED (created <= {cutoff_date}, no follow-up)")
            else:
                print(f"  -> EXCLUDED (created > {cutoff_date})")
        else:  # Has last follow-up
            if row[3] and row[3] <= cutoff_date:
                print(f"  -> SHOULD BE INCLUDED (next_followup_date {row[3]} <= {cutoff_date})")
            else:
                print(f"  -> EXCLUDED (next_followup_date {row[3]} > {cutoff_date} OR is NULL)")

conn.close()
