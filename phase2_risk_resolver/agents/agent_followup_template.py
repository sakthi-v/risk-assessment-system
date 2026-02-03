"""
Agent Follow-up Template-Based (NEW)
Reads Excel template from RAG, fills AI fields from database, generates questions for User fields
"""
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import json
from datetime import datetime
from typing import Dict, Any
import os
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from phase2_risk_resolver.config.agent_definitions import AGENT_FOLLOWUP
from phase2_risk_resolver.database.risk_register_db import RiskRegisterDB
from phase2_risk_resolver.tools.rag_tool import search_knowledge_base_function

@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base for template structure"""
    return search_knowledge_base_function(query)

def create_template_followup_agent(api_key: str) -> Agent:
    """Create Agent that uses Excel template from RAG"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_VERBOSE"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.0
    )
    
    agent = Agent(
        role="Follow-up Questionnaire Generator (Template-Based)",
        goal="Read Excel template structure from RAG, fill AI fields from database, generate questions for User fields",
        backstory="Expert at reading templates and generating structured questionnaires that connect database outputs with user input requirements",
        tools=[search_knowledge_base],
        llm=llm,
        verbose=False,
        allow_delegation=False
    )
    
    return agent

def create_template_followup_task(agent: Agent, risk_data: Dict[str, Any]) -> Task:
    """Create task to generate template-based questionnaire"""
    
    risk_id = risk_data.get('risk_id', 'Unknown')
    
    # Extract treatment actions
    treatment_actions = risk_data.get('treatment_actions', [])
    if isinstance(treatment_actions, str):
        try:
            treatment_actions = json.loads(treatment_actions)
        except:
            treatment_actions = []
    
    task = Task(
        description=f"""
        ═══════════════════════════════════════════════════════════════════════════════
        GENERATE TEMPLATE-BASED FOLLOW-UP QUESTIONNAIRE
        ═══════════════════════════════════════════════════════════════════════════════
        
        STEP 1: READ TEMPLATE STRUCTURE FROM RAG
        ═══════════════════════════════════════════════════════════════════════════════
        
        Use the Search Knowledge Base tool to query:
        "Show me the complete structure of Follow template_Use case v1.0.xlsx with all sections and fields"
        
        The template has 7 sections:
        - Section 1: Risk Context (AI-filled)
        - Section 2: Original Risk Ratings (AI-filled)
        - Section 3: Treatment Actions Tracking (AI fills actions, User fills progress)
        - Section 4: Decision-Specific Questions (User-filled)
        - Section 5: Progress (User-filled)
        - Section 6: Risk Re-assessment Results (AI-calculated)
        - Section 7: Final Sign-off (User-filled)
        
        STEP 2: FILL AI FIELDS FROM DATABASE
        ═══════════════════════════════════════════════════════════════════════════════
        
        Risk Data from Database:
        {json.dumps(risk_data, indent=2, default=str)}
        
        Treatment Actions to populate in Section 3:
        {json.dumps(treatment_actions, indent=2)}
        
        Fill these AI fields:
        - Risk ID: {risk_data.get('risk_id')}
        - Risk Description: {risk_data.get('risk_description')}
        - Asset Name: {risk_data.get('asset_name')}
        - Asset Type: {risk_data.get('asset_type')}
        - Asset Owner: {risk_data.get('asset_owner')}
        - Action Owner: {risk_data.get('risk_owner')}
        - Management Decision: {risk_data.get('management_decision')}
        - Original Assessment Date: {risk_data.get('created_at')}
        - Follow-up Count: {risk_data.get('followup_count', 0)}
        - Inherent Risk Rating: {risk_data.get('inherent_risk_rating')}
        - Original Control Rating: {risk_data.get('control_rating')}
        - Original Residual Risk: {risk_data.get('residual_risk_rating')}
        
        STEP 3: GENERATE QUESTIONS FOR USER FIELDS
        ═══════════════════════════════════════════════════════════════════════════════
        
        For Section 3 (Treatment Actions), generate questions for EACH action:
        - Status: "What is the current status of [action_description]?"
        - Progress %: "What is the completion percentage of [action_description]?"
        
        For Section 4 (Decision-Specific), generate questions based on decision type:
        - If TREAT: Ask about mitigation implementation, control effectiveness, evidence
        - If ACCEPT: Ask about acceptance reason, management approval, compensating controls
        - If TRANSFER: Ask about third party, transfer scope, review frequency
        - If TERMINATE: Ask about termination approach, date, dependencies
        
        For Section 5 (Progress): Ask about overall completion %, expected date, delays
        
        For Section 7 (Sign-off): Ask for comments and owner confirmation
        
        OUTPUT FORMAT: STRICT JSON
        ═══════════════════════════════════════════════════════════════════════════════
        
        {{
            "template_metadata": {{
                "template_name": "Follow template_Use case v1.0.xlsx",
                "risk_id": "{risk_id}",
                "generation_date": "{datetime.now().strftime('%Y-%m-%d')}",
                "followup_count": {risk_data.get('followup_count', 0)}
            }},
            "ai_filled_data": {{
                "section_1_risk_context": {{
                    "risk_id": "{risk_data.get('risk_id')}",
                    "risk_description": "{risk_data.get('risk_description')}",
                    "asset_name": "{risk_data.get('asset_name')}",
                    "asset_type": "{risk_data.get('asset_type')}",
                    "asset_owner": "{risk_data.get('asset_owner')}",
                    "action_owner": "{risk_data.get('risk_owner')}",
                    "management_decision": "{risk_data.get('management_decision')}",
                    "original_assessment_date": "{risk_data.get('created_at')}",
                    "followup_count": {risk_data.get('followup_count', 0)}
                }},
                "section_2_original_ratings": {{
                    "inherent_risk_rating": "{risk_data.get('inherent_risk_rating')}",
                    "control_rating": "{risk_data.get('control_rating')}",
                    "residual_risk_rating": "{risk_data.get('residual_risk_rating')}"
                }},
                "section_3_treatment_actions": {json.dumps(treatment_actions)}
            }},
            "user_questions": [
                {{
                    "section": "Section 3: Treatment Actions Tracking",
                    "questions": [
                        {{
                            "question_id": "action_1_status",
                            "question_text": "What is the current status of: [action_1_description]?",
                            "question_type": "radio",
                            "options": ["Not Started", "In Progress", "Completed", "Blocked"],
                            "required": true
                        }},
                        {{
                            "question_id": "action_1_progress",
                            "question_text": "What is the completion percentage of: [action_1_description]?",
                            "question_type": "number",
                            "min": 0,
                            "max": 100,
                            "required": true
                        }}
                    ]
                }},
                {{
                    "section": "Section 4: Decision-Specific Questions",
                    "questions": [
                        {{
                            "question_id": "mitigation_implemented",
                            "question_text": "Have the planned mitigation actions been implemented?",
                            "question_type": "radio",
                            "options": ["Yes", "Partially", "No"],
                            "required": true
                        }}
                    ]
                }},
                {{
                    "section": "Section 5: Progress",
                    "questions": [
                        {{
                            "question_id": "overall_completion",
                            "question_text": "What is the overall completion percentage?",
                            "question_type": "number",
                            "min": 0,
                            "max": 100,
                            "required": true
                        }}
                    ]
                }},
                {{
                    "section": "Section 7: Final Sign-off",
                    "questions": [
                        {{
                            "question_id": "owner_confirmation",
                            "question_text": "Asset/Product owner confirmation (Name, Signature, Date)",
                            "question_type": "text",
                            "required": true
                        }}
                    ]
                }}
            ]
        }}
        
        CRITICAL: Return ONLY valid JSON, no markdown, no explanations!
        """,
        expected_output="Template-based questionnaire JSON with AI-filled data and user questions",
        agent=agent
    )
    
    return task

