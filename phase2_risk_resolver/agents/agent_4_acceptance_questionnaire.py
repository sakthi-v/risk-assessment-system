"""
Agent 4 - FULLY AGENTIC Risk Acceptance Questionnaire Generator
Discovers requirements from RAG knowledge base (same as Agents 1, 2, 3)
"""

import os
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import json
from datetime import datetime
from typing import Dict, Any


@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base for risk acceptance requirements"""
    from phase2_risk_resolver.tools.rag_tool import search_knowledge_base_function
    return search_knowledge_base_function(query, use_cache=False)  # No cache for questionnaires


def generate_acceptance_questionnaire(api_key: str, risk_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate risk acceptance questionnaire using RAG (no memory cache)
    """
    
    try:
        print("\n" + "="*80)
        print(f"🤖 AGENT 4: GENERATING ACCEPTANCE QUESTIONNAIRE (RAG ONLY) - {datetime.now().strftime('%H:%M:%S')}")
        print("="*80)
        print("🔍 Using RAG to discover template structure...")
        print("="*80)
        
        # Fallback to original RAG generation
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGCHAIN_VERBOSE"] = "false"
        
        llm = LLM(model="gemini/gemini-3-flash-preview", api_key=api_key, temperature=0.0)
        
        agent = Agent(
            role="Risk Acceptance Questionnaire Designer with RAG Discovery",
            goal="Discover risk acceptance requirements from organizational documents and generate questionnaire",
            backstory="""You are an expert who discovers organizational requirements from documents.

**YOUR APPROACH:**
1. SEARCH knowledge base: "What fields are in the Risk Acceptance Form template?"
2. DISCOVER ALL fields dynamically from the template
3. IDENTIFY which fields AI already has vs what to ask user
4. GENERATE questionnaire for ALL discovered fields that need user input

**CRITICAL - FULLY DYNAMIC:**
- Query RAG to discover template structure
- Do NOT hardcode field names or sections
- Generate questions for ALL fields found in template
- Adapt to organization's specific template structure

**AI ALREADY HAS (from risk_context) - DO NOT ASK FOR THESE:**
- Risk ID, Category, Description
- Risk Ratings (Inherent, Residual)
- Asset Name and Threat Name
- Control Gaps (from Agent 3)

**CRITICAL: Skip generating questions for fields AI already has!**
The UI already displays this information at the top.
Do NOT create display-only fields or questions for:
- Risk ID
- Risk Category  
- Risk Description
- Asset Name
- Threat Name
- Risk Rating
- Residual Risk

**SPECIAL HANDLING:**

1. **Compensating Controls Question:**
   - If control_gaps exist in risk_context, create a MULTISELECT question
   - Use control_gaps as options (each control becomes a checkbox)
   - Type: "multiselect"
   - Include all control details (description, priority, cost, timeline, etc.)

2. **Combined Fields (e.g., "Name, Designation, Employee ID"):**
   - Split into SEPARATE questions for better data entry
   - Example: "Risk Owner Name, Designation, Employee ID" → 3 separate text questions
   - This improves user experience and data quality

**ASK USER FOR:**
- Everything else discovered in the template

Output ONLY valid JSON, nothing else.""",
            tools=[search_knowledge_base],
            llm=llm,
            verbose=True,
            allow_delegation=False
        )
        
        # Extract context
        asset_name = risk_context.get('asset_name', 'Unknown')
        threat_name = risk_context.get('threat_name', 'Unknown')
        risk_rating = risk_context.get('inherent_risk_rating', 0)
        residual_risk = risk_context.get('residual_risk_rating', 0)
        control_gaps = risk_context.get('control_gaps', [])
        risk_id = risk_context.get('risk_id', 'RSK-XXX')  # Get actual Risk ID from context
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        context = f"""
GENERATE RISK ACCEPTANCE QUESTIONNAIRE

## PHASE 1: DISCOVER FROM RAG
Search for "Risk Acceptance Form template" to discover required fields.

## PHASE 2: CURRENT RISK CONTEXT (AI ALREADY HAS THIS DATA!)
Risk ID: {risk_id}
Asset: {asset_name}
Threat: {threat_name}
Risk Rating: {risk_rating}/5
Residual Risk: {residual_risk}/5
Control Gaps: {json.dumps(control_gaps, indent=2)}

**CRITICAL: AI ALREADY HAS THIS DATA - DO NOT GENERATE QUESTIONS FOR IT!**

**CRITICAL FORMAT RULE:**
- Risk ratings MUST be in format "X/5" (e.g., "4/5", "1/5")
- Do NOT use format "X/5/5" - this is WRONG

The UI already displays Risk ID, Category, Asset, Threat, Risk Rating, and Residual Risk at the top.
Do NOT create display-only fields or questions for these - they are already shown!

## PHASE 3: GENERATE QUESTIONNAIRE

**DISCOVER from RAG:** Query "What fields are in Risk Acceptance Form template?"

Generate questionnaire with questions ONLY for fields that need user input.
SKIP fields that AI already has (Risk ID, Category, Description, Asset, Threat, Ratings).

Structure questionnaire with sections matching the template structure.
For each field in template that AI doesn't already have, create a question.

**SPECIAL INSTRUCTIONS:**

1. **For Compensating Controls field:**
   - Create a MULTISELECT question (type: "multiselect")
   - Use the control_gaps data above as options
   - CRITICAL: Each option should include BOTH gap AND recommended control name:
     * gap_description (what's missing)
     * recommended_control_name (what to implement - from Agent 3)
     * evidence
     * impact
     * severity
   - Format each option label as: "[Gap] → [Recommended Control]"
   - Example: "Missing encryption → Implement AES-256 encryption"
   - Question: "Select compensating controls to implement (from identified control gaps):"
   - Options format: Pass each control object with both gap and control name
   - Example: {json.dumps(control_gaps, indent=2)}

2. **For combined fields like "Name, Designation, Employee ID":**
   - Split into 3 separate text questions:
     * "Please provide the Name of [Role]"
     * "Please provide the Designation of [Role]"
     * "Please provide the Employee ID of [Role]"
   - This applies to Risk Owner, Risk Approver, etc.

3. **For "Risk Approved by" and "Risk Owned By" fields:**
   - These should be DROPDOWN/SELECT questions (type: "select")
   - Provide options based on organizational roles
   - Options: ["Risk & Compliance Apex Committee", "CISO", "RISO", "Delivery Compliance Officer", "CIO", "Legal", "L1 Head", "BU Head"]
   - These are role selection fields, not display-only
"""
        
        task = Task(
            description=context,
            agent=agent,
            expected_output="""Risk acceptance questionnaire in JSON format with this EXACT structure:
{
  "title": "Risk Acceptance Form",
  "sections": [
    {
      "title": "Section Name",
      "questions": [
        {
          "id": "field_id",
          "question": "Question text here?",
          "type": "text|textarea|date|select|multiselect|display",
          "required": true,
          "options": [],
          "placeholder": "Hint text"
        }
      ]
    }
  ]
}

CRITICAL RULES:
1. ALWAYS use "question" for question text (NOT "label" or "text")
2. ALWAYS use "questions" array in sections (NOT "fields")
3. NEVER use markdown symbols like ** or __ in question text - use plain text only
4. For multiselect compensating controls, preserve FULL control objects in options
5. For display fields, use type: "display" with value field
6. Question text must be clean plain text without any formatting symbols"""
        )
        
        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        
        print("\n" + "="*80)
        print(f"🤖 AGENT 4: GENERATING ACCEPTANCE QUESTIONNAIRE (RAG ONLY) - {datetime.now().strftime('%H:%M:%S')}")
        print("="*80)
        print("🔍 Querying RAG for template structure...")
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
        
        # Clean up common JSON errors
        json_text = json_text.replace('""', '"')  # Fix double quotes
        json_text = json_text.replace("''", "'")   # Fix double single quotes
        
        try:
            questionnaire = json.loads(json_text)
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parsing error: {e}")
            print(f"⚠️ Attempting to fix JSON...")
            
            # Try to fix common issues
            import re
            json_text = json_text.replace("'", '"')  # Replace single quotes
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)  # Remove trailing commas
            
            try:
                questionnaire = json.loads(json_text)
            except:
                # Last resort: return error
                return {
                    'error': f'JSON parsing failed: {str(e)}',
                    'raw_output': result_text[:2000]
                }
        
        # POST-PROCESSING: Aggressively clean markdown symbols from ALL text fields
        def clean_markdown(text):
            """Remove all markdown formatting symbols"""
            if not isinstance(text, str):
                return text
            # Remove bold
            text = text.replace('**', '')
            # Remove italic
            text = text.replace('__', '')
            text = text.replace('_', '')
            # Remove extra spaces
            text = ' '.join(text.split())
            return text.strip()
        
        if 'sections' in questionnaire:
            for section in questionnaire['sections']:
                # Clean section title
                if 'title' in section:
                    section['title'] = clean_markdown(section['title'])
                if 'section_title' in section:
                    section['section_title'] = clean_markdown(section['section_title'])
                
                questions_key = 'questions' if 'questions' in section else 'fields'
                if questions_key in section:
                    for question in section[questions_key]:
                        # Clean ALL text fields in question
                        for key in ['question', 'label', 'text', 'question_text', 'placeholder', 'help_text']:
                            if key in question and isinstance(question[key], str):
                                question[key] = clean_markdown(question[key])
        
        if 'risk_context' in questionnaire:
            questionnaire['risk_context']['generation_date'] = current_date
            questionnaire['risk_context']['risk_id'] = risk_id  # Ensure Risk ID is in output
        
        print("\n✅ QUESTIONNAIRE GENERATED FROM RAG!")
        print(f"   Sections: {len(questionnaire.get('sections', []))}")
        
        # DEBUG: Check compensating controls question
        for section in questionnaire.get('sections', []):
            for q in section.get('questions', section.get('fields', [])):
                if 'compensating' in q.get('question', '').lower():
                    print(f"\n🔍 DEBUG - Compensating Controls Question:")
                    print(f"   Question text: '{q.get('question', 'N/A')}'")
                    print(f"   Has ** symbols: {'**' in q.get('question', '')}")
        
        print("="*80 + "\n")
        
        return questionnaire
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'raw_output': result_text if 'result_text' in locals() else None}
