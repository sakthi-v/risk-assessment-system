"""
Database Save Module - WITH ACCEPT SUPPORT
Converts all dict/list objects to JSON strings before saving to SQLite
Properly extracts numeric CIA values from Agent 1 results
NOW SUPPORTS ACCEPT WORKFLOW!
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import os


def convert_cia_numeric_to_text(numeric_value: float) -> str:
    """
    Convert numeric CIA rating to text label
    
    Args:
        numeric_value: Numeric rating (0-5)
    
    Returns:
        Text label (Extreme, Very High, High, Medium, Low)
    """
    if numeric_value >= 5:
        return "Extreme"
    elif numeric_value >= 4:
        return "Very High"
    elif numeric_value >= 3:
        return "High"
    elif numeric_value >= 2:
        return "Medium"
    else:
        return "Low"


def convert_dates_to_strings(obj: Any) -> Any:
    """
    Recursively convert date/datetime objects to ISO format strings
    
    Args:
        obj: Any object (dict, list, date, datetime, etc.)
    
    Returns:
        Object with all dates converted to strings
    """
    from datetime import date, datetime
    
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')
    elif isinstance(obj, dict):
        return {key: convert_dates_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_dates_to_strings(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_dates_to_strings(item) for item in obj)
    else:
        return obj


def ensure_json_serializable(obj: Any) -> str:
    """
    Convert any object to JSON string for database storage
    
    Args:
        obj: Any object (dict, list, str, int, date, datetime, etc.)
    
    Returns:
        JSON string or original value if already string/None
    """
    if obj is None:
        return None
    
    if isinstance(obj, str):
        # Already a string, check if it's valid JSON
        try:
            json.loads(obj)
            return obj  # Already valid JSON string
        except:
            return obj  # Plain string, return as-is
    
    if isinstance(obj, (dict, list)):
        # First convert any date/datetime objects to strings
        obj_converted = convert_dates_to_strings(obj)
        # Then convert to JSON string
        return json.dumps(obj_converted, indent=2)
    
    # For other types (int, float, bool), return as-is
    return obj


def generate_mitigation_plan(treatment_decision: str, treatment_plan: Dict = None, acceptance_form: Dict = None, transfer_form: Dict = None, terminate_form: Dict = None) -> str:
    """
    Generate human-readable mitigation plan text from treatment decision
    Mitigation Plan = Preventive steps to reduce likelihood (as per Excel definition)
    
    Args:
        treatment_decision: TREAT, ACCEPT, TRANSFER, or TERMINATE
        treatment_plan: Treatment plan dict (for TREAT)
        acceptance_form: Acceptance form dict (for ACCEPT)
        transfer_form: Transfer form dict (for TRANSFER)
        terminate_form: Terminate form dict (for TERMINATE)
    
    Returns:
        Mitigation plan text (preventive steps)
    """
    if treatment_decision == 'TREAT' and treatment_plan:
        actions = treatment_plan.get('treatment_actions', [])
        if actions:
            plan_parts = []
            for i, action in enumerate(actions, 1):
                desc = action.get('description_of_activities', action.get('description', ''))
                if desc:
                    plan_parts.append(f"{i}. {desc}")
            return " ".join(plan_parts) if plan_parts else "Implement treatment actions to reduce risk likelihood"
        return "Implement treatment actions to reduce risk likelihood"
    
    elif treatment_decision == 'ACCEPT' and acceptance_form:
        controls = []
        comp_controls = acceptance_form.get('compensating_controls', {})
        if isinstance(comp_controls, dict):
            controls = comp_controls.get('selected_controls', [])
        if not controls:
            controls = acceptance_form.get('selected_controls', [])
        
        if controls:
            plan_parts = []
            for i, ctrl in enumerate(controls, 1):
                if isinstance(ctrl, dict):
                    # Try multiple keys for control name
                    name = ctrl.get('control_name') or ctrl.get('label') or ctrl.get('name') or ctrl.get('gap_description') or ctrl.get('description')
                    if name:
                        plan_parts.append(f"{i}. {name}")
                    else:
                        plan_parts.append(f"{i}. Control {i}")
                elif isinstance(ctrl, str):
                    plan_parts.append(f"{i}. {ctrl}")
                else:
                    plan_parts.append(f"{i}. Control {i}")
            return " ".join(plan_parts) if plan_parts else "Implement compensating controls to reduce risk likelihood"
        return "Implement compensating controls to reduce risk likelihood"
    
    elif treatment_decision == 'TRANSFER' and transfer_form:
        # Extract transfer details from questionnaire answers (based on Risk Transfer template_Use case v1.0.xlsx)
        plan_parts = []
        if isinstance(transfer_form, dict):
            # Extract from sections structure (AI-generated format)
            sections = transfer_form.get('sections', [])
            transfer_data = {}
            
            if sections:
                for section in sections:
                    fields = section.get('fields', [])
                    for field in fields:
                        field_name = field.get('field_name', '')
                        field_value = field.get('value')
                        
                        # Match exact field names
                        if field_name == 'Transfer Method':
                            transfer_data['transfer_method'] = field_value
                        elif field_name == 'Third Party Name':
                            transfer_data['third_party_name'] = field_value
                        elif field_name == 'Scope of Transfer':
                            transfer_data['scope_of_transfer'] = field_value
                        elif field_name == 'Contract Reference ID':
                            transfer_data['contract_reference'] = field_value
                        elif field_name == 'Review Frequency':
                            transfer_data['review_frequency'] = field_value
            
            # Fallback to direct keys
            if not transfer_data:
                transfer_data = transfer_form
            
            # Build mitigation plan text
            transfer_method = transfer_data.get('transfer_method', transfer_data.get('mechanism'))
            if transfer_method:
                plan_parts.append(f"Method: {transfer_method}")
            
            third_party = transfer_data.get('third_party_name', transfer_data.get('transfer_to'))
            if third_party:
                plan_parts.append(f"Third Party: {third_party}")
            
            scope = transfer_data.get('scope_of_transfer', transfer_data.get('scope'))
            if scope:
                # Truncate scope if too long
                scope_text = scope[:150] + '...' if len(scope) > 150 else scope
                plan_parts.append(f"Scope: {scope_text}")
            
            contract_ref = transfer_data.get('contract_reference')
            if contract_ref:
                plan_parts.append(f"Contract: {contract_ref}")
        
        return " | ".join(plan_parts) if plan_parts else "Transfer risk to third party (insurance/vendor) to reduce organizational exposure"
    
    elif treatment_decision == 'TERMINATE' and terminate_form:
        # Extract termination details from form sections structure
        plan_parts = []
        if isinstance(terminate_form, dict):
            # Extract from wrapper if present
            form = terminate_form.get('risk_termination_form', terminate_form)
            
            # Extract from sections structure
            sections = form.get('sections', [])
            termination_data = {}
            
            if sections:
                for section in sections:
                    fields = section.get('fields', [])
                    for field in fields:
                        field_name = field.get('field_name', '')
                        field_value = field.get('value')
                        
                        # Match exact field names
                        if field_name == 'Termination Justification' or field_name == 'Justification':
                            termination_data['justification'] = field_value
                        elif field_name == 'Termination Actions' or field_name == 'Actions':
                            termination_data['actions'] = field_value
                        elif field_name == 'Termination Completion Date' or field_name == 'Completion Date':
                            termination_data['completion_date'] = field_value
                        elif field_name == 'Closure Status':
                            termination_data['status'] = field_value
            
            # Fallback to direct keys
            if not termination_data:
                termination_data = form
            
            # Build mitigation plan text from actual fields
            justification = termination_data.get('justification')
            if justification:
                plan_parts.append(f"Justification: {justification}")
            
            actions = termination_data.get('actions')
            if actions:
                plan_parts.append(f"Actions: {actions}")
            
            completion_date = termination_data.get('completion_date')
            if completion_date:
                plan_parts.append(f"Target: {completion_date}")
            
            status = termination_data.get('status')
            if status:
                plan_parts.append(f"Status: {status}")
        
        return " | ".join(plan_parts) if plan_parts else "Terminate the activity/asset to eliminate the risk"
    
    else:
        return "Mitigation plan pending - awaiting management decision"


def save_assessment_to_risk_register(
    asset_data: Dict[str, Any],
    agent_1_results: Dict[str, Any],
    agent_2_results: Dict[str, Any],
    agent_3_results: Dict[str, Any],
    agent_4_results: Dict[str, Any]
) -> List[str]:
    """
    Save complete risk assessment to Risk Register database
    
    Returns:
        List of created risk IDs
    """
    
    print("\n" + "="*80)
    print("💾 SAVING RISK ASSESSMENT TO RISK REGISTER")
    print("="*80)
    
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'risk_register.db')
    db_path = os.path.normpath(db_path)
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Risk register database not found at: {db_path}")
    
    print(f"✅ Risk register database found at: {db_path}\n")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    risk_ids = []
    
    try:
        # Extract asset info
        asset_name = asset_data.get('asset_name', 'Unknown Asset')
        asset_type = asset_data.get('asset_type', asset_data.get('type', 'Unknown'))
        asset_description = asset_data.get('description', '')
        
        # Extract threat data
        threats = agent_2_results.get('threat_risk_quantification', [])
        
        print(f"📊 Processing {len(threats)} threat(s) for: {asset_name}\n")
        
        for idx, threat in enumerate(threats, 1):
            print(f"--- Processing Threat {idx}/{len(threats)} ---")
            
            try:
                # Extract threat info
                threat_name = threat.get('threat', 'Unknown Threat')
                threat_description = threat.get('threat_description', threat.get('risk_statement', ''))
                threat_scenario = threat.get('threat_scenario', '')
                
                # ✅ FIX: If threat_description is still empty, create a meaningful one
                if not threat_description or threat_description == '':
                    threat_description = f"Security risk to {asset_name} ({asset_type}) - {threat_name}"
                
                print(f"Threat: {threat_name}")
                
                # Extract risk ratings from Agent 2
                risk_eval = threat.get('risk_evaluation_rating', {})
                if isinstance(risk_eval, dict):
                    risk_rating = risk_eval.get('rating', 0)
                    risk_level = risk_eval.get('level', 'Unknown')
                else:
                    risk_rating = risk_eval if risk_eval else 0
                    risk_level = 'Unknown'
                
                # Extract likelihood and impact from Agent 2
                risk_prob = threat.get('risk_probability', {})
                if isinstance(risk_prob, dict):
                    likelihood_rating = risk_prob.get('rating', 0)
                else:
                    likelihood_rating = risk_prob if risk_prob else 0
                
                risk_impact = threat.get('risk_impact', {})
                if isinstance(risk_impact, dict):
                    impact_rating = risk_impact.get('rating', 0)
                else:
                    impact_rating = risk_impact if risk_impact else 0
                
                # ✅ FIXED: Extract CIA values from Agent 1 - try multiple structures
                confidentiality_rating = 0
                integrity_rating = 0
                availability_rating = 0
                
                # Try threat_analysis structure first (new format)
                if 'threat_analysis' in agent_1_results:
                    threat_analysis = agent_1_results['threat_analysis']
                    for t_analysis in threat_analysis:
                        if t_analysis.get('threat') == threat_name:
                            impact_assessment = t_analysis.get('impact_assessment', {})
                            
                            conf_data = impact_assessment.get('confidentiality', {})
                            if isinstance(conf_data, dict):
                                confidentiality_rating = conf_data.get('numeric_value', 0)
                            
                            int_data = impact_assessment.get('integrity', {})
                            if isinstance(int_data, dict):
                                integrity_rating = int_data.get('numeric_value', 0)
                            
                            avail_data = impact_assessment.get('availability', {})
                            if isinstance(avail_data, dict):
                                availability_rating = avail_data.get('numeric_value', 0)
                            break
                
                # Fallback to old structure
                if not confidentiality_rating and 'threat_cia_impact' in agent_1_results:
                    for t_cia in agent_1_results['threat_cia_impact']:
                        if t_cia.get('threat') == threat_name:
                            cia_impact = t_cia.get('cia_impact_calculation', {})
                            
                            conf_data = cia_impact.get('confidentiality', {})
                            if isinstance(conf_data, dict):
                                confidentiality_rating = conf_data.get('numeric_value', 0)
                            
                            int_data = cia_impact.get('integrity', {})
                            if isinstance(int_data, dict):
                                integrity_rating = int_data.get('numeric_value', 0)
                            
                            avail_data = cia_impact.get('availability', {})
                            if isinstance(avail_data, dict):
                                availability_rating = avail_data.get('numeric_value', 0)
                            break
                
                # Convert to float
                try:
                    confidentiality_rating = float(confidentiality_rating) if confidentiality_rating else 0
                    integrity_rating = float(integrity_rating) if integrity_rating else 0
                    availability_rating = float(availability_rating) if availability_rating else 0
                except (ValueError, TypeError):
                    pass
                
                # Extract control evaluation (from Agent 3)
                control_data = None
                if 'threat_control_evaluation' in agent_3_results:
                    control_eval = agent_3_results['threat_control_evaluation']
                    for ctrl in control_eval:
                        if ctrl.get('threat') == threat_name:
                            control_data = ctrl
                            break
                
                # Extract control info
                if control_data:
                    existing_controls = control_data.get('controls_identified', [])
                    recommended_controls = control_data.get('recommended_controls', [])
                    control_rating = control_data.get('control_rating_calculation', {}).get('control_rating', 0)
                    residual_risk_data = control_data.get('residual_risk', {})
                    residual_risk_value = residual_risk_data.get('residual_risk_value', 0)
                    residual_risk_level = residual_risk_data.get('residual_risk_level', 'Unknown')
                    control_gaps = control_data.get('control_gaps', [])
                else:
                    existing_controls = []
                    recommended_controls = []
                    control_rating = 0
                    residual_risk_value = risk_rating
                    residual_risk_level = risk_level
                    control_gaps = []
                
                # Extract treatment plan (from Agent 4)
                treatment_plan = None
                rtp_answers = None
                treatment_decision = 'Pending'
                risk_owner = 'Unassigned'
                priority = 'Medium'
                target_date = None
                
                # ✅ NEW: Calculate target date from treatment plan duration
                from datetime import datetime, timedelta
                
                # ✅ NEW: ACCEPT data fields
                acceptance_reason = None
                business_justification = None
                cost_benefit_analysis = None
                monitoring_plan = None
                approval_status = None
                valid_until_date = None
                review_frequency = None
                next_review_date = None
                approver_risk_owner = None
                approver_ciso = None
                approver_cio = None
                acceptance_form = None
                
                # ✅ FIX: Extract TRANSFER and TERMINATE forms
                transfer_form = None
                terminate_form = None
                
                if agent_4_results:
                    # 🆕 FIX: Check for management_decision first (from email workflow)
                    if 'management_decision' in agent_4_results:
                        treatment_decision = agent_4_results['management_decision']
                    
                    # Check if treatment plan exists (TREAT decision)
                    if 'treatment_plan' in agent_4_results:
                        treatment_plan = agent_4_results['treatment_plan']
                        treatment_decision = treatment_plan.get('treatment_option', treatment_plan.get('treatment_decision', 'TREAT'))
                        risk_owner = treatment_plan.get('risk_owner', 'Unassigned')
                        
                        # ✅ FIX: Calculate priority from risk rating
                        if risk_rating >= 4:
                            priority = 'Critical'
                        elif risk_rating >= 3:
                            priority = 'High'
                        else:
                            priority = 'Medium'
                        
                        # ✅ FIX: Calculate target date from treatment plan duration
                        target_date = treatment_plan.get('target_completion_date')
                        if not target_date:
                            # Get longest completion date from treatment actions
                            actions = treatment_plan.get('treatment_actions', [])
                            if actions:
                                completion_dates = []
                                for action in actions:
                                    comp_date = action.get('proposed_completion_date')
                                    if comp_date:
                                        completion_dates.append(comp_date)
                                if completion_dates:
                                    # Use the latest completion date as target
                                    target_date = max(completion_dates)
                            
                            # Fallback: calculate from total duration
                            if not target_date:
                                summary = treatment_plan.get('summary', {})
                                total_days = summary.get('total_duration_days', 90)
                                if isinstance(total_days, str):
                                    try:
                                        total_days = int(total_days.split()[0])
                                    except:
                                        total_days = 90
                                target_date = (datetime.now() + timedelta(days=total_days)).strftime('%Y-%m-%d')
                    
                    # ✅ NEW: Check if acceptance form exists (ACCEPT decision)
                    if 'acceptance_form' in agent_4_results:
                        acceptance_form = agent_4_results['acceptance_form']
                        treatment_decision = 'ACCEPT'
                        
                        # Extract acceptance data - FLEXIBLE for ANY AI-generated structure
                        if isinstance(acceptance_form, dict):
                            # Extract risk description from risk_context
                            risk_context = acceptance_form.get('risk_context', {})
                            if risk_context:
                                threat_description = risk_context.get('risk_description', threat_description)
                            
                            # Extract justification - try multiple possible locations
                            justification_section = acceptance_form.get('justification', {})
                            if justification_section:
                                acceptance_reason = justification_section.get('justification_text') or justification_section.get('justification')
                                valid_until_date = justification_section.get('valid_until_date') or justification_section.get('valid_until')
                            
                            # Fallback: check if justification is at root level
                            if not acceptance_reason:
                                acceptance_reason = acceptance_form.get('justification_text') or acceptance_form.get('justification')
                            if not valid_until_date:
                                valid_until_date = acceptance_form.get('valid_until_date') or acceptance_form.get('valid_until')
                            
                            # ✅ FIX: Set target_date to valid_until_date for ACCEPT workflow
                            target_date = valid_until_date
                            
                            # Extract engagement/project info
                            engagement_project = acceptance_form.get('engagement_project', {})
                            if engagement_project:
                                # Store as business justification
                                business_justification = ensure_json_serializable(engagement_project)
                            
                            # ✅ FIX: Keep Agent 3 recommended controls (don't overwrite with gaps from ACCEPT form)
                            # The ACCEPT form contains control GAPS, not actual controls
                            # Agent 3 already populated recommended_controls above, so we keep those
                            
                            # Extract approvals - flexible for any structure
                            approvals = acceptance_form.get('approvals', {})
                            if approvals:
                                # Extract owner info
                                owner_info = approvals.get('owner', {})
                                if isinstance(owner_info, dict):
                                    risk_owner = owner_info.get('name', risk_owner)  # ✅ FIX: Keep existing if not found
                                    approver_risk_owner = ensure_json_serializable(owner_info)
                                elif isinstance(owner_info, str):
                                    risk_owner = owner_info
                                
                                # Extract approver info
                                approver_info = approvals.get('approver', {})
                                if isinstance(approver_info, dict):
                                    approver_ciso = ensure_json_serializable(approver_info)
                                elif isinstance(approver_info, str):
                                    approver_ciso = approver_info
                                
                                approval_status = 'Pending Approval'
                            
                            # Fallback: check root level for owner/approver
                            if not risk_owner or risk_owner == 'Unassigned':
                                risk_owner = acceptance_form.get('risk_owner') or acceptance_form.get('owner_name', 'Unassigned')
                            if not approver_ciso:
                                approver_ciso = acceptance_form.get('approver_name') or acceptance_form.get('approved_by')
                            
                            # Extract signoff (but don't overwrite target_date)
                            signoff = acceptance_form.get('signoff', {})
                            # Note: target_date already set to valid_until_date above
                            
                            # Set monitoring plan (auto-generated for high risks)
                            if risk_rating >= 4:
                                review_frequency = 'Monthly'
                            elif risk_rating >= 3:
                                review_frequency = 'Quarterly'
                            else:
                                review_frequency = 'Annually'
                            
                            monitoring_plan = ensure_json_serializable({
                                'review_frequency': review_frequency,
                                'next_review_date': valid_until_date,
                                'monitoring_required': 'Yes - Risk accepted with compensating controls'
                            })
                            next_review_date = valid_until_date
                            
                            # Set priority based on risk rating
                            if risk_rating >= 4:
                                priority = 'High'
                            elif risk_rating >= 3:
                                priority = 'Medium'
                            else:
                                priority = 'Low'
                    
                    # ✅ NEW: Check if transfer form exists (TRANSFER decision)
                    if 'transfer_form' in agent_4_results or 'transfer_questionnaire_answers' in agent_4_results:
                        transfer_form_raw = agent_4_results.get('transfer_form') or agent_4_results.get('transfer_questionnaire_answers')
                        treatment_decision = 'TRANSFER'
                        
                        # ✅ FIX: Extract from wrapper if present
                        if isinstance(transfer_form_raw, dict) and 'risk_transfer_form' in transfer_form_raw:
                            transfer_form_inner = transfer_form_raw.get('risk_transfer_form')
                        else:
                            transfer_form_inner = transfer_form_raw
                        
                        if isinstance(transfer_form_inner, dict):
                            # Extract from sections structure
                            sections = transfer_form_inner.get('sections', [])
                            if sections:
                                for section in sections:
                                    fields = section.get('fields', [])
                                    for field in fields:
                                        field_name = field.get('field_name', '')
                                        field_value = field.get('value')
                                        
                                        # Match exact field names from transfer form
                                        if field_name == 'Risk Owner':
                                            risk_owner = field_value
                                        elif field_name == 'Transfer End Date':
                                            target_date = field_value
                                        elif field_name == 'Review Frequency':
                                            review_frequency = field_value
                                        elif field_name == 'Transfer Start Date':
                                            # Could use as identified date if needed
                                            pass
                            
                            # Fallback to direct keys
                            if not risk_owner or risk_owner == 'Unassigned':
                                risk_owner = transfer_form_inner.get('risk_owner', transfer_form_inner.get('owner_name', risk_owner))
                            if not target_date:
                                target_date = transfer_form_inner.get('transfer_end_date', transfer_form_inner.get('transfer_completion_date', transfer_form_inner.get('target_date')))
                            if not next_review_date:
                                next_review_date = transfer_form_inner.get('next_review_date')
                            if not review_frequency:
                                review_frequency = transfer_form_inner.get('review_frequency', 'Quarterly')
                            
                            priority = 'Medium'
                        
                        # ✅ FIX: Store the raw form (with wrapper) for database
                        transfer_form = transfer_form_raw
                    
                    # ✅ NEW: Check if terminate form exists (TERMINATE decision)
                    if 'terminate_form' in agent_4_results or 'terminate_questionnaire_answers' in agent_4_results:
                        terminate_form_raw = agent_4_results.get('terminate_form') or agent_4_results.get('terminate_questionnaire_answers')
                        treatment_decision = 'TERMINATE'
                        
                        # ✅ FIX: Use Asset Owner from Agent 0 questionnaire (asset_data)
                        asset_owner = asset_data.get('asset_owner') or asset_data.get('owner')
                        if asset_owner:
                            risk_owner = asset_owner
                        
                        # ✅ FIX: Extract from wrapper if present
                        if isinstance(terminate_form_raw, dict) and 'risk_termination_form' in terminate_form_raw:
                            terminate_form_inner = terminate_form_raw.get('risk_termination_form')
                        else:
                            terminate_form_inner = terminate_form_raw
                        
                        if isinstance(terminate_form_inner, dict):
                            # Extract from sections structure
                            sections = terminate_form_inner.get('sections', [])
                            if sections:
                                for section in sections:
                                    fields = section.get('fields', [])
                                    for field in fields:
                                        field_name = field.get('field_name', '')
                                        field_value = field.get('value')
                                        
                                        # Match exact field names from terminate form
                                        if field_name == 'Risk Owner' or field_name == 'Approval Authority':
                                            # Extract first name before comma for Approval Authority
                                            if ',' in str(field_value):
                                                risk_owner = field_value.split(',')[0].strip()
                                            else:
                                                risk_owner = field_value
                                        elif field_name == 'Termination Completion Date' or field_name == 'Completion Date':
                                            target_date = field_value
                                        elif field_name == 'Closure Status':
                                            closure_status = field_value
                                            if field_value and 'closed' in str(field_value).lower():
                                                approval_status = 'Terminated - Closed'
                                            else:
                                                approval_status = 'Pending Termination'
                            
                            # Fallback to direct keys
                            if not target_date:
                                target_date = terminate_form_inner.get('completion_date', terminate_form_inner.get('termination_date'))
                            
                            priority = 'High'
                        
                        # ✅ FIX: Store the raw form (with wrapper) for database
                        terminate_form = terminate_form_raw
                    
                    # Check if RTP answers exist (Agent 4 Part 1 output)
                    if 'rtp_answers' in agent_4_results:
                        rtp_answers = agent_4_results['rtp_answers']
                        
                        # If no treatment plan and no acceptance form, extract from answers
                        if not treatment_plan and not acceptance_form:
                            treatment_decision = rtp_answers.get('Q1.1', 'Pending')
                            risk_owner = rtp_answers.get('Q1.3', 'Unassigned')
                            priority = rtp_answers.get('Q1.5', 'Medium')
                            target_date = rtp_answers.get('Q1.4')
                
                # Get next sequential risk ID from database
                cursor.execute("SELECT MAX(CAST(SUBSTR(risk_id, 6) AS INTEGER)) FROM risks WHERE risk_id LIKE 'RSK-%'")
                result = cursor.fetchone()
                next_num = (result[0] or 0) + 1
                risk_id = f"RSK-{next_num:03d}"
                
                # ✅ NEW: Generate mitigation plan text with all decision types
                mitigation_plan = generate_mitigation_plan(treatment_decision, treatment_plan, acceptance_form, transfer_form, terminate_form)
                
                # ✅ FIX: Set risk_title = threat_name
                risk_title = threat_name
                
                # ✅ FIX: Set status based on treatment decision and closure status
                risk_status = 'Open'
                if treatment_decision == 'TERMINATE' and approval_status == 'Terminated - Closed':
                    risk_status = 'Closed'
                
                # Prepare data for insertion
                current_date = datetime.now().strftime('%Y-%m-%d')
                
                insert_data = (
                    risk_id,                                            # risk_id
                    asset_name,                                         # asset_name
                    asset_type,                                         # asset_type
                    threat_name,                                        # threat_name
                    threat_description,                                 # threat_description
                    risk_rating,                                        # inherent_risk_rating
                    risk_level,                                         # inherent_risk_level
                    likelihood_rating,                                  # likelihood_rating
                    convert_cia_numeric_to_text(confidentiality_rating),  # confidentiality_impact
                    convert_cia_numeric_to_text(integrity_rating),      # integrity_impact
                    convert_cia_numeric_to_text(availability_rating),   # availability_impact
                    ensure_json_serializable(existing_controls),        # existing_controls
                    control_rating,                                     # control_rating
                    residual_risk_value,                                # residual_risk_rating
                    residual_risk_level,                                # residual_risk_level
                    ensure_json_serializable(control_gaps),             # control_gaps
                    ensure_json_serializable(recommended_controls),     # recommended_controls
                    ensure_json_serializable(treatment_plan),           # treatment_plan
                    ensure_json_serializable(rtp_answers),              # rtp_answers
                    treatment_decision,                                 # treatment_decision
                    risk_owner,                                         # risk_owner
                    priority,                                           # priority
                    target_date,                                        # target_completion_date
                    risk_status,                                        # status
                    current_date,                                       # identified_date
                    current_date,                                       # last_updated
                    None,                                               # review_date
                    None,                                               # closure_date
                    None,                                               # comments
                    ensure_json_serializable(agent_1_results),          # agent_1_raw
                    ensure_json_serializable(agent_2_results),          # agent_2_raw
                    ensure_json_serializable(agent_3_results),          # agent_3_raw
                    ensure_json_serializable(agent_4_results),          # agent_4_raw
                    acceptance_reason,                                  # acceptance_reason
                    business_justification,                             # business_justification
                    cost_benefit_analysis,                              # cost_benefit_analysis
                    monitoring_plan,                                    # monitoring_plan
                    approval_status,                                    # approval_status
                    valid_until_date,                                   # valid_until_date
                    review_frequency,                                   # review_frequency
                    next_review_date,                                   # next_review_date
                    approver_risk_owner,                                # approver_risk_owner
                    approver_ciso,                                      # approver_ciso
                    approver_cio,                                       # approver_cio
                    ensure_json_serializable(acceptance_form),          # acceptance_form
                    mitigation_plan,                                    # mitigation_plan
                    'PENDING',                                          # followup_status
                    None,                                               # followup_date
                    None,                                               # followup_answers
                    ensure_json_serializable(transfer_form),            # transfer_form
                    ensure_json_serializable(terminate_form),           # terminate_form
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')        # created_at
                )
                
                # Insert into database
                cursor.execute("""
                    INSERT INTO risks (
                        risk_id, asset_name, asset_type, threat_name, threat_description,
                        inherent_risk_rating, inherent_risk_level, likelihood_rating,
                        confidentiality_impact, integrity_impact, availability_impact,
                        existing_controls, control_rating, residual_risk_rating, residual_risk_level,
                        control_gaps, recommended_controls, treatment_plan, rtp_answers,
                        treatment_decision, risk_owner, priority, target_completion_date,
                        status, identified_date, last_updated, review_date, closure_date, comments,
                        agent_1_raw, agent_2_raw, agent_3_raw, agent_4_raw,
                        acceptance_reason, business_justification, cost_benefit_analysis, monitoring_plan,
                        approval_status, valid_until_date, review_frequency, next_review_date,
                        approver_risk_owner, approver_ciso, approver_cio, acceptance_form,
                        mitigation_plan, followup_status, followup_date, followup_answers,
                        transfer_form, terminate_form, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, insert_data)
                
                risk_ids.append(risk_id)
                print(f"✅ Saved: {risk_id}\n")
                
            except Exception as e:
                print(f"❌ Error saving threat {idx}: {str(e)}\n")
                import traceback
                print(traceback.format_exc())
                continue
        
        # ✅ NEW: Update questionnaire status to 'saved' using token (if available)
        # This makes questionnaires disappear from the UI after saving to Risk Register
        try:
            import streamlit as st
            if hasattr(st, 'session_state') and hasattr(st.session_state, 'loaded_questionnaire_token'):
                # Use token for precise update
                cursor.execute("""
                    UPDATE pending_questionnaires 
                    SET status = 'saved' 
                    WHERE token = ?
                """, (st.session_state.loaded_questionnaire_token,))
            else:
                # Fallback: Update by asset_name (old behavior)
                cursor.execute("""
                    UPDATE pending_questionnaires 
                    SET status = 'saved' 
                    WHERE asset_name = ? AND status = 'completed'
                """, (asset_name,))
        except:
            # If streamlit not available (shouldn't happen), use asset_name
            cursor.execute("""
                UPDATE pending_questionnaires 
                SET status = 'saved' 
                WHERE asset_name = ? AND status = 'completed'
            """, (asset_name,))
        
        # Commit all changes
        conn.commit()
        
        print("="*80)
        print(f"✅ SUCCESSFULLY SAVED {len(risk_ids)} RISK(S) TO REGISTER!")
        print("="*80)
        print(f"Risk IDs: {', '.join(risk_ids)}\n")
        
        return risk_ids
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error saving to database: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise
    
    finally:
        conn.close()


if __name__ == "__main__":
    print("Database Save Module - WITH ACCEPT SUPPORT")
    print("This module saves risk assessments to the Risk Register database")
    print("Now supports BOTH TREAT and ACCEPT workflows!")