def generate_template_based_questionnaire(api_key: str, risk_id: str) -> Dict[str, Any]:
    """Generate template-based follow-up questionnaire"""
    
    print(f"\n{'='*80}")
    print(f"GENERATING TEMPLATE-BASED FOLLOW-UP FOR {risk_id}")
    print('='*80)
    
    # Load risk data
    db = RiskRegisterDB()
    risk_data = db.get_risk(risk_id)
    
    if not risk_data:
        return {'error': f'Risk {risk_id} not found', 'status': 'error'}
    
    print(f"\nLoaded risk: {risk_data.get('risk_title', 'Unknown')}")
    print(f"Decision: {risk_data.get('management_decision', 'Unknown')}")
    
    # Create agent and task
    agent = create_template_followup_agent(api_key)
    task = create_template_followup_task(agent, risk_data)
    
    # Run crew
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=False,
        memory=False
    )
    
    result = crew.kickoff()
    
    # Parse result
    try:
        result_text = str(result)
        
        # Clean markdown
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            parts = result_text.split("```")
            if len(parts) >= 2:
                result_text = parts[1].strip()
        
        # Extract JSON
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            result_text = result_text[start_idx:end_idx]
        
        questionnaire = json.loads(result_text)
        
        print(f"\n{'='*80}")
        print("TEMPLATE-BASED QUESTIONNAIRE GENERATED")
        print('='*80)
        
        return questionnaire
        
    except json.JSONDecodeError as e:
        print(f"\nJSON parsing failed: {e}")
        return {
            'error': 'JSON parsing failed',
            'raw_output': str(result)[:1000],
            'status': 'error'
        }

if __name__ == "__main__":
    print("Template-Based Follow-up Agent - Ready!")
