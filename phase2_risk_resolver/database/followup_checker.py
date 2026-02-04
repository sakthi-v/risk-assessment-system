"""
Follow-up Checker - Identifies risks that need follow-up after 5 days
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any
import sqlite3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from database_manager import get_database_connection


def get_risks_needing_followup(days_threshold: int = 5) -> List[Dict[str, Any]]:
    """
    Check all risks in database and return those needing follow-up
    
    Args:
        days_threshold: Number of days after created_at to trigger follow-up (default: 5)
    
    Returns:
        List of risk records that need follow-up
    """
    risks = []
    try:
        conn = get_database_connection()
        # 🔧 FIX: Don't use row_factory with Turso - it doesn't support it
        # conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 🔧 FIX: Use India time (IST = UTC+5:30)
        from datetime import timezone, timedelta as td
        ist = timezone(td(hours=5, minutes=30))
        now_ist = datetime.now(ist)
        cutoff_date = (now_ist - timedelta(days=days_threshold)).strftime('%Y-%m-%d')
        today_date = now_ist.strftime('%Y-%m-%d')
        
        # Query risks where:
        # 1. First follow-up: created_at >= 5 days ago AND no follow-up done yet
        # 2. Recurring follow-ups: next_followup_date is due (on or before today)
        # 3. treatment_decision exists (TREAT/ACCEPT/TRANSFER/TERMINATE)
        # 4. Risk not closed
        # 🔧 FIX: Use SUBSTR for Turso compatibility instead of date()
        cursor.execute("""
            SELECT 
                risk_id,
                asset_name,
                threat_name,
                treatment_decision,
                created_at,
                followup_status,
                followup_date,
                followup_answers,
                next_followup_date,
                followup_count,
                last_followup_date,
                status,
                completion_percentage,
                current_blockers,
                timeline_status,
                inherent_risk_rating,
                control_rating,
                residual_risk_rating
            FROM risks
            WHERE treatment_decision IS NOT NULL
            AND treatment_decision != ''
            AND status NOT IN ('Closed')
            AND (
                -- First follow-up: 5+ days after creation, no follow-up done yet
                (SUBSTR(created_at, 1, 10) <= ? AND last_followup_date IS NULL)
                OR
                -- Recurring follow-ups: next_followup_date is due (on or before today)
                (next_followup_date IS NOT NULL AND next_followup_date <= ?)
            )
            ORDER BY created_at ASC
        """, (cutoff_date, today_date))
        
        for row in cursor.fetchall():
            # 🔧 FIX: Access by index since row_factory is disabled for Turso
            risk_id = row[0]
            asset_name = row[1]
            threat_name = row[2]
            treatment_decision = row[3]
            created_at = row[4]
            followup_status = row[5]
            followup_date = row[6]
            followup_answers = row[7]
            next_followup_date = row[8]
            followup_count = row[9]
            last_followup_date = row[10]
            status = row[11]
            completion_percentage = row[12]
            current_blockers = row[13]
            timeline_status = row[14]
            inherent_risk_rating = row[15]
            control_rating = row[16]
            residual_risk_rating = row[17]
            
            # Handle both date and datetime formats for created_at
            created_str = created_at
            # 🔧 FIX: Handle both "YYYY-MM-DD" and "YYYY-MM-DD HH:MM:SS" formats
            if ' ' in str(created_str):
                created_str = created_str.split()[0]  # Extract date part
            
            # 🔧 FIX: Use India time (IST)
            ist = timezone(td(hours=5, minutes=30))
            now_ist = datetime.now(ist).date()
            
            # Calculate days since creation or last follow-up
            if last_followup_date:
                days_since = (now_ist - datetime.strptime(last_followup_date, '%Y-%m-%d').date()).days
            else:
                days_since = (now_ist - datetime.strptime(created_str, '%Y-%m-%d').date()).days
            
            risks.append({
                'risk_id': risk_id,
                'asset_name': asset_name,
                'threat_name': threat_name,
                'treatment_decision': treatment_decision,
                'created_at': created_at,
                'followup_status': followup_status,
                'followup_date': followup_date,
                'followup_answers': followup_answers,
                'next_followup_date': next_followup_date,
                'followup_count': followup_count or 0,
                'last_followup_date': last_followup_date,
                'status': status or 'Open',
                'completion_percentage': completion_percentage or 0,
                'current_blockers': current_blockers,
                'timeline_status': timeline_status,
                'inherent_risk_rating': inherent_risk_rating,
                'control_rating': control_rating,
                'residual_risk_rating': residual_risk_rating,
                # 🔧 FIX: Use already calculated days_since
                'days_since_creation': days_since,
                'days_since_last_followup': days_since
            })
        
        conn.close()
        return risks
        
    except Exception as e:
        print(f"Error checking follow-ups: {str(e)}")
        import traceback
        traceback.print_exc()
        return risks  # Return whatever we collected so far


def get_followup_count() -> int:
    """Get count of risks needing follow-up"""
    risks = get_risks_needing_followup()
    return len(risks)
