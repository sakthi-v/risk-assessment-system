"""
Save Follow-up Submission to Risk Register
Updates risk record with follow-up answers and status
🔧 UPDATED: Now integrates Agent 2 & 3 for risk recalculation
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from phase2_risk_resolver.agents.agent_3_followup import run_agent_3_followup
from phase2_risk_resolver.agents.agent_2_followup import run_agent_2_followup


def save_followup_to_risk_register(risk_id: str, answers: Dict[str, Any], questionnaire: Dict[str, Any], api_key: str = None) -> Dict[str, Any]:
    """
    Save follow-up answers to risk register and update status
    
    Args:
        risk_id: Risk ID to update
        answers: User's answers to follow-up questions
        questionnaire: The questionnaire structure
    
    Returns:
        Dict with success status and message
    """
    
    db_path = Path(__file__).parent.parent.parent / "database" / "risk_register.db"
    
    try:
        # ✅ FIX: Convert date objects to strings before JSON serialization
        answers = _convert_dates_to_strings(answers)
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Get existing follow-up history
        cursor.execute("SELECT followup_answers FROM risks WHERE risk_id = ?", (risk_id,))
        result = cursor.fetchone()
        
        if not result:
            return {'success': False, 'message': f'Risk {risk_id} not found'}
        
        # Parse existing history
        existing_history = []
        if result[0]:
            try:
                existing_history = json.loads(result[0])
                if not isinstance(existing_history, list):
                    existing_history = [existing_history]
            except:
                existing_history = []
        
        # Create new follow-up record
        followup_record = {
            'followup_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'decision_type': questionnaire.get('risk_context', {}).get('treatment_decision', 'Unknown'),
            'questionnaire_type': questionnaire.get('questionnaire_metadata', {}).get('questionnaire_type', 'Follow-up'),
            'answers': answers,
            'summary': _extract_summary(answers)
        }
        
        # Append to history
        existing_history.append(followup_record)
        
        # Get current risk data for intelligent updates
        cursor.execute("""
            SELECT status, inherent_risk_rating, residual_risk_rating, target_completion_date, followup_count,
                   control_rating, treatment_actions, asset_name, threat_name
            FROM risks WHERE risk_id = ?
        """, (risk_id,))
        current_risk = cursor.fetchone()
        current_count = current_risk[4] or 0
        
        # Build risk_data dict for agents
        risk_data = {
            'risk_id': risk_id,
            'status': current_risk[0],
            'inherent_risk_rating': current_risk[1],
            'residual_risk_rating': current_risk[2],
            'target_completion_date': current_risk[3],
            'followup_count': current_risk[4],
            'control_rating': current_risk[5],
            'treatment_actions': current_risk[6],
            'asset_name': current_risk[7],
            'threat_name': current_risk[8]
        }
        
        # 🤖 PHASE 2: Run Agent 3 & 2 to recalculate risk
        new_control_rating = None
        new_residual_risk = None
        risk_reduction_pct = 0
        agent_3_result = None
        agent_2_result = None
        
        if api_key:
            try:
                print("\n🤖 Running Agent 3 (Control Re-evaluation)...")
                agent_3_result = run_agent_3_followup(api_key, risk_data, answers)
                new_control_rating = agent_3_result.get('new_control_rating')
                
                if new_control_rating:
                    print("\n🤖 Running Agent 2 (Risk Recalculation)...")
                    agent_2_result = run_agent_2_followup(api_key, risk_data, new_control_rating)
                    new_residual_risk = agent_2_result.get('new_residual_risk')
                    risk_reduction_pct = agent_2_result.get('risk_reduction_percentage', 0)
            except Exception as e:
                print(f"⚠️ Agent execution error: {e}")
                # Continue with fallback calculation
        
        # ✅ PHASE 3: Analyze answers and extract intelligent updates
        decision_type = questionnaire.get('risk_context', {}).get('treatment_decision', 'Unknown')
        intelligent_updates = _analyze_followup_answers(answers, decision_type, {
            'status': current_risk[0],
            'inherent_risk_rating': current_risk[1],
            'residual_risk_rating': current_risk[2],
            'target_completion_date': current_risk[3]
        })
        
        # ✅ PHASE 1: Calculate next follow-up date based on completion
        completion_pct = intelligent_updates.get('completion_percentage', _extract_completion_percentage(answers))
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        if completion_pct >= 100:
            # Risk completed - no more follow-ups needed
            next_followup_date = None
            new_status = 'Closed'
        elif completion_pct >= 75:
            # Near completion - follow up in 7 days
            next_followup_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            new_status = 'In Progress'
        elif completion_pct >= 50:
            # Moderate progress - follow up in 5 days
            next_followup_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
            new_status = 'In Progress'
        elif completion_pct > 0:
            # Low progress - follow up in 5 days
            next_followup_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
            new_status = 'In Progress'
        else:
            # No progress - follow up in 3 days (urgent)
            next_followup_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
            new_status = 'Open'
        
        # ✅ FIX: Removed redundant database query - already have current_count from line 78
        
        # ✅ Extract action_owner from answers
        action_owner = None
        for key, value in answers.items():
            if 'action_owner' in key.lower():
                action_owner = str(value) if value else None
                break
        
        # Update database with all intelligent fields + agent results
        cursor.execute("""
            UPDATE risks 
            SET followup_status = 'COMPLETED',
                followup_date = ?,
                followup_answers = ?,
                last_updated = ?,
                next_followup_date = ?,
                followup_count = ?,
                last_followup_date = ?,
                status = ?,
                completion_percentage = ?,
                control_effectiveness = ?,
                timeline_status = ?,
                revised_completion_date = ?,
                residual_risk = ?,
                action_owner = ?,
                current_control_rating = ?,
                current_residual_risk = ?,
                risk_reduction_percentage = ?,
                last_reassessment_date = ?
            WHERE risk_id = ?
        """, (
            datetime.now().strftime('%Y-%m-%d'),
            json.dumps(existing_history),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            next_followup_date,
            current_count + 1,
            current_date,
            new_status,
            intelligent_updates.get('completion_percentage', completion_pct),
            intelligent_updates.get('control_effectiveness'),
            intelligent_updates.get('timeline_status'),
            intelligent_updates.get('revised_completion_date'),
            intelligent_updates.get('residual_risk'),
            action_owner,
            new_control_rating,
            new_residual_risk,
            risk_reduction_pct,
            current_date if new_residual_risk else None,
            risk_id
        ))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'message': f'Follow-up saved successfully for {risk_id}',
            'followup_count': current_count + 1,
            'next_followup_date': next_followup_date,
            'status': new_status,
            'new_control_rating': new_control_rating,
            'new_residual_risk': new_residual_risk,
            'risk_reduction_percentage': risk_reduction_pct,
            'agent_3_result': agent_3_result,
            'agent_2_result': agent_2_result
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'Error saving follow-up: {str(e)}'
        }


def _analyze_followup_answers(answers: Dict[str, Any], decision_type: str, current_risk: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ UPDATED: Analyze follow-up answers - removed action-level calculation, use user input only
    
    Args:
        answers: User's answers to follow-up questions
        decision_type: TREAT/ACCEPT/TRANSFER/TERMINATE
        current_risk: Current risk data from database
    
    Returns:
        Dictionary with fields to update
    """
    updates = {}
    
    # Helper function to find answer by keyword
    def find_answer(keyword):
        for key, value in answers.items():
            if keyword.lower() in key.lower():
                return str(value) if value else None
        return None
    
    # ============================================
    # EXTRACT USER-ENTERED COMPLETION PERCENTAGE
    # ============================================
    completion_pct = _extract_completion_percentage(answers)
    if completion_pct >= 0:
        updates['completion_percentage'] = completion_pct
    
    # ============================================
    # PROGRESS SECTION (ALL DECISIONS)
    # ============================================
    
    # Extract expected completion date
    expected_date = find_answer('expected completion date') or find_answer('completion date')
    if expected_date and expected_date != 'None':
        updates['revised_completion_date'] = expected_date
        # Calculate timeline status
        if current_risk.get('target_completion_date'):
            try:
                target = datetime.strptime(current_risk['target_completion_date'], '%Y-%m-%d')
                expected = datetime.strptime(expected_date, '%Y-%m-%d')
                if expected > target:
                    updates['timeline_status'] = 'Delayed'
                elif expected < target:
                    updates['timeline_status'] = 'Ahead of Schedule'
                else:
                    updates['timeline_status'] = 'On Track'
            except:
                pass
    
    return updates


