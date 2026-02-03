"""
Agent 4 - FULLY AGENTIC Risk Transfer Questionnaire Generator
Discovers requirements from RAG knowledge base
"""

import os
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import json
from datetime import datetime
from typing import Dict, Any


@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base for risk transfer requirements"""
    from phase2_risk_resolver.tools.rag_tool import search_knowledge_base_function
    return search_knowledge_base_function(query, use_cache=False)  # No cache for questionnaires


def generate_transfer_questionnaire(api_key: str, risk_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate risk transfer questionnaire using RAG (no memory cache)
    """
    
    print("\n" + "="*80)
    print("🤖 GENERATING TRANSFER QUESTIONNAIRE VIA RAG ONLY")
    print("="*80)
    
    try:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGCHAIN_VERBOSE"] = "false"
        
        llm = LLM(model="gemini/gemini-3-flash-preview", api_key=api_key, temperature=0.0)
        
        agent = Agent(
            role="Risk Transfer Questionnaire Designer with RAG Discovery",
            goal="Discover risk transfer requirements from organizational documents and generate questionnaire",
            backstory="""You are an expert who discovers organizational requirements from documents.

**YOUR APPROACH:**
1. SEARCH knowledge base: "What fields are in the Risk Transfer Form template?"
2. DISCOVER ALL fields dynamically from the template
3. IDENTIFY which fields AI already has vs what to ask user
4. GENERATE questionnaire for ONLY the discovered fields that need user input

**CRITICAL - ULTRA STRICT TEMPLATE MATCHING:**
- Query RAG to discover template structure
- Do NOT hardcode field names
- Generate questions for ONLY fields found in template
- ABSOLUTE RULE: If field NOT in RAG search results, do NOT include it
- Do NOT add Status, Comments, Documentation Link, or ANY other helpful fields
- Do NOT add fields that seem logical but are not in template
- TEMPLATE IS THE ONLY SOURCE OF TRUTH - nothing else matters

**AI ALREADY HAS (from risk_context):**
- Risk ID, Risk Description, Inherent Risk Rating, Residual Risk Rating
- Asset and Threat information

**ASK USER FOR:**
- ONLY fields from RAG results that AI doesn't already have
- Do NOT add ANY extra fields beyond RAG results

Output ONLY valid JSON, nothing else.""",
            tools=[search_knowledge_base],
            llm=llm,
            verbose=True,
            allow_delegation=False
        )
        
        asset_name = risk_context.get('asset_name', 'Unknown')
        threat_name = risk_context.get('threat_name', 'Unknown')
        risk_rating = risk_context.get('inherent_risk_rating', 0)
        residual_risk = risk_context.get('residual_risk_rating', 0)
        control_gaps = risk_context.get('control_gaps', [])
        risk_id = risk_context.get('risk_id', 'RSK-XXX')  # Get actual Risk ID from context
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Extract root cause from control gaps and threat
        root_cause_auto = f"Threat: {threat_name}. "
        if control_gaps:
            gap_descriptions = []
            for gap in control_gaps[:3]:  # Top 3 gaps
                if isinstance(gap, dict):
                    gap_descriptions.append(gap.get('gap_description', str(gap)))
                else:
                    gap_descriptions.append(str(gap))
            if gap_descriptions:
                root_cause_auto += f"Control Gaps: {', '.join(gap_descriptions)}"
        
        context = f"""
GENERATE RISK TRANSFER QUESTIONNAIRE

## PHASE 1: DISCOVER FROM RAG
Search for "Risk Transfer template" to discover required fields.

## PHASE 2: CURRENT RISK CONTEXT (AI ALREADY HAS THIS DATA!)
Risk ID: {risk_id}
Asset: {asset_name}
Threat: {threat_name}
Risk Rating: {risk_rating}/5
Residual Risk: {residual_risk}/5
Root Cause (AI-discovered): {root_cause_auto}

**CRITICAL: AI ALREADY HAS THIS DATA - DO NOT ASK USER FOR IT!**

**CRITICAL FORMAT RULE:**
- Risk ratings MUST be in format "X/5" (e.g., "4/5", "1/5")
- Do NOT use format "X/5/5" - this is WRONG

## PHASE 3: GENERATE QUESTIONNAIRE

**DISCOVER from RAG:** Query "What fields are in Risk Transfer Form template?"

**ULTRA STRICT RULES:**
1. Generate questions for ONLY fields discovered in RAG search results
2. Do NOT add Status field (not in template)
3. Do NOT add Comments field (not in template)
4. Do NOT add Documentation Link field (not in template)
5. Do NOT add ANY field that is not explicitly listed in RAG results
6. Template RAG results are the ONLY source of truth
7. If you think a field would be helpful but it's not in RAG results, DO NOT ADD IT

**FIELD NAME CLARIFICATIONS:**
- "Contract Reference" should be displayed as "Contract Reference ID" (more specific)

**FIELDS AI ALREADY HAS (do not ask user):**
- Risk ID: {risk_id}
- Risk Description, Inherent Risk Rating, Residual Risk Rating
- Root Cause (AI discovered from threat + control gaps)

**FOR ROOT CAUSE FIELD:**
- Set as "display" type with pre-filled value: "{root_cause_auto}"
- User can see it but doesn't need to type it

Structure questionnaire with sections matching the template structure.
For each field in RAG results:
- If AI already has it (Risk ID, Risk Description, Root Cause), set type="display" with value
- If user needs to provide it, create input question

Output ONLY valid JSON with risk_context and sections array.
"""
        
        task = Task(
            description=context,
            agent=agent,
            expected_output="""Valid JSON object with this EXACT structure:
{
  "risk_context": {"risk_id": "...", "asset_name": "..."},
  "sections": [{"title": "...", "fields": [{"id": "...", "field_name": "...", "type": "..."}]}]
}

Do NOT return tool calls. Return ONLY the JSON questionnaire."""
        )
        
        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        
        print("\n" + "="*80)
        print("🤖 AGENT 4: GENERATING TRANSFER QUESTIONNAIRE (100% DYNAMIC)")
        print("="*80)
        print("📚 Discovering ALL fields from template via RAG...")
        print("="*80)
        
        result = crew.kickoff()
        result_text = str(result)
        
        # ✅ FIX: If agent returned tool call instead of JSON, return error with helpful message
        if 'Search Knowledge Base' in result_text and '{' not in result_text:
            return {
                'error': 'Agent returned tool call instead of questionnaire. Retrying...',
                'retry': True,
                'raw_output': result_text[:500]
            }
        
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
        
        json_text = json_text.replace('""', '"').replace("''", "'")
        
        try:
            questionnaire = json.loads(json_text)
        except json.JSONDecodeError as e:
            import re
            json_text = json_text.replace("'", '"')
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            try:
                questionnaire = json.loads(json_text)
            except:
                return {'error': f'JSON parsing failed: {str(e)}', 'raw_output': result_text[:2000]}
        
        if 'risk_context' in questionnaire:
            questionnaire['risk_context']['generation_date'] = current_date
            questionnaire['risk_context']['risk_id'] = risk_id  # Ensure Risk ID is in output
        
        print("\n✅ TRANSFER QUESTIONNAIRE GENERATED FROM RAG!")
        print(f"   Sections: {len(questionnaire.get('sections', []))}")
        total_fields = sum(len(s.get('fields', s.get('questions', []))) for s in questionnaire.get('sections', []))
        print(f"   Total Fields: {total_fields}")
        print("="*80 + "\n")
        
        return questionnaire
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'raw_output': result_text if 'result_text' in locals() else None}
