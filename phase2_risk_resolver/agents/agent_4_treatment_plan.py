"""
Agent 4 - Treatment Plan Generator (FULLY AGENTIC)
Discovers Treatment Plan structure from RAG and auto-generates complete treatment plan
"""

import os
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import json
from datetime import datetime, timedelta
from typing import Dict, Any

from ..tools.rag_tool import search_knowledge_base_function


@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base for treatment plan templates"""
    return search_knowledge_base_function(query)


def create_treatment_plan_agent(api_key: str) -> Agent:
    """
    Create Fully Agentic Treatment Plan Agent with RAG Discovery
    """
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_VERBOSE"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.0
    )
    
    agent = Agent(
        role="Intelligent Risk Treatment Plan Generator",
        goal="""Discover Treatment Plan template structure from RAG and use your expert 
        knowledge to auto-generate complete, actionable treatment plans for ALL control gaps.""",
        backstory="""You are an EXPERT risk treatment strategist with deep knowledge of:
        - Security control implementation (patch management, MFA, encryption, monitoring, etc.)
        - Resource estimation (people, tools, budgets)
        - Timeline planning (realistic implementation durations)
        - Success metrics (KPIs and evaluation methods)
        
        Your workflow:
        1. DISCOVER Treatment Plan Excel template structure from RAG
        2. GET control gaps from Agent 3 (weak/deficient controls)
        3. USE YOUR INTELLIGENCE to generate treatment details for EACH gap:
           - Implementation activities (step-by-step HOW to fix)
           - Resources needed (people, tools, budget)
           - Timeline (realistic duration)
           - Success metrics (how to measure completion)
        
        IMPORTANT:
        - RAG only has TEMPLATES (Excel structure), NOT implementation details
        - YOU must generate implementation details using YOUR expert knowledge
        - Generate realistic, actionable plans for EVERY control gap
        - Don't search RAG for "patch management implementation" - it's not there!
        - Use your LLM knowledge to create smart, practical treatment plans
        
        You are INTELLIGENT enough to know:
        - Patch Management: Setup automated patching, test patches, deploy schedules
        - MFA: Deploy MFA solution, configure policies, train users
        - Encryption: Implement encryption at rest/transit, key management
        - Monitoring: Deploy SIEM, configure alerts, establish SOC procedures
        - Access Control: Implement RBAC, review access, enforce least privilege
        
        You create plans that are:
        - Complete (ALL gaps addressed)
        - Realistic (achievable timelines and budgets)
        - Actionable (clear implementation steps)
        - Measurable (clear success criteria)
        """,
        tools=[search_knowledge_base],
        llm=llm,
        verbose=False,
        allow_delegation=False
    )
    
    return agent


def generate_treatment_plan(
    api_key: str,
    agent_3_results: Dict[str, Any],
    risk_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate FULLY AGENTIC treatment plan by discovering structure from RAG
    
    Args:
        api_key: Gemini API key
        agent_3_results: Results from Agent 3 (control gaps and recommendations)
        risk_data: Current risk assessment data (Agent 1-3 results)
    
    Returns:
        Dictionary with complete treatment plan
    """
    
    try:
        agent = create_treatment_plan_agent(api_key)
        
        # ✅ FIX: Check if we have selected_controls (new flow) or control_gaps (old flow)
        selected_controls = risk_data.get('selected_controls', [])
        control_gaps = risk_data.get('control_gaps', [])
        
        # If we have selected controls, use them to generate treatment actions
        if selected_controls:
            print(f"\n✅ Using {len(selected_controls)} SELECTED CONTROLS for treatment plan")
            for idx, control in enumerate(selected_controls, 1):
                control_name = control.get('control_name', control.get('control_id', f'Control {idx}'))
                print(f"   {idx}. {control_name}")
        elif control_gaps:
            print(f"\n✅ Using {len(control_gaps)} CONTROL GAPS for treatment plan (fallback)")
            for idx, gap in enumerate(control_gaps, 1):
                gap_desc = gap.get('gap_description', f'Gap {idx}')
                print(f"   {idx}. {gap_desc}")
        else:
            print("\n⚠️ WARNING: No selected controls or control gaps provided!")
            # Try to extract from Agent 3 results as last resort
            if 'threat_control_evaluation' in agent_3_results:
                for threat_eval in agent_3_results['threat_control_evaluation']:
                    threat_name = threat_eval.get('threat', 'Unknown')
                    gaps = threat_eval.get('control_gaps', [])
                    
                    for gap in gaps:
                        control_gaps.append({
                            'threat': threat_name,
                            'gap_description': gap.get('gap_description', ''),
                            'control_id': gap.get('control_id', ''),
                            'current_rating': gap.get('current_rating', 0),
                            'severity': gap.get('severity', 'MEDIUM'),
                            'evidence': gap.get('evidence', '')
                        })
                print(f"   ✅ Extracted {len(control_gaps)} gaps from Agent 3 results")
        
        # ✅ FIX: Extract asset info from MULTIPLE sources (priority order)
        # 1. Try from Agent 3 results first
        asset_name = agent_3_results.get('asset_name')
        asset_type = agent_3_results.get('asset_type')
        
        # 2. If not in Agent 3, try from risk_data (passed from main_app)
        if not asset_name or asset_name == 'Unknown Asset':
            asset_name = risk_data.get('asset_name', 'Unknown Asset')
        if not asset_type or asset_type == 'Unknown':
            asset_type = risk_data.get('asset_type', 'Unknown')
        
        # 3. Generate Risk ID from asset name (will be replaced by Risk Register query later)
        # Format: RISK-ASSETNAME-YYYY-NNN
        # Get current date and year for timeline calculations
        today = datetime.now().strftime('%Y-%m-%d')
        current_year = datetime.now().year
        
        if asset_name and asset_name != 'Unknown Asset':
            # Clean asset name for Risk ID
            clean_name = asset_name.replace(' ', '-').replace('/', '-')[:20]
            risk_id_base = f"RISK-{clean_name}-{current_year}"
        else:
            risk_id_base = f"RISK-UNKNOWN-{current_year}"
        
        # ✅ FIX: Build context based on whether we have controls or gaps
        if selected_controls:
            # NEW FLOW: Generate treatment plan for SELECTED CONTROLS
            controls_context = "\n".join([
                f"""
Control {idx}: {control.get('control_name', control.get('control_id', f'Control {idx}'))}
- Control ID: {control.get('control_id', 'N/A')}
- Category: {control.get('category', 'N/A')}
- Description: {control.get('description', 'N/A')}
- Target Rating: {control.get('target_rating', 'N/A')}
- Priority: {control.get('priority', 'MEDIUM')}
- Implementation Guidance: {control.get('implementation_guidance', 'Use your expert knowledge')}
- Addresses Gap: {control.get('addresses_gap', 'N/A')}
- Source: {control.get('source', 'N/A')}
"""
                for idx, control in enumerate(selected_controls, 1)
            ])
            
            items_to_treat = selected_controls
            items_type = "SELECTED CONTROLS"
            items_count = len(selected_controls)
        else:
            # OLD FLOW: Generate treatment plan for CONTROL GAPS
            controls_context = json.dumps(control_gaps, indent=2)
            items_to_treat = control_gaps
            items_type = "CONTROL GAPS"
            items_count = len(control_gaps)
        
        context = f"""
═══════════════════════════════════════════════════════════════════════════════
AGENT 4: INTELLIGENT TREATMENT PLAN GENERATOR
═══════════════════════════════════════════════════════════════════════════════

CURRENT DATE: {today}
CURRENT YEAR: {current_year}

You are generating a COMPLETE treatment plan for {items_type}.

═══════════════════════════════════════════════════════════════════════════════
STEP 1: DISCOVER TREATMENT PLAN TEMPLATE FROM RAG
═══════════════════════════════════════════════════════════════════════════════

Search knowledge base ONCE for:
- "Risk Treatment Plan template"
- "Risk Treatment Plan Excel"

Discover the Excel columns/fields required (e.g., Description of activities, 
Necessary resources, Proposed deadline, Method for evaluation, etc.)

IMPORTANT: RAG only has TEMPLATE STRUCTURE, not implementation details!

═══════════════════════════════════════════════════════════════════════════════
STEP 2: {items_type} TO ADDRESS
═══════════════════════════════════════════════════════════════════════════════

Asset: {asset_name} ({asset_type})
Risk Owner: {risk_data.get('risk_owner', 'IT Security Team')}

{items_type} (from Agent 3 / User Selection):
{controls_context}

Current Risk:
- Risk Rating: {risk_data.get('risk_rating', 'Unknown')}/5
- Risk Level: {risk_data.get('risk_level', 'Unknown')}
- Residual Risk: {risk_data.get('residual_risk', 'Unknown')}

═══════════════════════════════════════════════════════════════════════════════
STEP 3: USE YOUR INTELLIGENCE TO GENERATE TREATMENT FOR EACH ITEM
═══════════════════════════════════════════════════════════════════════════════

For EACH {items_type.lower()} item above, YOU must generate:

1. **Description of Activities** (HOW to implement):
   - Use YOUR expert knowledge of security controls
   - Provide step-by-step implementation activities
   - Be specific and actionable
   
   Examples:
   - Patch Management: "Establish automated patch management using WSUS/SCCM, 
     define patch testing procedures, create deployment schedule (critical: 7 days, 
     high: 30 days), implement rollback procedures"
   - MFA: "Deploy Azure AD MFA solution, configure conditional access policies, 
     enroll all users, provide training, establish helpdesk procedures"
   - Antivirus: "Update antivirus definitions to latest version, configure 
     automatic updates, implement centralized management console, schedule 
     regular scans"

2. **Necessary Resources** (What's needed):
   - People (roles, FTE)
   - Tools/Software (licenses, subscriptions)
   - Budget estimate
   
   Examples:
   - "1 System Administrator (0.5 FTE), WSUS/SCCM license ($5K), Test environment"
   - "2 Security Engineers (0.25 FTE each), Azure AD P1 licenses ($10K/year)"

3. **Implementation Priority**:
   - HIGH severity gap → CRITICAL priority
   - MEDIUM severity gap → HIGH priority
   - LOW severity gap → MEDIUM priority

4. **Proposed Timeline**:
   - IMPORTANT: Use CURRENT DATE {today} for calculations!
   - Calculate realistic start and completion dates
   - Consider complexity:
     * Simple (Antivirus update): 1-2 weeks
     * Medium (Patch Management): 4-6 weeks
     * Complex (MFA deployment): 6-8 weeks
   - Start date: {today} or within 1 week from today
   - Completion date: Start date + duration
   - ALL DATES MUST BE IN {current_year} OR LATER!

5. **Method for Evaluation** (Success metrics):
   - Define measurable KPIs
   
   Examples:
   - "95% of systems patched within SLA, Zero critical vulnerabilities >7 days old"
   - "100% user MFA enrollment, <5% helpdesk calls related to MFA"
   - "Antivirus definitions updated daily, 100% endpoint coverage"

═══════════════════════════════════════════════════════════════════════════════
STEP 4: OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Generate JSON matching the discovered template structure:

IMPORTANT: ALL treatment actions must share the SAME risk_id: "{risk_id_base}-001"
(All actions are treating the SAME risk for the SAME asset)

{{
  "asset_name": "{asset_name}",
  "asset_type": "{asset_type}",
  "treatment_option": "TREAT",
  "risk_owner": "{risk_data.get('risk_owner', 'IT Security Team')}",
  "risk_id": "{risk_id_base}-001",
  
  "treatment_actions": [
    {{
      "action_id": "ACTION-1",
      "risk_id": "{risk_id_base}-001",
      "threat": "Threat from control gap",
      "control_gap": "Gap description from Agent 3",
      "control_id": "Control ID from gap (if available), or generate format: CTRL-XXX-NNN",
      
      "description_of_activities": "YOUR GENERATED implementation steps",
      "necessary_resources": "YOUR GENERATED resources list",
      "implementation_priority": "CRITICAL/HIGH/MEDIUM based on severity",
      "implementation_responsibility": "{risk_data.get('risk_owner', 'IT Security Team')}",
      "proposed_start_date": "YYYY-MM-DD (calculate)",
      "proposed_completion_date": "YYYY-MM-DD (calculate)",
      "actual_start_date": null,
      "actual_completion_date": null,
      "risk_owner_comments": "",
      "method_for_evaluation": "YOUR GENERATED success metrics",
      "status": "Planned",
      
      "estimated_cost": "YOUR GENERATED cost estimate",
      "estimated_duration_days": "YOUR CALCULATED duration",
      "expected_risk_reduction": "Calculate improvement"
    }}
  ],
  
  "summary": {{
    "total_actions": "Count",
    "total_estimated_cost": "Sum of costs",
    "total_duration_days": "Longest timeline",
    "expected_risk_rating_after": "Calculate",
    "expected_residual_risk_after": "Calculate"
  }}
}}

═══════════════════════════════════════════════════════════════════════════════
CRITICAL REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

✅ DO:
1. Search RAG ONCE for template structure
2. Generate treatment for EVERY control gap
3. Use YOUR intelligence to create realistic implementation details
4. Fill ALL fields with meaningful content (no placeholders!)
5. Calculate actual dates (use today's date + duration)
6. Return ONLY valid JSON

❌ DON'T:
1. Search RAG for implementation details (they're not there!)
2. Leave fields empty or with placeholders
3. Skip any control gaps
4. Use generic text - be specific!
5. Return text outside JSON

═══════════════════════════════════════════════════════════════════════════════

Generate complete treatment plan for ALL {items_count} {items_type.lower()}!
Return ONLY the JSON object!
"""
        
        task = Task(
            description=context,
            agent=agent,
            expected_output="Complete treatment plan in JSON format with all fields auto-generated"
        )
        
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True
        )
        
        print("\n" + "="*80)
        print("🚀 GENERATING FULLY AGENTIC TREATMENT PLAN")
        print("   ✅ Discovering structure from RAG")
        print("   ✅ Auto-generating implementation details")
        print("   ✅ No user input required")
        print("="*80)
        
        result = crew.kickoff()
        
        print("\n" + "="*80)
        print("✅ TREATMENT PLAN GENERATION COMPLETE")
        print("="*80)
        
        # Parse JSON result
        result_text = str(result)
        
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            parts = result_text.split("```")
            if len(parts) >= 2:
                result_text = parts[1].strip()
        
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            result_text = result_text[start_idx:end_idx]
        
        result_json = json.loads(result_text)
        
        print(f"\n✅ Generated {len(result_json.get('treatment_actions', []))} treatment actions")
        print(f"✅ Total estimated cost: {result_json.get('summary', {}).get('total_estimated_cost', 'N/A')}")
        print(f"✅ Total duration: {result_json.get('summary', {}).get('total_duration_days', 'N/A')} days")
        
        return result_json
        
    except json.JSONDecodeError as e:
        print(f"\n⚠️ JSON parsing failed: {e}")
        return {
            "error": "JSON parsing failed",
            "raw_output": str(result)[:500] if 'result' in locals() else "No output"
        }
    except Exception as e:
        print(f"\n⚠️ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


if __name__ == "__main__":
    print("Agent 4 - Treatment Plan Generator (Fully Agentic)")
    print("Discovers structure from RAG and auto-generates complete treatment plans")
