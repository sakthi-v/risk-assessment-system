"""
Agent 4 - FULLY AGENTIC Risk Acceptance Form Generator
Uses RAG knowledge base to discover form structure (same as Agents 1, 2, 3)
"""

import os
import json
from typing import Dict, Any
from datetime import datetime
from crewai import Agent, Task, Crew, LLM
import re

from ..tools.rag_tool import search_knowledge_base_function


def generate_acceptance_form(risk_context: Dict[str, Any], questionnaire_answers: Dict[str, Any], questionnaire_structure: Dict[str, Any], api_key: str = None, agent_3_recommended_controls: list = None) -> Dict[str, Any]:
    """
    Generate risk acceptance form using questionnaire structure (no RAG lookup needed)
    (Fully agentic - uses questionnaire structure already discovered by questionnaire generator)
    
    Args:
        risk_context: Risk context data
        questionnaire_answers: User's questionnaire answers
        questionnaire_structure: Questionnaire structure
        api_key: Gemini API key
        agent_3_recommended_controls: Agent 3's recommended controls (to map gaps to controls)
    """
    
    try:
        # Validate API key
        if not api_key or api_key.strip() == '':
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                try:
                    from api_key_manager import get_active_api_key
                    api_key = get_active_api_key()
                    if not api_key:
                        raise ValueError("Gemini API key required - no valid API key available")
                except Exception as e:
                    raise ValueError(f"Gemini API key required - failed to get API key: {str(e)}")
        
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGCHAIN_VERBOSE"] = "false"
        
        llm = LLM(model="gemini/gemini-3-flash-preview", api_key=api_key, temperature=0.0)
        
        agent = Agent(
            role="Risk Acceptance Form Generator",
            goal="Generate filled form by mapping questionnaire answers to questionnaire structure",
            backstory="""You are an expert who generates filled forms from questionnaire answers.

**YOUR APPROACH:**
1. USE questionnaire structure (already discovered by questionnaire generator)
2. MAP questionnaire answers to questionnaire field IDs
3. GENERATE filled form with actual VALUES (not questions)

**CRITICAL:**
- DO NOT hardcode form structure
- USE the questionnaire structure provided
- Map answers to exact field IDs from questionnaire
- Generate FILLED form with VALUES

You are efficient and accurate.""",
            tools=[],
            llm=llm,
            verbose=True,
            allow_delegation=False
        )
        
        # Extract context
        asset_name = risk_context.get('asset_name', 'Unknown')
        threat_name = risk_context.get('threat_name', 'Unknown')
        risk_id = risk_context.get('risk_id', 'RSK-XXX')  # Use actual Risk ID from context
        risk_category = risk_context.get('risk_category', 'Security Risk')  # ✅ FIX: Get from context
        risk_rating = risk_context.get('inherent_risk_rating', 0)
        risk_level = risk_context.get('risk_level', 'Unknown')
        residual_risk = risk_context.get('residual_risk_rating', 0)
        control_gaps = risk_context.get('control_gaps', [])
        
        # ✅ NEW: Map selected gaps to Agent 3's recommended controls
        # User selected control gaps in questionnaire, but we need to show the CONTROL NAMES (not gaps)
        selected_controls_with_names = []
        if agent_3_recommended_controls:
            # Find the compensating controls answer
            for answer_key, answer_value in questionnaire_answers.items():
                if 'compensating' in answer_key.lower() or 'control' in answer_key.lower():
                    # answer_value is list of selected gaps
                    if isinstance(answer_value, list):
                        for selected_gap in answer_value:
                            gap_desc = selected_gap.get('gap_description', '') if isinstance(selected_gap, dict) else str(selected_gap)
                            # Find matching recommended control from Agent 3
                            for rec_ctrl in agent_3_recommended_controls:
                                if isinstance(rec_ctrl, dict):
                                    # Check if this control addresses this gap
                                    ctrl_name = rec_ctrl.get('control_name', rec_ctrl.get('label', ''))
                                    addresses_gap = rec_ctrl.get('addresses_gap', '')
                                    if gap_desc in addresses_gap or addresses_gap in gap_desc:
                                        # Found matching control!
                                        selected_controls_with_names.append({
                                            'gap_description': gap_desc,
                                            'compensating_control': ctrl_name,
                                            'control_type': rec_ctrl.get('control_type', 'N/A'),
                                            'priority': rec_ctrl.get('priority', 'N/A'),
                                            'severity': selected_gap.get('severity', 'N/A') if isinstance(selected_gap, dict) else 'N/A'
                                        })
                                        break
                            else:
                                # No matching control found, use gap only
                                selected_controls_with_names.append(selected_gap)
                    break
        
        # If no mapping done, use original answers
        if not selected_controls_with_names:
            selected_controls_with_names = None
        
        context = f"""
═══════════════════════════════════════════════════════════════════════════════
MISSION: Generate Risk Acceptance Form Using Questionnaire Structure
═══════════════════════════════════════════════════════════════════════════════

## PHASE 1: QUESTIONNAIRE STRUCTURE (Already Discovered!)

The questionnaire generator already discovered the Excel structure from RAG.
Here is the questionnaire structure with all field IDs:

{json.dumps(questionnaire_structure, indent=2)}

**Use these exact field IDs to map the answers - NO RAG search needed!**

═══════════════════════════════════════════════════════════════════════════════
## PHASE 2: AI PRE-FILLED DATA (from Agents 1-3)
═══════════════════════════════════════════════════════════════════════════════

Risk ID: {risk_id}
Risk Category: {risk_category}
Risk Description: {threat_name} affecting {asset_name}
Inherent Risk Rating: {risk_rating}/5
Residual Risk Rating: {residual_risk}
Risk Level: {risk_level}
Control Gaps: {len(control_gaps)} identified

Control Gaps Details:
{json.dumps(control_gaps, indent=2)}

**Agent 3 Recommended Controls (to address gaps):**
{json.dumps(agent_3_recommended_controls if agent_3_recommended_controls else [], indent=2)}

**Mapped Selected Controls (gaps + control names):**
{json.dumps(selected_controls_with_names if selected_controls_with_names else [], indent=2)}

**These fields are AI PRE-FILLED - include them in the form!**

═══════════════════════════════════════════════════════════════════════════════
## PHASE 3: USER QUESTIONNAIRE ANSWERS
═══════════════════════════════════════════════════════════════════════════════

{json.dumps(questionnaire_answers, indent=2)}

**Map these answers to the Excel fields you discovered in Phase 1!**

═══════════════════════════════════════════════════════════════════════════════
## PHASE 4: GENERATE FORM DYNAMICALLY
═══════════════════════════════════════════════════════════════════════════════

**INSTRUCTIONS:**

1. **Use questionnaire structure** from Phase 1 (already has all field IDs)
2. **For each field ID** in the questionnaire:
   - Is it AI pre-filled? (Risk ID, Risk Rating, etc.) → Use data from Phase 2
   - Is it user-filled? (from questionnaire) → Use data from Phase 3
3. **Generate FILLED FORM JSON** with VALUES (NOT questions!)
4. **Map questionnaire answers** to exact field IDs from questionnaire structure

**CRITICAL: Generate a FILLED FORM with VALUES, NOT a questionnaire with questions!**

**REQUIRED OUTPUT FORMAT - CLEAN FORM (NO QUESTIONS ARRAY!):**

```json
{{
  "metadata": {{
    "form_id": "RAF-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
    "form_name": "Risk Acceptance Form",
    "generated_date": "{datetime.now().strftime('%Y-%m-%d')}",
    "status": "Completed"
  }},
  
  "risk_context": {{
    "risk_id": "{risk_id}",
    "risk_category": "{risk_category}",
    "risk_description": "{threat_name} affecting {asset_name}",
    "current_risk_rating": {risk_rating},
    "calculated_residual_risk": {residual_risk}
  }},
  
  "engagement_project": {{
    "engagement_name": "<value from Q_ENGAGEMENT_NAME>",
    "project_name": "<value from Q_PROJECT_NAME>",
    "facility_location": "<value from Q_FACILITY_LOCATION>",
    "line_of_business": "<value from Q_LOB>",
    "bu_head": "<value from Q_BU_HEAD>",
    "l1_head": "<value from Q_L1_HEAD>"
  }},
  
  "compensating_controls": {{
    "selected_controls": {json.dumps(selected_controls_with_names if selected_controls_with_names else "<PRESERVE FULL CONTROL OBJECTS from Q_COMPENSATING_CONTROLS>")}
  }},
  
  "justification": {{
    "justification_text": "<value from Q_JUSTIFICATION>",
    "valid_until_date": "<value from Q_VALID_TILL>"
  }},
  
  "approvals": {{
    "risk_approved_by_role": "<value from Q_RISK_APPROVED_BY_ROLE>",
    "approver": {{
      "name": "<value from Q_APPROVER_NAME>",
      "designation": "<value from Q_APPROVER_DESIGNATION>",
      "employee_id": "<value from Q_APPROVER_EMPID>"
    }},
    "risk_owned_by_role": "<value from Q_RISK_OWNED_BY_ROLE>",
    "owner": {{
      "name": "<value from Q_OWNER_NAME>",
      "designation": "<value from Q_OWNER_DESIGNATION>",
      "employee_id": "<value from Q_OWNER_EMPID>"
    }},
    "client_ciso_name": "<value from Q_CLIENT_CISO_NAME or empty>",
    "client_approval_evidence": "<value from Q_CLIENT_APPROVAL_DATE_EVIDENCE or empty>"
  }},
  
  "signoff": {{
    "signoff_name": "<value from field with 'signoff' and 'name'>",
    "signoff_date": "<value from field with 'signoff' and 'date'>"
    // ONLY include signoff_signature if a 'signature' field exists in questionnaire!
  }}
}}
```

**CRITICAL MAPPING RULES - ONLY MAP FIELDS THAT EXIST IN QUESTIONNAIRE:**

For each field in questionnaire_answers, map to the form:
1. Fields with 'engagement' or 'name_of_engagement' → engagement_name
2. Fields with 'project' → project_name
3. Fields with 'facility' or 'location' → facility_location
4. Fields with 'lob' or 'line_of_business' → line_of_business
5. Fields with 'bu_head' or 'du_head' → bu_head
6. Fields with 'l1_head' → l1_head
7. Fields with 'compensating' or 'controls' → selected_controls (CRITICAL: preserve FULL control objects with ALL fields - control_name, gap_description, label, priority, cost, timeline, etc. DO NOT simplify to strings!)
8. Fields with 'justification' → justification_text
9. Fields with 'valid' and 'till' or 'until' → valid_until_date
10. Fields with 'approved_by' → risk_approved_by_role
11. Fields with 'approver' and 'name' → approver.name
12. Fields with 'approver' and 'designation' → approver.designation
13. Fields with 'approver' and ('empid' or 'employee') → approver.employee_id
14. Fields with 'owned_by' → risk_owned_by_role
15. Fields with 'owner' and 'name' → owner.name
16. Fields with 'owner' and 'designation' → owner.designation
17. Fields with 'owner' and ('empid' or 'employee') → owner.employee_id
18. Fields with 'client' and 'ciso' → client_ciso_name
19. Fields with 'client' and ('approval' or 'evidence') → client_approval_evidence
20. Fields with 'signoff' and 'name' → signoff_name
21. Fields with 'signoff' and 'date' → signoff_date
22. Fields with 'signature' (ONLY IF EXISTS) → signoff_signature

**CRITICAL: DO NOT include signoff_signature in output if no 'signature' field exists in questionnaire_answers!**
**CRITICAL: DO NOT hardcode any fields - only include what was asked in the questionnaire!**

═══════════════════════════════════════════════════════════════════════════════
## CRITICAL INSTRUCTIONS
═══════════════════════════════════════════════════════════════════════════════

✅ DO:
1. Use questionnaire structure to find field IDs
2. Map questionnaire answers to exact field IDs
3. Generate CLEAN FORM with FLAT SECTIONS (like the example above)
4. NO "questions" arrays - just clean key-value pairs
5. Output ONLY valid JSON

❌ DON'T:
1. Include "questions" arrays in output
2. Copy questionnaire structure into form
3. Add empty sections
4. Hardcode values
5. Search RAG (structure already provided)

**CRITICAL: Output a CLEAN FORM with FLAT SECTIONS, NOT a questionnaire with questions arrays!**

**CRITICAL FINAL CHECK:**
Before outputting, verify you ONLY included fields that exist in questionnaire_answers!
DO NOT add signoff_signature if no signature field was in the questionnaire!
DO NOT add any fields that weren't asked in the questionnaire!

**Output ONLY JSON, nothing else.**
"""
        
        task = Task(
            description=context,
            agent=agent,
            expected_output="FILLED Risk Acceptance Form in JSON format with actual VALUES from questionnaire answers (NOT questions, but filled values!)"
        )
        
        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        
        print("\n" + "="*80)
        print("🤖 AGENT 4: GENERATING ACCEPTANCE FORM (OPTIMIZED)")
        print("="*80)
        print("📋 Using questionnaire structure (no RAG lookup needed)...")
        print(f"   Found {len(questionnaire_structure.get('sections', []))} sections")
        print("="*80)
        
        result = crew.kickoff()
        result_text = str(result)
        
        # Extract JSON
        if '```json' in result_text:
            json_start = result_text.find('```json') + 7
            json_end = result_text.find('```', json_start)
            json_text = result_text[json_start:json_end].strip()
        elif '```' in result_text:
            json_start = result_text.find('```') + 3
            json_end = result_text.find('```', json_start)
            json_text = result_text[json_start:json_end].strip()
        else:
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = result_text.strip()
        
        try:
            acceptance_form = json.loads(json_text)
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parsing error: {e}")
            json_text = json_text.replace("'", '"')
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            acceptance_form = json.loads(json_text)
        
        print("\n✅ ACCEPTANCE FORM GENERATED FROM QUESTIONNAIRE STRUCTURE!")
        print(f"   Form ID: {acceptance_form.get('form_metadata', {}).get('form_id', 'N/A')}")
        print(f"   Mapped {len(questionnaire_answers)} answers to form fields")
        print("="*80 + "\n")
        
        return acceptance_form
    
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'error': str(e),
            'error_type': 'Agentic Form Generation Error',
            'traceback': traceback.format_exc(),
            'raw_output': result_text if 'result_text' in locals() else None
        }
