"""
Agent 4 - Risk Termination Form Generator
Generates final termination form from questionnaire responses
"""

import os
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import json
from datetime import datetime
from typing import Dict, Any

from ..tools.rag_tool import search_knowledge_base_function


@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base for risk termination form templates"""
    return search_knowledge_base_function(query)


def generate_terminate_form(api_key: str, risk_context: Dict[str, Any], questionnaire_responses: Dict[str, Any], questionnaire_structure: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Generate final risk termination form from questionnaire responses
    Uses questionnaire structure (already discovered by questionnaire generator)
    """
    
    try:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGCHAIN_VERBOSE"] = "false"
        
        llm = LLM(model="gemini/gemini-3-flash-preview", api_key=api_key, temperature=0.0)
        
        agent = Agent(
            role="Risk Termination Form Generator",
            goal="Generate filled termination form by mapping questionnaire answers to form structure",
            backstory="""You create filled forms by mapping questionnaire answers to the discovered template structure.

**YOUR JOB:**
1. Look at the questionnaire structure (sections and fields)
2. Map user answers to those fields
3. Create a filled form with sections matching the questionnaire
4. Use actual VALUES from answers (not field names)
5. CRITICAL: Use the actual Risk ID from AI data - DO NOT generate placeholder IDs

**CRITICAL RULES:**
- Output a form with 'risk_context' and 'sections' array
- Each section has 'title' and 'fields' array
- Each field has 'field_name' and 'value'
- Use questionnaire structure as the template
- Fill values from questionnaire_responses
- ALWAYS use the actual Risk ID provided in AI data
- DO NOT create placeholder Risk IDs like "RISK-1", "RISK-2", etc.

You are precise and follow structure exactly.""",
            tools=[],
            llm=llm,
            verbose=True,
            allow_delegation=False
        )
        
        # Extract context
        asset_name = risk_context.get('asset_name', 'Unknown')
        threat_name = risk_context.get('threat_name', 'Unknown')
        risk_id = risk_context.get('risk_id', 'RSK-XXX')  # Use actual Risk ID from context
        inherent_risk = risk_context.get('inherent_risk_rating', 0)
        residual_risk = risk_context.get('residual_risk_rating', 0)
        
        context = f"""
GENERATE RISK TERMINATION FORM

## QUESTIONNAIRE STRUCTURE
{json.dumps(questionnaire_structure, indent=2) if questionnaire_structure else 'No structure'}

## AI DATA
Risk ID: {risk_id}
Asset: {asset_name}
Threat: {threat_name}
Inherent Risk: {inherent_risk}
Residual Risk: {residual_risk}

## USER ANSWERS
{json.dumps(questionnaire_responses, indent=2)}

## YOUR TASK

1. Look at the questionnaire structure above
2. Create a filled form that mirrors the questionnaire structure
3. For each section in questionnaire, create a section in form
4. For each field in questionnaire, create a field in form with the user's answer
5. Add risk_context with AI data at the top

The form should have the SAME structure as the questionnaire, just with answers filled in.

Output valid JSON only.
"""
        
        task = Task(
            description=context,
            agent=agent,
            expected_output="Complete risk termination form in JSON format"
        )
        
        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        
        print("\n" + "="*80)
        print("🤖 AGENT 4: GENERATING TERMINATION FORM (SAME AS ACCEPTANCE)")
        print("="*80)
        print("📋 Using questionnaire structure (no RAG needed)...")
        if questionnaire_structure:
            print(f"   Found {len(questionnaire_structure.get('sections', questionnaire_structure.get('questionnaire', [])))} sections")
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
            import re
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = result_text.strip()
        
        try:
            form = json.loads(json_text)
        except json.JSONDecodeError as e:
            import re
            json_text = json_text.replace("'", '"')
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            try:
                form = json.loads(json_text)
            except:
                return {'error': f'JSON parsing failed: {str(e)}', 'raw_output': result_text[:2000]}
        
        form['generation_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print("\n✅ TERMINATION FORM GENERATED!")
        print("="*80 + "\n")
        
        return form
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'raw_output': result_text if 'result_text' in locals() else None}