def _extract_completion_percentage(answers: Dict[str, Any]) -> int:
    """✅ FIX: Extract completion percentage from user input - checks multiple field patterns"""
    
    import re
    
    for key, value in answers.items():
        key_lower = key.lower()
        value_str = str(value)
        
        # Priority 1: Look for "overall_completion" or "completion_percentage"
        if ('overall' in key_lower and 'completion' in key_lower) or \
           ('completion' in key_lower and 'percentage' in key_lower):
            try:
                if isinstance(value, (int, float)):
                    return int(value)
                elif isinstance(value, str):
                    value_clean = value.replace('%', '').strip()
                    if value_clean.isdigit() or value_clean.replace('.', '', 1).isdigit():
                        return int(float(value_clean))
            except:
                pass
        
        # Priority 2: Look for "progress" field with numeric value
        if 'progress' in key_lower and 'action' not in key_lower:
            try:
                if isinstance(value, (int, float)):
                    return int(value)
                elif isinstance(value, str):
                    # Try direct conversion first
                    value_clean = value.replace('%', '').strip()
                    if value_clean.isdigit():
                        return int(value_clean)
                    # Search for patterns like "75%", "75 %"
                    match = re.search(r'(\d+)\s*%', value_str)
                    if match:
                        return int(match.group(1))
            except:
                pass
    
    return 0


def _extract_summary(answers: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key metrics from answers for quick reference"""
    
    summary = {}
    
    for key, value in answers.items():
        key_lower = key.lower()
        
        # Extract completion percentage
        if 'completion' in key_lower and 'percentage' in key_lower:
            try:
                summary['completion_percentage'] = float(value)
            except:
                pass
        
        # Extract control effectiveness
        if 'effective' in key_lower and 'control' in key_lower:
            summary['controls_effective'] = str(value)
        
        # Extract implementation status
        if 'implemented' in key_lower or 'status' in key_lower:
            summary['implementation_status'] = str(value)
        
        # Extract risk level changes
        if 'risk' in key_lower and ('reduced' in key_lower or 'impact' in key_lower):
            summary['risk_level_changed'] = str(value)
    
    return summary


def _convert_dates_to_strings(obj: Any) -> Any:
    """
    ✅ FIX: Recursively convert date/datetime objects to strings for JSON serialization
    
    Args:
        obj: Object to convert (dict, list, date, datetime, or primitive)
    
    Returns:
        Object with all dates converted to strings
    """
    from datetime import date, datetime
    
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')
    elif isinstance(obj, dict):
        return {k: _convert_dates_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_dates_to_strings(item) for item in obj]
    else:
        return obj
