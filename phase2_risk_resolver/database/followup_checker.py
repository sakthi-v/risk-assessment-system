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
    try:
        conn = get_database_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 🔧 FIX: Use India time (IST = UTC+5:30)
        from datetime import timezone, timedelta as td
        ist = timezone(td(hours=5, minutes=30))
        now_ist = datetime.now(ist)
        cutoff_date = (now_ist - timedelta(days=days_threshold)).strftime('%Y-%m-%d')
        
        # Query risks where:
        # 1. First follow-up: created_at >= 5 days ago AND no follow-up done yet
        # 2. Recurring follow-ups: next_followup_date is due
        # 3. treatment_decision exists (TREAT/ACCEPT/TRANSFER/TERMINATE)
        # 4. Risk not closed
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
                (date(created_at) <= ? AND last_followup_date IS NULL)
                OR
                -- Recurring follow-ups: next_followup_date is due
                (next_followup_date IS NOT NULL AND next_followup_date <= date('now'))
            )
            ORDER BY created_at ASC
        """, (cutoff_date,))
        
        risks = []
        for row in cursor.fetchall():
            # Handle both date and datetime formats for created_at
            created_str = row['created_at'].split()[0] if ' ' in str(row['created_at']) else str(row['created_at'])
            
            # 🔧 FIX: Use India time (IST)
            from datetime import timezone, timedelta as td
            ist = timezone(td(hours=5, minutes=30))
            now_ist = datetime.now(ist).date()
            
            # Calculate days since creation or last follow-up
            if row['last_followup_date']:
                days_since = (now_ist - datetime.strptime(row['last_followup_date'], '%Y-%m-%d').date()).days
            else:
                days_since = (now_ist - datetime.strptime(created_str, '%Y-%m-%d').date()).days
            
            risks.append({
                'risk_id': row['risk_id'],
                'asset_name': row['asset_name'],
                'threat_name': row['threat_name'],
                'treatment_decision': row['treatment_decision'],
                'created_at': row['created_at'],
                'followup_status': row['followup_status'],
                'followup_date': row['followup_date'],
                'followup_answers': row['followup_answers'],
                'next_followup_date': row['next_followup_date'],
                'followup_count': row['followup_count'] or 0,
                'last_followup_date': row['last_followup_date'],
                'status': row['status'] or 'Open',
                'completion_percentage': row['completion_percentage'] or 0,
                'current_blockers': row['current_blockers'],
                'timeline_status': row['timeline_status'],
                'inherent_risk_rating': row['inherent_risk_rating'],
                'control_rating': row['control_rating'],
                'residual_risk_rating': row['residual_risk_rating'],
                # 🔧 FIX: Use India time (IST)
                'days_since_creation': (now_ist - datetime.strptime(created_str, '%Y-%m-%d').date()).days,
                'days_since_last_followup': days_since
            })
        
        conn.close()
        return risks
        
    except Exception as e:
        print(f"Error checking follow-ups: {str(e)}")
        return []


def get_followup_count() -> int:
    """Get count of risks needing follow-up"""
    risks = get_risks_needing_followup()
    return len(risks)
