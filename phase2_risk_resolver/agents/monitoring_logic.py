"""
Risk Monitoring Logic - Automated Risk Health Checks
Detects problem risks and generates alerts (NO EMAIL - UI only)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
import sqlite3


def check_risk_progress(risk_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if a risk is progressing as expected
    
    Args:
        risk_data: Risk record from database
    
    Returns:
        Dict with health_status, severity, problem, recommendation
    """
    
    risk_id = risk_data.get('risk_id', 'Unknown')
    status = risk_data.get('status', 'Open')
    created_at = risk_data.get('created_at', '')
    completion_pct = risk_data.get('completion_percentage', 0) or 0
    followup_count = risk_data.get('followup_count', 0) or 0
    
    # Calculate days since creation
    try:
        created_date = datetime.strptime(created_at.split()[0], '%Y-%m-%d')
        days_old = (datetime.now() - created_date).days
    except:
        days_old = 0
    
    # Check for risk trend (if follow-up done)
    original_residual = risk_data.get('residual_risk_rating', 0) or 0
    current_residual = risk_data.get('current_residual_risk', 0)
    
    risk_trend = "UNKNOWN"
    if current_residual:
        if current_residual < original_residual:
            risk_trend = "IMPROVING"
        elif current_residual > original_residual:
            risk_trend = "WORSENING"
        else:
            risk_trend = "SAME"
    
    # ═══════════════════════════════════════════════════════════════
    # DETECTION LOGIC
    # ═══════════════════════════════════════════════════════════════
    
    # CRITICAL: Risk worsening
    if risk_trend == "WORSENING":
        return {
            'health_status': 'CRITICAL',
            'severity': 'HIGH',
            'problem': f'Risk INCREASED after treatment (from {original_residual}/5 to {current_residual}/5)',
            'recommendation': 'Immediate review required. Current controls may be ineffective.',
            'days_old': days_old,
            'trend': risk_trend
        }
    

    
    # CRITICAL: No progress for 30+ days
    if days_old >= 30 and followup_count == 0 and status == 'Open':
        return {
            'health_status': 'CRITICAL',
            'severity': 'HIGH',
            'problem': f'No progress for {days_old} days. No follow-up done.',
            'recommendation': 'Contact action owner immediately. Schedule urgent review.',
            'days_old': days_old,
            'trend': risk_trend
        }
    
    # WARNING: Slow progress after 60 days
    if days_old >= 60 and completion_pct < 50:
        return {
            'health_status': 'WARNING',
            'severity': 'MEDIUM',
            'problem': f'Only {completion_pct}% complete after {days_old} days',
            'recommendation': 'Review timeline and resources. Consider escalation.',
            'days_old': days_old,
            'trend': risk_trend
        }
    
    # WARNING: Approaching 90 days with incomplete status
    if days_old >= 75 and status != 'Completed':
        return {
            'health_status': 'WARNING',
            'severity': 'MEDIUM',
            'problem': f'Approaching 90-day deadline ({days_old} days old)',
            'recommendation': 'Expedite remaining actions or request timeline extension.',
            'days_old': days_old,
            'trend': risk_trend
        }
    
    # ON_TRACK: Good progress
    if risk_trend == "IMPROVING" or completion_pct >= 50:
        return {
            'health_status': 'ON_TRACK',
            'severity': 'LOW',
            'problem': None,
            'recommendation': 'Continue monitoring. Risk is progressing well.',
            'days_old': days_old,
            'trend': risk_trend
        }
    
    # DEFAULT: Normal status
    return {
        'health_status': 'ON_TRACK',
        'severity': 'LOW',
        'problem': None,
        'recommendation': 'No issues detected. Continue as planned.',
        'days_old': days_old,
        'trend': risk_trend
    }


