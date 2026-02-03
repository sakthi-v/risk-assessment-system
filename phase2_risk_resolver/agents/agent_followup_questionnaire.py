"""
Agent Follow-up Questionnaire Generator - RAG-Powered
Discovers follow-up fields from Follow-up template using RAG
"""

from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import json
from datetime import datetime
from typing import Dict, Any
import os

@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base for follow-up template"""
    from phase2_risk_resolver.tools.rag_tool import search_knowledge_base_function
    return search_knowledge_base_function(query, use_cache=False)  # No cache for questionnaires

def create_followup_questionnaire_agent(api_key: str) -> Agent:
    """Create agent for follow-up questionnaire generation"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.0
    )
    
    agent = Agent(
        role="Follow-up Questionnaire Generator",
        goal="Generate follow-up questionnaire by discovering fields from Follow-up template using RAG",
        backstory="""You are an expert at generating follow-up questionnaires for risk treatment tracking.
        You use RAG to discover what fields are needed from the organization's Follow-up template,
        then create a questionnaire that matches their format exactly.""",
        llm=llm,
        tools=[search_knowledge_base],
        verbose=True,
        allow_delegation=False
    )
    
    return agent


def generate_followup_questionnaire(risk_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate follow-up questionnaire using RAG discovery with API key rotation
    
    Args:
        risk_context: Dict with risk_id, asset_name, threat_name, treatment_decision, etc.
    
    Returns:
        Questionnaire JSON with discovered fields
    """
    
    from api_key_manager import get_active_api_key, get_api_key_manager
    from phase2_risk_resolver.database.risk_register_db import RiskRegisterDB
    # Memory cache removed - using RAG only
    
    # Get treatment decision for template key
    decision = risk_context.get('treatment_decision', 'TREAT')
    template_key = f"{decision}_FOLLOWUP"
    
    # 🆕 NEW: Check template cache first
    # Cache disabled
    
    if False:  # Cache disabled
        print("\n" + "="*80)
        print(f"✅ USING CACHED {decision} FOLLOWUP TEMPLATE (0 API calls)")
        print("="*80)
        
        # Update risk context in cached template
        risk_id = risk_context.get('risk_id')
        asset_name = risk_context.get('asset_name', 'Unknown')
        threat_name = risk_context.get('threat_name', 'Unknown')
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        cached_template['risk_context'] = {
            'risk_id': risk_id,
            'asset': asset_name,
            'threat': threat_name,
            'treatment_decision': decision
        }
        
        cached_template['questionnaire_metadata'] = {
            'questionnaire_type': f"{decision} Follow-up",
            'generation_date': current_date,
            'days_since_identification': risk_context.get('days_since_creation', 0),
            'target_completion_date': risk_context.get('target_date', 'N/A'),
            'days_until_target': risk_context.get('days_until_target', 'N/A')
        }
        
        print(f"💾 Using cached template")
        print("="*80 + "\n")
        
        return cached_template
    
    # If not cached, generate using RAG and save to cache
    print("\n" + "="*80)
    print(f"🤖 GENERATING {decision} FOLLOWUP TEMPLATE VIA RAG (will cache for future)")
    print("="*80)
    
    # 🔧 FIX: Load treatment_actions from database based on decision type
    db = RiskRegisterDB()
    risk_id = risk_context.get('risk_id')
    risk_data = db.get_risk(risk_id)
    
    treatment_actions = []
    decision = risk_context.get('treatment_decision', '')
    
    if risk_data:
        try:
            if decision == 'TREAT':
                # For TREAT: Get from treatment_actions or treatment_plan
                actions_json = risk_data.get('treatment_actions') or risk_data.get('treatment_plan')
                if actions_json:
                    if isinstance(actions_json, str):
                        data = json.loads(actions_json)
                        # Extract actions from treatment_plan if it's a dict
                        if isinstance(data, dict):
                            treatment_actions = data.get('actions', data.get('treatment_actions', []))
                        elif isinstance(data, list):
                            treatment_actions = data
                    elif isinstance(actions_json, list):
                        treatment_actions = actions_json
            
            elif decision == 'ACCEPT':
                # For ACCEPT: Get compensating_controls from acceptance_form
                acceptance_form = risk_data.get('acceptance_form')
                if acceptance_form:
                    if isinstance(acceptance_form, str):
                        form_data = json.loads(acceptance_form)
                    else:
                        form_data = acceptance_form
                    treatment_actions = form_data.get('compensating_controls', [])
            
            elif decision == 'TRANSFER':
                # For TRANSFER: Get from transfer_form
                transfer_form = risk_data.get('transfer_form')
                if transfer_form:
                    if isinstance(transfer_form, str):
                        form_data = json.loads(transfer_form)
                    else:
                        form_data = transfer_form
                    # Extract relevant tracking items from transfer form
                    treatment_actions = form_data.get('transfer_actions', [])
            
            elif decision == 'TERMINATE':
                # For TERMINATE: Get from terminate_form
                terminate_form = risk_data.get('terminate_form')
                if terminate_form:
                    if isinstance(terminate_form, str):
                        form_data = json.loads(terminate_form)
                    else:
                        form_data = terminate_form
                    # Extract termination steps
                    treatment_actions = form_data.get('termination_steps', [])
        except Exception as e:
            print(f"Error loading actions: {e}")
            treatment_actions = []
    
    # 🆕 NEW: Extract reason_for_acceptance for ACCEPT decisions
    reason_for_acceptance = ""
    if decision == 'ACCEPT' and risk_data:
        try:
            acceptance_form = risk_data.get('acceptance_form')
            if acceptance_form:
                if isinstance(acceptance_form, str):
                    form_data = json.loads(acceptance_form)
                else:
                    form_data = acceptance_form
                # Try multiple possible field names
                reason_for_acceptance = (
                    form_data.get('reason_for_acceptance') or 
                    form_data.get('justification', {}).get('justification_text') or
                    form_data.get('justification', {}).get('reason_for_acceptance') or
                    form_data.get('justification', {}).get('justification_for_acceptance') or
                    ""
                )
        except Exception as e:
            print(f"Error extracting reason_for_acceptance: {e}")
    
    # 🆕 NEW: Extract transfer details for TRANSFER decisions
    transfer_method = ""
    third_party_name = ""
    scope_of_transfer = ""
    if decision == 'TRANSFER' and risk_data:
        try:
            transfer_form = risk_data.get('transfer_form')
            if transfer_form:
                if isinstance(transfer_form, str):
                    form_data = json.loads(transfer_form)
                else:
                    form_data = transfer_form
                # 🔧 FIX: Search ALL sections, not just first one
                sections = form_data.get('sections', [])
                for section in sections:
                    fields = section.get('fields', [])
                    for field in fields:
                        field_name = field.get('field_name', '')
                        if field_name == 'Transfer Method':
                            transfer_method = field.get('value', '')
                        elif field_name == 'Third Party Name':
                            third_party_name = field.get('value', '')
                        elif field_name == 'Scope of Transfer':
                            scope_of_transfer = field.get('value', '')
        except Exception as e:
            print(f"Error extracting transfer details: {e}")
    
    # 🆕 NEW: Extract termination details for TERMINATE decisions
    termination_justification = ""
    business_impact = ""
    termination_actions_text = ""
    if decision == 'TERMINATE' and risk_data:
        try:
            terminate_form = risk_data.get('terminate_form')
            if terminate_form:
                if isinstance(terminate_form, str):
                    form_data = json.loads(terminate_form)
                else:
                    form_data = terminate_form
                # Extract from sections[1].fields array (Risk Termination Details section)
                sections = form_data.get('sections', [])
                if sections and len(sections) > 1:
                    fields = sections[1].get('fields', [])
                    for field in fields:
                        field_name = field.get('field_name', '')
                        if field_name == 'Termination Justification':
                            termination_justification = field.get('value', '')
                        elif field_name == 'Business Impact':
                            business_impact = field.get('value', '')
                        elif field_name == 'Termination Actions':
                            termination_actions_text = field.get('value', '')
        except Exception as e:
            print(f"Error extracting termination details: {e}")
    
    # Add to risk_context for agent
    risk_context['treatment_actions'] = treatment_actions
    risk_context['num_actions'] = len(treatment_actions)
    risk_context['reason_for_acceptance'] = reason_for_acceptance
    risk_context['transfer_method'] = transfer_method
    risk_context['third_party_name'] = third_party_name
    risk_context['scope_of_transfer'] = scope_of_transfer
    risk_context['termination_justification'] = termination_justification
    risk_context['business_impact'] = business_impact
    risk_context['termination_actions_text'] = termination_actions_text
    
    max_retries = 6  # Match other agents' retry limit
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            api_key = get_active_api_key()
            
            agent = create_followup_questionnaire_agent(api_key)
            
            risk_id = risk_context.get('risk_id', 'Unknown')
            asset_name = risk_context.get('asset_name', 'Unknown')
            threat_name = risk_context.get('threat_name', 'Unknown')
            treatment_decision = risk_context.get('treatment_decision', 'Unknown')
            created_at = risk_context.get('created_at', '')
            days_since_creation = risk_context.get('days_since_creation', 0)
            treatment_actions = risk_context.get('treatment_actions', [])
            num_actions = len(treatment_actions)
            reason_for_acceptance = risk_context.get('reason_for_acceptance', '')
            transfer_method = risk_context.get('transfer_method', '')
            third_party_name = risk_context.get('third_party_name', '')
            scope_of_transfer = risk_context.get('scope_of_transfer', '')
            termination_justification = risk_context.get('termination_justification', '')
            business_impact = risk_context.get('business_impact', '')
            termination_actions_text = risk_context.get('termination_actions_text', '')
            
            # Calculate target date based on decision type
            from datetime import datetime, timedelta
            target_date = 'N/A'
            days_until_target = 'N/A'
            
            # 🔧 FIX: For TRANSFER, get Transfer End Date from transfer_form
            if decision == 'TRANSFER' and risk_data:
                try:
                    transfer_form = risk_data.get('transfer_form')
                    if transfer_form:
                        if isinstance(transfer_form, str):
                            form_data = json.loads(transfer_form)
                        else:
                            form_data = transfer_form
                        sections = form_data.get('sections', [])
                        for section in sections:
                            fields = section.get('fields', [])
                            for field in fields:
                                if field.get('field_name') == 'Transfer End Date':
                                    target_date = field.get('value', 'N/A')
                                    if target_date != 'N/A':
                                        try:
                                            end_date = datetime.strptime(target_date, '%Y-%m-%d')
                                            days_until_target = (end_date - datetime.now()).days
                                        except:
                                            days_until_target = 'N/A'
                                    break
                            if target_date != 'N/A':
                                break
                except:
                    pass
            # 🔧 FIX: For TERMINATE, get Completion Date from terminate_form
            elif decision == 'TERMINATE' and risk_data:
                try:
                    terminate_form = risk_data.get('terminate_form')
                    if terminate_form:
                        if isinstance(terminate_form, str):
                            form_data = json.loads(terminate_form)
                        else:
                            form_data = terminate_form
                        sections = form_data.get('sections', [])
                        for section in sections:
                            fields = section.get('fields', [])
                            for field in fields:
                                if field.get('field_name') == 'Completion Date':
                                    target_date = field.get('value', 'N/A')
                                    if target_date != 'N/A':
                                        try:
                                            end_date = datetime.strptime(target_date, '%Y-%m-%d')
                                            days_until_target = (end_date - datetime.now()).days
                                        except:
                                            days_until_target = 'N/A'
                                    break
                            if target_date != 'N/A':
                                break
                except:
                    pass
            # For TREAT/ACCEPT: Calculate 90 days from creation
            else:
                try:
                    # Handle both date formats: 'YYYY-MM-DD' and 'YYYY-MM-DD HH:MM:SS'
                    if ' ' in created_at:
                        created_date = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                    else:
                        created_date = datetime.strptime(created_at, '%Y-%m-%d')
                    target_date = (created_date + timedelta(days=90)).strftime('%Y-%m-%d')
                    days_until_target = (created_date + timedelta(days=90) - datetime.now()).days
                except:
                    target_date = 'N/A'
                    days_until_target = 'N/A'
            
            task = Task(
                description=f"""
                Generate a follow-up questionnaire using the NEW enhanced Follow template from RAG.
                
                RISK CONTEXT:
                - Risk ID: {risk_id}
                - Asset: {asset_name}
                - Threat: {threat_name}
                - Treatment Decision: {treatment_decision}
                - Created: {created_at}
                - Days Since Creation: {days_since_creation}
                - Target Date: {target_date}
                - Days Until Target: {days_until_target}
                
                TREATMENT ACTIONS FROM DATABASE (Agent 4 Output):
                {json.dumps(treatment_actions, indent=2)}
                
                Number of Actions: {num_actions}
                {f'''\n                REASON FOR ACCEPTANCE (from original acceptance form):\n                {reason_for_acceptance}\n                ''' if decision == 'ACCEPT' and reason_for_acceptance else ''}
                {f'''\n                TRANSFER DETAILS (from original transfer form):\n                - Transfer Method: {transfer_method}\n                - Third Party Name: {third_party_name}\n                - Scope of Transfer: {scope_of_transfer}\n                ''' if decision == 'TRANSFER' and transfer_method else ''}
                {f'''\n                TERMINATION DETAILS (from original termination form):\n                - Termination Justification: {termination_justification}\n                - Business Impact: {business_impact}\n                - Termination Actions: {termination_actions_text}\n                ''' if decision == 'TERMINATE' and termination_justification else ''}
                
                STEP 1: DISCOVER TEMPLATE STRUCTURE
                Use Search Knowledge Base tool to query: "Show complete structure of Follow template_Use case v1.0.xlsx with all 7 sections"
                
                The template has:
                - Section 1: Risk Context (AI-filled from database)
                - Section 2: Original Risk Ratings (AI-filled from database)
                - Section 3: Treatment Actions Tracking (AI fills actions, User fills progress)
                - Section 4: Decision-Specific Questions (User-filled based on {treatment_decision})
                - Section 5: Progress (User-filled)
                - Section 6: Risk Re-assessment Results (AI-calculated after submission)
                - Section 7: Final Sign-off (User-filled)
                
                STEP 2: BUILD QUESTIONNAIRE
                
                For Section 1 & 2: Show as "display" fields (pre-filled, read-only)
                For Section 3: Generate questions for treatment actions from database
                  - CRITICAL: Section 3 title MUST be decision-specific:
                    * If ACCEPT: "Section 3: Compensating Controls Tracking"
                    * If TREAT: "Section 3: Treatment Actions Tracking"
                    * If TRANSFER: "Section 3: Transfer Actions Tracking"
                    * If TERMINATE: "Section 3: Termination Steps Tracking"
                For Section 4: Show ONLY {treatment_decision} questions (ignore other decisions)
                For Section 5: Ask about overall progress
                For Section 6: Skip (calculated after submission)
                For Section 7: Ask for comments and owner confirmation
                
                JSON STRUCTURE:
                {{
                    "questionnaire_title": "Risk Follow-up Questionnaire",
                    "questionnaire_metadata": {{
                        "questionnaire_type": "{treatment_decision} Follow-up",
                        "generation_date": "{datetime.now().strftime('%Y-%m-%d')}",
                        "days_since_identification": {days_since_creation},
                        "target_completion_date": "{target_date}",
                        "days_until_target": "{days_until_target}"
                    }},
                    "risk_context": {{
                        "risk_id": "{risk_id}",
                        "asset": "{asset_name}",
                        "threat": "{threat_name}",
                        "treatment_decision": "{treatment_decision}"
                    }},
                    "sections": [
                        {{
                            "title": "Section 1: Risk Context",
                            "description": "Pre-filled from database",
                            "fields": [
                                {{"id": "risk_id", "field_name": "Risk ID", "type": "display", "value": "{risk_id}"}},
                                {{"id": "asset_name", "field_name": "Asset Name", "type": "display", "value": "{asset_name}"}},
                                {{"id": "threat_name", "field_name": "Risk Description", "type": "display", "value": "{threat_name}"}},
                                {{"id": "treatment_decision", "field_name": "Management Decision", "type": "display", "value": "{treatment_decision}"}},{f'''\n                                {{"id": "reason_for_acceptance", "field_name": "Reason for Accepting Risk", "type": "display", "value": "{reason_for_acceptance}"}},''' if decision == 'ACCEPT' and reason_for_acceptance else ''}{f'''\n                                {{"id": "transfer_method", "field_name": "Transfer Method", "type": "display", "value": "{transfer_method}"}},\n                                {{"id": "third_party_name", "field_name": "Third Party Name", "type": "display", "value": "{third_party_name}"}},\n                                {{"id": "scope_of_transfer", "field_name": "Scope of Transfer", "type": "display", "value": "{scope_of_transfer}"}},''' if decision == 'TRANSFER' and transfer_method else ''}{f'''\n                                {{"id": "termination_justification", "field_name": "Termination Justification", "type": "display", "value": "{termination_justification}"}},\n                                {{"id": "business_impact", "field_name": "Business Impact", "type": "display", "value": "{business_impact}"}},\n                                {{"id": "termination_actions", "field_name": "Termination Actions", "type": "display", "value": "{termination_actions_text}"}},''' if decision == 'TERMINATE' and termination_justification else ''}
                                {{"id": "action_owner", "field_name": "Action Owner (Person responsible for implementation)", "type": "text", "placeholder": "Enter name of person responsible"}}
                            ]
                        }},
                        {{
                            "title": "Section 3: [USE DECISION-SPECIFIC TITLE: 'Compensating Controls Tracking' for ACCEPT, 'Treatment Actions Tracking' for TREAT, 'Transfer Actions Tracking' for TRANSFER, 'Termination Steps Tracking' for TERMINATE]",
                            "description": "Track implementation progress of each action",
                            "fields": [
                                // CRITICAL: Generate ONE question per action from treatment_actions
                                // For each action in treatment_actions list:
                                {{"id": "action_1_status", "field_name": "Status of [Action 1 Description]", "type": "select", "options": ["Not Started", "In Progress", "Completed", "Blocked"]}},
                                {{"id": "action_1_progress", "field_name": "Progress % of [Action 1 Description]", "type": "number", "placeholder": "0-100"}},
                                {{"id": "action_2_status", "field_name": "Status of [Action 2 Description]", "type": "select", "options": ["Not Started", "In Progress", "Completed", "Blocked"]}},
                                {{"id": "action_2_progress", "field_name": "Progress % of [Action 2 Description]", "type": "number", "placeholder": "0-100"}}
                                // Continue for all {num_actions} actions
                            ]
                        }},
                        {{
                            "title": "Section 4: {treatment_decision} Questionnaire",
                            "description": "Decision-specific follow-up questions",
                            "fields": [
                                // Discover from template based on {treatment_decision}
                            ]
                        }},
                        {{
                            "title": "Section 5: Progress",
                            "description": "Overall progress tracking",
                            "fields": [
                                {{"id": "overall_completion", "field_name": "Completion Percentage (if in progress)", "type": "number", "placeholder": "___ %"}},
                                {{"id": "expected_completion", "field_name": "Expected Completion Date", "type": "date"}},
                                {{"id": "delay_reason", "field_name": "Reason for Delay (if applicable)", "type": "textarea"}}
                            ]
                        }},
                        {{
                            "title": "Section 7: Final Sign-off",
                            "description": "Confirmation and approval",
                            "fields": [
                                {{"id": "comments", "field_name": "Comments / additional notes (If any)", "type": "textarea"}},
                                {{"id": "owner_confirmation", "field_name": "Asset / Product owner confirmation", "type": "text", "placeholder": "Name  Signature  Date"}}
                            ]
                        }}
                    ]
                }}
                
                CRITICAL RULES:
                - Use exact field names from template
                - For Section 4, show ONLY {treatment_decision} questions (TREAT/ACCEPT/TRANSFER/TERMINATE)
                - Match field types from template (text/select/number/date/textarea)
                - Return ONLY valid JSON, no markdown, no explanations
                
                {f'''SPECIAL RULES FOR ACCEPT DECISIONS:
                - In Section 1: Display "Reason for Accepting Risk" as read-only field with value: "{reason_for_acceptance}"
                - COMPLETELY REMOVE Section 3 (Compensating Controls Tracking) if no actions exist
                - COMPLETELY REMOVE Section 4 (ACCEPT Questions) - do not show this section at all, not even the heading
                - Renumber sections for ACCEPT: Section 1 (Risk Context), Section 2 (Compensating Controls Tracking - only if actions exist), Section 3 (Progress), Section 4 (Final Sign-off)
                - In Section 3 (Progress): Include these questions:
                  * "Completion Percentage (if in progress)"
                  * "Expected Completion Date"
                  * "Reason for Delay (if applicable)"
                  * "Management approval for acceptance valid till?"
                  * "Is the risk still within the organization's risk appetite?"
                  * "Evidence of acceptance"
                - Final section numbering: 1, 2, 3, 4 (or 1, 2, 3 if no actions)''' if decision == 'ACCEPT' else ''}
                
                {f'''SPECIAL RULES FOR TRANSFER DECISIONS:
                - In Section 1: Display these as read-only fields:
                  * "Transfer Method": "{transfer_method}"
                  * "Third Party Name": "{third_party_name}"
                  * "Scope of Transfer": "{scope_of_transfer}"
                - COMPLETELY REMOVE Section 3 (Transfer Actions Tracking) - do not show this section at all
                - In Section 4 (TRANSFER Questions): REMOVE these 2 questions:
                  * "Name of third party / insurer and reference number"
                  * "Scope of risk transferred"
                - Rename Section 4 to "Section 2: Transfer Questionnaire"
                - Rename Section 5 to "Section 3: Progress"
                - Rename Section 7 to "Section 4: Final Sign-off"
                - Final section numbering: 1, 2, 3, 4''' if decision == 'TRANSFER' else ''}
                
                {f'''SPECIAL RULES FOR TREAT DECISIONS:
                - DO NOT use RAG to discover questions - use this FIXED template:
                - Section 1: Risk Context (display fields)
                - Section 2: Treatment Actions Tracking (one status + progress question per action)
                - Section 3: TREAT Questionnaire with EXACTLY these 6 questions:
                  1. "Have the planned treatment actions been implemented as per the treatment plan?" (select: Yes/Partially or No)
                  2. "Are the implemented controls effective in reducing the risk?" (select: Yes/Partially or No)
                  3. "Has the residual risk been reduced to an acceptable level?" (select: Yes/Partially or No)
                  4. "Are there any additional controls required?" (select: Yes/Partially or No)
                  5. "Evidence of treatment implementation" (select: Yes/attach reference)
                  6. "Current residual risk level" (select: Very Low/Low/Medium/High/Extreme)
                - Section 4: Progress (overall_completion, expected_completion, delay_reason)
                - Section 5: Final Sign-off (comments, owner_confirmation)
                - Final section numbering MUST be: 1, 2, 3, 4, 5 (no gaps)
                - NEVER change these questions - they must be identical every time''' if decision == 'TREAT' else ''}
                
                {f'''SPECIAL RULES FOR TERMINATE DECISIONS:
                - In Section 1: Display these as read-only fields:
                  * "Termination Justification": "{termination_justification}"
                  * "Business Impact": "{business_impact}"
                  * "Termination Actions": "{termination_actions_text}"
                - If no termination steps exist (num_actions = 0):
                  * COMPLETELY REMOVE Section 3 (Termination Steps Tracking)
                  * Renumber: Section 1 (Risk Context), Section 2 (TERMINATE Questions), Section 3 (Progress), Section 4 (Final Sign-off)
                - If termination steps exist:
                  * Keep all sections with normal numbering: 1, 2, 3, 4, 5''' if decision == 'TERMINATE' else ''}
                """,
                expected_output="Follow-up questionnaire JSON with 100% RAG-discovered structure",
                agent=agent
            )
            
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=True,
                memory=False
            )
            
            result = crew.kickoff()
            
            # Parse JSON
            result_text = str(result)
            
            # Find JSON block in markdown
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                parts = result_text.split("```")
                for part in parts:
                    if part.strip().startswith('{'):
                        result_text = part.strip()
                        break
            
            # Extract JSON object
            start_idx = result_text.find('{')
            if start_idx == -1:
                return {
                    'error': 'No JSON found in response',
                    'raw_output': result_text[:1000]
                }
            
            # Find matching closing brace
            brace_count = 0
            end_idx = -1
            for i in range(start_idx, len(result_text)):
                if result_text[i] == '{':
                    brace_count += 1
                elif result_text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            
            if end_idx == -1:
                return {
                    'error': 'Incomplete JSON in response',
                    'raw_output': result_text[:1000]
                }
            
            json_text = result_text[start_idx:end_idx]
            
            # 🔧 FIX: Replace unquoted N/A with quoted "N/A" for valid JSON
            json_text = json_text.replace(': N/A', ': "N/A"')
            
            questionnaire = json.loads(json_text)
            
            # 🆕 NEW: Save to template cache for future use
            template_to_cache = questionnaire.copy()
            if 'risk_context' in template_to_cache:
                del template_to_cache['risk_context']  # Remove specific context before caching
            if 'questionnaire_metadata' in template_to_cache:
                del template_to_cache['questionnaire_metadata']  # Remove specific metadata before caching
            
            # Cache save disabled
            print(f"💾 {decision} followup template cached for future use!")
            
            return questionnaire
            
        except json.JSONDecodeError as e:
            return {
                'error': f'JSON parsing failed: {str(e)}',
                'raw_output': str(result)[:1000]
            }
        except Exception as e:
            error_msg = str(e)
            
            # Check if quota exceeded
            if '429' in error_msg or 'quota' in error_msg.lower() or 'RESOURCE_EXHAUSTED' in error_msg:
                retry_count += 1
                if retry_count < max_retries:
                    print(f"\n⚠️ API quota exceeded. Rotating to next API key... (Attempt {retry_count}/{max_retries})")
                    manager = get_api_key_manager()
                    new_key = manager.rotate_key(reason="quota_exceeded")
                    if new_key:
                        continue
                    else:
                        return {
                            'error': 'All API keys exhausted. Please try again later.',
                            'raw_output': error_msg[:1000]
                        }
                else:
                    return {
                        'error': 'All API keys exhausted. Please try again later.',
                        'raw_output': error_msg[:1000]
                    }
            else:
                return {
                    'error': f'Unexpected error: {str(e)}',
                    'raw_output': error_msg[:1000]
                }
    
    return {
        'error': 'Max retries exceeded',
        'raw_output': 'Failed after multiple API key rotations'
    }
