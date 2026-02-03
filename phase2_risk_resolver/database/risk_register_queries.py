"""
Risk Register Query Functions - WITH ACCEPT SUPPORT
Read risks from database and display in Risk Register page
Now properly parses ACCEPT fields!
"""

import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


def get_database_path() -> str:
    """Get the path to risk register database"""
    db_path = os.path.join('database', 'risk_register.db')
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at: {db_path}")
    return db_path


def get_all_risks(
    status_filter: Optional[str] = None,
    risk_rating_filter: Optional[str] = None,
    risk_owner_filter: Optional[str] = None,
    treatment_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search_query: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Query all risks from database with optional filters
    
    Args:
        status_filter: Filter by status (Open, In Progress, Closed)
        risk_rating_filter: Filter by risk rating (1-5)
        risk_owner_filter: Filter by risk owner
        treatment_filter: Filter by treatment decision
        date_from: Filter by date from (YYYY-MM-DD)
        date_to: Filter by date to (YYYY-MM-DD)
        search_query: Search in title, description, asset
    
    Returns:
        List of risk dictionaries
    """
    
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    cursor = conn.cursor()
    
    # Build query
    query = "SELECT * FROM risks WHERE 1=1"
    params = []
    
    # Apply filters
    if status_filter and status_filter != 'All':
        query += " AND status = ?"
        params.append(status_filter)
    
    if risk_rating_filter and risk_rating_filter != 'All':
        query += " AND CAST(inherent_risk_rating AS INTEGER) = ?"
        params.append(int(risk_rating_filter))
    
    if risk_owner_filter and risk_owner_filter != 'All':
        query += " AND risk_owner = ?"
        params.append(risk_owner_filter)
    
    if treatment_filter and treatment_filter != 'All':
        query += " AND treatment_decision = ?"
        params.append(treatment_filter)
    
    if date_from:
        query += " AND identified_date >= ?"
        params.append(date_from)
    
    if date_to:
        query += " AND identified_date <= ?"
        params.append(date_to)
    
    if search_query:
        query += " AND (threat_name LIKE ? OR threat_description LIKE ? OR asset_name LIKE ?)"
        search_pattern = f"%{search_query}%"
        params.extend([search_pattern, search_pattern, search_pattern])
    
    # Order by
    query += " ORDER BY identified_date DESC, inherent_risk_rating DESC"
    
    # Execute query
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Convert to list of dictionaries
    risks = []
    for row in rows:
        risk = dict(row)
        
        # Parse JSON fields (existing + ACCEPT fields)
        json_fields = [
            'existing_controls', 'control_gaps', 'recommended_controls',
            'treatment_plan', 'rtp_answers', 'agent_1_raw', 'agent_2_raw',
            'agent_3_raw', 'agent_4_raw',
            # ✅ NEW: ACCEPT JSON fields
            'business_justification', 'cost_benefit_analysis', 'monitoring_plan',
            'approver_risk_owner', 'approver_ciso', 'approver_cio', 'acceptance_form'
        ]
        
        for field in json_fields:
            if risk.get(field):
                try:
                    risk[field] = json.loads(risk[field])
                except:
                    pass  # Keep as string if not valid JSON
        
        risks.append(risk)
    
    conn.close()
    
    return risks


def get_risk_by_id(risk_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single risk by ID
    
    Args:
        risk_id: Risk ID to fetch
    
    Returns:
        Risk dictionary or None if not found
    """
    
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM risks WHERE risk_id = ?", (risk_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
    
    risk = dict(row)
    
    # Parse JSON fields (existing + ACCEPT fields)
    json_fields = [
        'existing_controls', 'control_gaps', 'recommended_controls',
        'treatment_plan', 'rtp_answers', 'agent_1_raw', 'agent_2_raw',
        'agent_3_raw', 'agent_4_raw',
        # ✅ NEW: ACCEPT JSON fields
        'business_justification', 'cost_benefit_analysis', 'monitoring_plan',
        'approver_risk_owner', 'approver_ciso', 'approver_cio', 'acceptance_form'
    ]
    
    for field in json_fields:
        if risk.get(field):
            try:
                risk[field] = json.loads(risk[field])
            except:
                pass
    
    conn.close()
    
    return risk


def get_dashboard_stats() -> Dict[str, Any]:
    """
    Get dashboard statistics
    
    Returns:
        Dictionary with dashboard stats
    """
    
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {}
    
    # Total risks
    cursor.execute("SELECT COUNT(*) FROM risks")
    stats['total_risks'] = cursor.fetchone()[0]
    
    # High priority risks (rating >= 4.5 for Critical, or priority field is Critical/High)
    cursor.execute("""
        SELECT COUNT(*) FROM risks 
        WHERE inherent_risk_rating >= 4.5
    """)
    stats['high_priority'] = cursor.fetchone()[0]
    
    # Open risks
    cursor.execute("SELECT COUNT(*) FROM risks WHERE status = 'Open'")
    stats['open_risks'] = cursor.fetchone()[0]
    
    # Closed risks
    cursor.execute("SELECT COUNT(*) FROM risks WHERE status = 'Closed'")
    stats['closed_risks'] = cursor.fetchone()[0]
    
    # In progress risks
    cursor.execute("SELECT COUNT(*) FROM risks WHERE status = 'In Progress'")
    stats['in_progress'] = cursor.fetchone()[0]
    
    # Highest risk rating
    cursor.execute("SELECT MAX(inherent_risk_rating) FROM risks")
    max_rating = cursor.fetchone()[0]
    stats['highest_risk'] = f"{max_rating or 0}/5"
    
    # Risks by status
    cursor.execute("""
        SELECT status, COUNT(*) 
        FROM risks 
        GROUP BY status
    """)
    stats['by_status'] = dict(cursor.fetchall())
    
    # Risks by priority
    cursor.execute("""
        SELECT priority, COUNT(*) 
        FROM risks 
        GROUP BY priority
    """)
    stats['by_priority'] = dict(cursor.fetchall())
    
    # Risks by risk level
    cursor.execute("""
        SELECT inherent_risk_level, COUNT(*) 
        FROM risks 
        GROUP BY inherent_risk_level
    """)
    stats['by_risk_level'] = dict(cursor.fetchall())
    
    # ✅ NEW: Risks by treatment decision
    cursor.execute("""
        SELECT treatment_decision, COUNT(*) 
        FROM risks 
        GROUP BY treatment_decision
    """)
    stats['by_treatment_decision'] = dict(cursor.fetchall())
    
    # ✅ NEW: Accepted risks count
    cursor.execute("SELECT COUNT(*) FROM risks WHERE treatment_decision = 'ACCEPT'")
    stats['accepted_risks'] = cursor.fetchone()[0]
    
    # ✅ NEW: Treated risks count
    cursor.execute("SELECT COUNT(*) FROM risks WHERE treatment_decision = 'TREAT'")
    stats['treated_risks'] = cursor.fetchone()[0]
    
    conn.close()
    
    return stats


def get_followup_metrics() -> Dict[str, Any]:
    """
    ✅ PHASE 3: Get follow-up statistics for dashboard
    
    Returns:
        Dictionary with follow-up metrics
    """
    
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    metrics = {}
    
    # Total risks with follow-ups
    cursor.execute("SELECT COUNT(*) FROM risks WHERE followup_count > 0")
    metrics['total_with_followups'] = cursor.fetchone()[0]
    
    # Overdue follow-ups (next_followup_date is past)
    cursor.execute("""
        SELECT COUNT(*) FROM risks 
        WHERE next_followup_date IS NOT NULL 
        AND next_followup_date < date('now')
        AND status NOT IN ('Completed', 'Closed', 'Terminated - Closed')
    """)
    metrics['overdue_followups'] = cursor.fetchone()[0]
    
    # Never followed up (created 5+ days ago, no follow-up done)
    cutoff_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT COUNT(*) FROM risks 
        WHERE created_at <= ?
        AND treatment_decision IS NOT NULL
        AND followup_count = 0
        AND status NOT IN ('Completed', 'Closed', 'Terminated - Closed')
    """, (cutoff_date,))
    metrics['never_followed_up'] = cursor.fetchone()[0]
    
    # Average follow-ups per risk
    cursor.execute("""
        SELECT AVG(followup_count) FROM risks 
        WHERE treatment_decision IS NOT NULL
    """)
    avg = cursor.fetchone()[0]
    metrics['avg_followups_per_risk'] = round(avg, 1) if avg else 0
    
    # Completed after follow-up
    cursor.execute("""
        SELECT COUNT(*) FROM risks 
        WHERE followup_count > 0 
        AND status IN ('Completed', 'Closed', 'Terminated - Closed')
    """)
    metrics['completed_after_followup'] = cursor.fetchone()[0]
    
    # Risks with high follow-up count but low progress
    cursor.execute("""
        SELECT COUNT(*) FROM risks 
        WHERE followup_count >= 3 
        AND completion_percentage < 25
        AND status NOT IN ('Completed', 'Closed', 'Terminated - Closed')
    """)
    metrics['high_followup_low_progress'] = cursor.fetchone()[0]
    
    # Delayed risks
    cursor.execute("""
        SELECT COUNT(*) FROM risks 
        WHERE timeline_status = 'Delayed'
        AND status NOT IN ('Completed', 'Closed', 'Terminated - Closed')
    """)
    metrics['delayed_risks'] = cursor.fetchone()[0]
    
    conn.close()
    
    return metrics


def get_overdue_followups() -> List[Dict[str, Any]]:
    """
    ✅ PHASE 3: Get list of risks with overdue follow-ups
    
    Returns:
        List of overdue risks with days overdue
    """
    
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            risk_id,
            asset_name,
            threat_name,
            next_followup_date,
            followup_count,
            completion_percentage,
            status,
            julianday('now') - julianday(next_followup_date) as days_overdue
        FROM risks
        WHERE next_followup_date < date('now')
        AND status NOT IN ('Completed', 'Closed', 'Terminated - Closed')
        ORDER BY days_overdue DESC
    """)
    
    rows = cursor.fetchall()
    overdue = [dict(row) for row in rows]
    
    conn.close()
    
    return overdue