def get_all_risk_alerts() -> Dict[str, List[Dict[str, Any]]]:
    """
    Scan all open risks and return alerts grouped by severity
    
    Returns:
        Dict with 'critical', 'warning', 'on_track' lists
    """
    
    try:
        conn = sqlite3.connect('database/risk_register.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all non-completed risks
        cursor.execute("""
            SELECT 
                risk_id, asset_name, threat_name, status, created_at,
                completion_percentage, followup_count,
                residual_risk_rating, current_residual_risk,
                treatment_decision
            FROM risks
            WHERE status NOT IN ('Completed', 'Closed', 'Terminated - Closed')
            AND treatment_decision IS NOT NULL
            ORDER BY created_at ASC
        """)
        
        risks = cursor.fetchall()
        conn.close()
        
        alerts = {
            'critical': [],
            'warning': [],
            'on_track': []
        }
        
        for row in risks:
            risk_data = dict(row)
            health_check = check_risk_progress(risk_data)
            
            alert = {
                'risk_id': risk_data['risk_id'],
                'asset_name': risk_data['asset_name'],
                'threat_name': risk_data['threat_name'],
                'status': risk_data['status'],
                'health_status': health_check['health_status'],
                'severity': health_check['severity'],
                'problem': health_check['problem'],
                'recommendation': health_check['recommendation'],
                'days_old': health_check['days_old'],
                'trend': health_check['trend']
            }
            
            if health_check['health_status'] == 'CRITICAL':
                alerts['critical'].append(alert)
            elif health_check['health_status'] == 'WARNING':
                alerts['warning'].append(alert)
            else:
                alerts['on_track'].append(alert)
        
        return alerts
        
    except Exception as e:
        print(f"Error getting risk alerts: {str(e)}")
        return {'critical': [], 'warning': [], 'on_track': []}


def get_monitoring_stats() -> Dict[str, Any]:
    """
    Get dashboard statistics for risk monitoring
    
    Returns:
        Dict with counts, percentages, and metrics
    """
    
    alerts = get_all_risk_alerts()
    
    total_risks = len(alerts['critical']) + len(alerts['warning']) + len(alerts['on_track'])
    
    if total_risks == 0:
        return {
            'total_risks': 0,
            'critical_count': 0,
            'warning_count': 0,
            'on_track_count': 0,
            'critical_pct': 0,
            'warning_pct': 0,
            'on_track_pct': 0
        }
    
    critical_count = len(alerts['critical'])
    warning_count = len(alerts['warning'])
    on_track_count = len(alerts['on_track'])
    
    return {
        'total_risks': total_risks,
        'critical_count': critical_count,
        'warning_count': warning_count,
        'on_track_count': on_track_count,
        'critical_pct': round((critical_count / total_risks) * 100, 1),
        'warning_pct': round((warning_count / total_risks) * 100, 1),
        'on_track_pct': round((on_track_count / total_risks) * 100, 1)
    }


def get_risk_recommendations(risk_id: str) -> List[str]:
    """
    Get specific recommendations for a risk
    
    Args:
        risk_id: Risk ID to analyze
    
    Returns:
        List of actionable recommendations
    """
    
    try:
        conn = sqlite3.connect('database/risk_register.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM risks WHERE risk_id = ?
        """, (risk_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return ["Risk not found"]
        
        risk_data = dict(row)
        health_check = check_risk_progress(risk_data)
        
        recommendations = []
        
        # Add health-based recommendation
        if health_check['recommendation']:
            recommendations.append(health_check['recommendation'])
        
        # Add specific recommendations based on data
        completion_pct = risk_data.get('completion_percentage', 0) or 0
        followup_count = risk_data.get('followup_count', 0) or 0
        
        if completion_pct == 0 and followup_count == 0:
            recommendations.append("Schedule first follow-up to assess progress")
        
        if completion_pct > 0 and completion_pct < 100:
            recommendations.append(f"Track remaining {100 - completion_pct}% of implementation")
        
        if followup_count > 0 and completion_pct < 50:
            recommendations.append("Consider additional resources or timeline adjustment")
        
        return recommendations if recommendations else ["No specific recommendations"]
        
    except Exception as e:
        return [f"Error generating recommendations: {str(e)}"]


if __name__ == "__main__":
    # Test the monitoring logic
    print("Testing Risk Monitoring Logic...")
    
    alerts = get_all_risk_alerts()
    print(f"\nCritical: {len(alerts['critical'])}")
    print(f"Warning: {len(alerts['warning'])}")
    print(f"On Track: {len(alerts['on_track'])}")
    
    stats = get_monitoring_stats()
    print(f"\nTotal Risks: {stats['total_risks']}")
    print(f"Critical: {stats['critical_pct']}%")
    print(f"Warning: {stats['warning_pct']}%")
    print(f"On Track: {stats['on_track_pct']}%")