def get_unique_risk_owners() -> List[str]:
    """Get list of unique risk owners"""
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT risk_owner FROM risks WHERE risk_owner IS NOT NULL ORDER BY risk_owner")
    owners = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return owners


def get_unique_treatment_decisions() -> List[str]:
    """Get list of unique treatment decisions"""
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT treatment_decision FROM risks WHERE treatment_decision IS NOT NULL ORDER BY treatment_decision")
    decisions = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return decisions


def get_accepted_risks() -> List[Dict[str, Any]]:
    """
    Get all risks with ACCEPT decision
    
    Returns:
        List of accepted risk dictionaries
    """
    return get_all_risks(treatment_filter='ACCEPT')


def get_risks_expiring_soon(days: int = 30) -> List[Dict[str, Any]]:
    """
    Get accepted risks that are expiring soon
    
    Args:
        days: Number of days threshold
    
    Returns:
        List of risks expiring within specified days
    """
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Calculate expiry threshold
    threshold_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT * FROM risks 
        WHERE treatment_decision = 'ACCEPT' 
        AND valid_until_date IS NOT NULL 
        AND valid_until_date <= ?
        AND status != 'Closed'
        ORDER BY valid_until_date ASC
    """, (threshold_date,))
    
    rows = cursor.fetchall()
    
    risks = []
    for row in rows:
        risk = dict(row)
        
        # Parse JSON fields
        json_fields = [
            'existing_controls', 'control_gaps', 'recommended_controls',
            'treatment_plan', 'rtp_answers', 'agent_1_raw', 'agent_2_raw',
            'agent_3_raw', 'agent_4_raw',
            'business_justification', 'cost_benefit_analysis', 'monitoring_plan',
            'approver_risk_owner', 'approver_ciso', 'approver_cio', 'acceptance_form'
        ]
        
        for field in json_fields:
            if risk.get(field):
                try:
                    risk[field] = json.loads(risk[field])
                except:
                    pass
        
        risks.append(risk)
    
    conn.close()
    
    return risks


def update_risk_field(risk_id: str, field: str, value: Any) -> bool:
    """
    Update a single field for a risk
    
    Args:
        risk_id: Risk ID
        field: Field name to update
        value: New value
    
    Returns:
        True if successful
    """
    
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Convert dict/list to JSON string if needed
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        cursor.execute(f"""
            UPDATE risks 
            SET {field} = ?, last_updated = ?
            WHERE risk_id = ?
        """, (value, datetime.now().strftime('%Y-%m-%d'), risk_id))
        
        conn.commit()
        success = cursor.rowcount > 0
        
    except Exception as e:
        print(f"Error updating risk {risk_id}: {str(e)}")
        success = False
    
    finally:
        conn.close()
    
    return success


def delete_risk(risk_id: str) -> bool:
    """
    Delete a risk from database
    
    Args:
        risk_id: Risk ID to delete
    
    Returns:
        True if successful
    """
    
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM risks WHERE risk_id = ?", (risk_id,))
        conn.commit()
        success = cursor.rowcount > 0
    
    except Exception as e:
        print(f"Error deleting risk {risk_id}: {str(e)}")
        success = False
    
    finally:
        conn.close()
    
    return success


if __name__ == "__main__":
    # Test queries
    print("Testing Risk Register Queries - WITH ACCEPT SUPPORT...")
    
    try:
        stats = get_dashboard_stats()
        print(f"\nDashboard Stats:")
        print(f"  Total Risks: {stats['total_risks']}")
        print(f"  High Priority: {stats['high_priority']}")
        print(f"  Open Risks: {stats['open_risks']}")
        print(f"  Accepted Risks: {stats.get('accepted_risks', 0)}")
        print(f"  Treated Risks: {stats.get('treated_risks', 0)}")
        
        risks = get_all_risks()
        print(f"\nFound {len(risks)} risk(s) in database")
        
        if risks:
            print(f"\nFirst risk:")
            print(f"  ID: {risks[0]['risk_id']}")
            print(f"  Asset: {risks[0]['asset_name']}")
            print(f"  Threat: {risks[0]['threat_name']}")
            print(f"  Risk Rating: {risks[0]['inherent_risk_rating']}/5")
            print(f"  Decision: {risks[0].get('treatment_decision', 'N/A')}")
        
        # Test accepted risks
        accepted = get_accepted_risks()
        print(f"\nAccepted Risks: {len(accepted)}")
        
    except Exception as e:
        print(f"Error: {str(e)}")