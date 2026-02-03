"""
Agent Follow-up - Hybrid Approach
Generates intelligent follow-up questionnaires by analyzing treatment plans
Uses AI intelligence (no RAG needed for follow-up questions)
"""

from crewai import Agent, Task, Crew, LLM
import json
from datetime import datetime
from typing import Dict, Any, List
import os
from pathlib import Path
import sys

from phase2_risk_resolver.config.agent_definitions import AGENT_FOLLOWUP

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from phase2_risk_resolver.database.risk_register_db import RiskRegisterDB


def create_followup_agent(api_key: str) -> Agent:
    """Create Agent for Follow-up Questionnaire Generation"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_VERBOSE"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.0
    )
    
    agent = Agent(
        role=AGENT_FOLLOWUP["role"],
        goal=AGENT_FOLLOWUP["goal"],
        backstory=AGENT_FOLLOWUP["backstory"],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return agent


def create_followup_task(agent: Agent, risk_data: Dict[str, Any]) -> Task:
    """Create task for Agent to generate follow-up questionnaire"""
    
    risk_id = risk_data.get('risk_id', 'Unknown')
    risk_title = risk_data.get('risk_title', 'Unknown Risk')
    
    # Extract treatment plan details
    treatment_actions = risk_data.get('treatment_actions', [])
    if isinstance(treatment_actions, str):
        try:
            treatment_actions = json.loads(treatment_actions)
        except:
            treatment_actions = []
    
    recommended_controls = risk_data.get('recommended_controls', [])
    if isinstance(recommended_controls, str):
        try:
            recommended_controls = json.loads(recommended_controls)
        except:
            recommended_controls = []
    
    management_decision = risk_data.get('management_decision', 'Unknown')
    date_identified = risk_data.get('date_identified', 'Unknown')
    target_date = risk_data.get('target_closure_date', 'Not set')
    risk_owner = risk_data.get('risk_owner', 'Unassigned')
    
    # 🆕 NEW: Extract acceptance-specific data from database
    acceptance_form = risk_data.get('acceptance_form', {})
    if isinstance(acceptance_form, str):
        try:
            acceptance_form = json.loads(acceptance_form)
        except:
            acceptance_form = {}
    
    # Extract reason for accepting risk from acceptance form
    reason_for_acceptance = ""
    if acceptance_form:
        # Try multiple possible field names
        reason_for_acceptance = (
            acceptance_form.get('reason_for_acceptance') or 
            acceptance_form.get('justification', {}).get('reason_for_acceptance') or
            acceptance_form.get('justification', {}).get('justification_for_acceptance') or
            "Not specified in acceptance form"
        )
    
    task = Task(
        description=f"""
        ═══════════════════════════════════════════════════════════════════════════════
        GENERATE FOLLOW-UP QUESTIONNAIRE FOR RISK TREATMENT TRACKING
        ═══════════════════════════════════════════════════════════════════════════════
        
        You are generating a follow-up questionnaire to track the implementation progress
        of a risk treatment plan. Use your expertise in project management and risk 
        tracking to create relevant, specific questions.
        
        ═══════════════════════════════════════════════════════════════════════════════
        RISK INFORMATION
        ═══════════════════════════════════════════════════════════════════════════════
        
        Risk ID: {risk_id}
        Risk Title: {risk_title}
        Risk Owner: {risk_owner}
        Management Decision: {management_decision}
        Date Identified: {date_identified}
        Target Completion: {target_date}
        
        **FOR ACCEPT DECISIONS:**
        Reason for Accepting Risk: {reason_for_acceptance if management_decision == 'ACCEPT' else 'N/A'}
        
        ═══════════════════════════════════════════════════════════════════════════════
        TREATMENT PLAN TO TRACK
        ═══════════════════════════════════════════════════════════════════════════════
        
        Treatment Actions Planned:
        {json.dumps(treatment_actions, indent=2) if treatment_actions else "No specific actions documented"}
        
        Controls to Implement:
        {json.dumps(recommended_controls, indent=2) if recommended_controls else "No specific controls documented"}
        
        ═══════════════════════════════════════════════════════════════════════════════
        YOUR TASK
        ═══════════════════════════════════════════════════════════════════════════════
        
        Generate a comprehensive follow-up questionnaire with these sections:
        
        **SECTION 1: IMPLEMENTATION STATUS**
        For EACH action in the treatment plan:
        - Ask about current status (Not Started / In Progress / Completed / Blocked)
        - Ask about completion percentage (0-100%)
        - Ask about any blockers or challenges
        - Ask about actual vs planned timeline
        
        **SECTION 2: CONTROL EFFECTIVENESS**
        For EACH control to implement:
        - Ask if control has been implemented
        - Ask about implementation quality
        - Ask about effectiveness after implementation (1-5 rating)
        - Ask about any issues or weaknesses found
        
        **SECTION 3: RISK REASSESSMENT**
        - Ask if risk level has changed since treatment started
        - Ask about any security incidents related to this risk
        - Ask about residual risk perception
        - Ask if additional threats have been identified
        
        **SECTION 4: RESOURCE & TIMELINE**
        - Ask about actual budget spent vs estimated
        - Ask about actual time taken vs estimated
        - Ask about resource adequacy
        - Ask about revised completion date if needed
        
        **SECTION 5: LESSONS LEARNED**
        - Ask what worked well
        - Ask what challenges were faced
        - Ask what would be done differently
        - Ask for recommendations for similar risks
        
        **SECTION 6: NEXT STEPS**
        - Ask about remaining actions
        - Ask about priority for next steps
        - Ask about support needed
        - Ask about expected completion date
        
        ═══════════════════════════════════════════════════════════════════════════════
        IMPORTANT GUIDELINES
        ═══════════════════════════════════════════════════════════════════════════════
        
        1. **BE SPECIFIC**: Reference the actual action names and control names from the plan
        
        2. **BE ADAPTIVE**: If there are 3 actions, ask 3 status questions. If 5, ask 5.
        
        3. **BE INTELLIGENT**: Use dropdown/radio for status, number input for percentages,
           textarea for open-ended questions
        
        4. **BE PRACTICAL**: Ask questions that help track progress and identify issues
        
        5. **CALCULATE DAYS**: Calculate how many days have passed since date_identified
           to help assess if on track
        
        6. **FOR ACCEPT DECISIONS - SPECIAL RULES:**
           - In Section 1 (Risk Context), ADD a display-only field showing "Reason for Accepting Risk: {reason_for_acceptance}"
           - DO NOT ask "Has the potential impact increased since acceptance?" - EXCLUDE THIS
           - DO NOT ask "Are compensating controls in place" - EXCLUDE THIS
           - Move these 3 questions to Progress section:
             * Management approval for acceptance valid till?
             * Is the risk still within the organization's risk appetite?
             * Evidence of acceptance
        
        ═══════════════════════════════════════════════════════════════════════════════
        OUTPUT FORMAT: JSON
        ═══════════════════════════════════════════════════════════════════════════════
        
        Return ONLY valid JSON in this exact structure:
        
        {{
            "questionnaire_metadata": {{
                "questionnaire_type": "FOLLOW_UP",
                "risk_id": "{risk_id}",
                "risk_title": "{risk_title}",
                "generation_date": "{datetime.now().strftime('%Y-%m-%d')}",
                "days_since_identification": <calculate days>,
                "target_completion_date": "{target_date}",
                "days_until_target": <calculate days>
            }},
            "sections": [
                {{
                    "section_id": "SECTION_1",
                    "section_name": "Implementation Status",
                    "section_description": "Track the status of each planned action",
                    "questions": [
                        {{
                            "question_id": "Q1.1",
                            "question_text": "What is the current status of: [ACTION_NAME]?",
                            "question_type": "radio",
                            "required": true,
                            "options": [
                                {{"value": "NOT_STARTED", "label": "Not Started"}},
                                {{"value": "IN_PROGRESS", "label": "In Progress"}},
                                {{"value": "COMPLETED", "label": "Completed"}},
                                {{"value": "BLOCKED", "label": "Blocked"}}
                            ],
                            "context": "Action from treatment plan",
                            "help_text": "Select the current implementation status"
                        }},
                        {{
                            "question_id": "Q1.2",
                            "question_text": "What percentage complete is: [ACTION_NAME]?",
                            "question_type": "number",
                            "required": false,
                            "min_value": 0,
                            "max_value": 100,
                            "help_text": "Enter completion percentage (0-100)"
                        }},
                        {{
                            "question_id": "Q1.3",
                            "question_text": "Are there any blockers preventing: [ACTION_NAME]?",
                            "question_type": "textarea",
                            "required": false,
                            "placeholder": "Describe any blockers or challenges...",
                            "help_text": "Identify obstacles that need to be addressed"
                        }}
                    ]
                }},
                {{
                    "section_id": "SECTION_2",
                    "section_name": "Control Effectiveness",
                    "section_description": "Assess the effectiveness of implemented controls",
                    "questions": [
                        {{
                            "question_id": "Q2.1",
                            "question_text": "Has [CONTROL_NAME] been implemented?",
                            "question_type": "radio",
                            "required": true,
                            "options": [
                                {{"value": "YES", "label": "Yes, fully implemented"}},
                                {{"value": "PARTIAL", "label": "Partially implemented"}},
                                {{"value": "NO", "label": "Not yet implemented"}}
                            ]
                        }},
                        {{
                            "question_id": "Q2.2",
                            "question_text": "How effective is [CONTROL_NAME] at reducing the risk?",
                            "question_type": "rating_scale",
                            "required": false,
                            "scale": "1-5",
                            "labels": {{
                                "1": "Not Effective",
                                "3": "Moderately Effective",
                                "5": "Very Effective"
                            }},
                            "help_text": "Rate based on observed effectiveness"
                        }}
                    ]
                }},
                {{
                    "section_id": "SECTION_3",
                    "section_name": "Risk Reassessment",
                    "section_description": "Evaluate if the risk level has changed",
                    "questions": [
                        {{
                            "question_id": "Q3.1",
                            "question_text": "Has the risk level decreased since starting treatment?",
                            "question_type": "radio",
                            "required": true,
                            "options": [
                                {{"value": "DECREASED", "label": "Yes, risk has decreased"}},
                                {{"value": "SAME", "label": "Risk level is the same"}},
                                {{"value": "INCREASED", "label": "Risk has increased"}},
                                {{"value": "TOO_EARLY", "label": "Too early to tell"}}
                            ]
                        }},
                        {{
                            "question_id": "Q3.2",
                            "question_text": "Have there been any security incidents related to this risk?",
                            "question_type": "radio",
                            "required": true,
                            "options": [
                                {{"value": "YES", "label": "Yes"}},
                                {{"value": "NO", "label": "No"}}
                            ]
                        }},
                        {{
                            "question_id": "Q3.3",
                            "question_text": "If yes, describe the incident(s):",
                            "question_type": "textarea",
                            "required": false,
                            "conditional": "Q3.2 == 'YES'",
                            "placeholder": "Describe what happened..."
                        }}
                    ]
                }},
                {{
                    "section_id": "SECTION_4",
                    "section_name": "Resources & Timeline",
                    "section_description": "Track resource usage and timeline adherence",
                    "questions": [
                        {{
                            "question_id": "Q4.1",
                            "question_text": "Is the treatment on track to meet the target date of {target_date}?",
                            "question_type": "radio",
                            "required": true,
                            "options": [
                                {{"value": "ON_TRACK", "label": "Yes, on track"}},
                                {{"value": "DELAYED", "label": "Delayed"}},
                                {{"value": "AHEAD", "label": "Ahead of schedule"}}
                            ]
                        }},
                        {{
                            "question_id": "Q4.2",
                            "question_text": "If delayed, what is the revised completion date?",
                            "question_type": "date",
                            "required": false,
                            "conditional": "Q4.1 == 'DELAYED'"
                        }},
                        {{
                            "question_id": "Q4.3",
                            "question_text": "Are resources (budget, people, tools) adequate?",
                            "question_type": "radio",
                            "required": true,
                            "options": [
                                {{"value": "ADEQUATE", "label": "Yes, adequate"}},
                                {{"value": "INSUFFICIENT", "label": "Insufficient"}},
                                {{"value": "EXCESSIVE", "label": "More than needed"}}
                            ]
                        }}
                    ]
                }},
                {{
                    "section_id": "SECTION_5",
                    "section_name": "Lessons Learned",
                    "section_description": "Capture insights for future improvements",
                    "questions": [
                        {{
                            "question_id": "Q5.1",
                            "question_text": "What has worked well in this treatment implementation?",
                            "question_type": "textarea",
                            "required": false,
                            "placeholder": "Share successes and best practices...",
                            "help_text": "Help others learn from your experience"
                        }},
                        {{
                            "question_id": "Q5.2",
                            "question_text": "What challenges did you face?",
                            "question_type": "textarea",
                            "required": false,
                            "placeholder": "Describe challenges encountered...",
                            "help_text": "Identify obstacles for future planning"
                        }},
                        {{
                            "question_id": "Q5.3",
                            "question_text": "What would you do differently?",
                            "question_type": "textarea",
                            "required": false,
                            "placeholder": "Recommendations for improvement...",
                            "help_text": "Suggestions for similar future treatments"
                        }}
                    ]
                }},
                {{
                    "section_id": "SECTION_6",
                    "section_name": "Next Steps",
                    "section_description": "Plan remaining actions and priorities",
                    "questions": [
                        {{
                            "question_id": "Q6.1",
                            "question_text": "What are the immediate next steps?",
                            "question_type": "textarea",
                            "required": true,
                            "placeholder": "List priority actions...",
                            "help_text": "What needs to happen next?"
                        }},
                        {{
                            "question_id": "Q6.2",
                            "question_text": "What support or resources are needed?",
                            "question_type": "textarea",
                            "required": false,
                            "placeholder": "Identify needed support...",
                            "help_text": "Budget, people, approvals, tools, etc."
                        }},
                        {{
                            "question_id": "Q6.3",
                            "question_text": "When should the next follow-up be scheduled?",
                            "question_type": "date",
                            "required": false,
                            "help_text": "Recommended based on implementation progress"
                        }}
                    ]
                }}
            ]
        }}
        
        ═══════════════════════════════════════════════════════════════════════════════
        CRITICAL REQUIREMENTS
        ═══════════════════════════════════════════════════════════════════════════════
        
        1. ✅ Use actual action names and control names from the treatment plan
        2. ✅ Calculate days_since_identification and days_until_target
        3. ✅ Adapt number of questions to number of actions/controls
        4. ✅ Use appropriate question types (radio, number, textarea, date, rating_scale)
        5. ✅ Return ONLY valid JSON (no markdown, no explanations)
        
        Generate the questionnaire now!
        """,
        expected_output="Follow-up questionnaire JSON with questions adapted to treatment plan",
        agent=agent
    )
    
    return task


def generate_followup_questionnaire(api_key: str, risk_id: str) -> Dict[str, Any]:
    """
    Generate follow-up questionnaire for a risk
    
    Args:
        api_key: Gemini API key
        risk_id: Risk ID from database (e.g., 'RSK-001')
    
    Returns:
        Questionnaire JSON
    """
    
    print("\n" + "="*80)
    print(f"🔄 GENERATING FOLLOW-UP QUESTIONNAIRE FOR {risk_id}")
    print("="*80)
    
    # Load risk data from database
    db = RiskRegisterDB()
    risk_data = db.get_risk(risk_id)
    
    if not risk_data:
        return {
            'error': f'Risk {risk_id} not found in database',
            'status': 'error'
        }
    
    print(f"\n✅ Loaded risk: {risk_data.get('risk_title', 'Unknown')}")
    print(f"   Owner: {risk_data.get('risk_owner', 'Unknown')}")
    print(f"   Decision: {risk_data.get('management_decision', 'Unknown')}")
    
    # Create agent and task
    agent = create_followup_agent(api_key)
    task = create_followup_task(agent, risk_data)
    
    # Run crew
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
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
        
        print("\n" + "="*80)
        print("✅ FOLLOW-UP QUESTIONNAIRE GENERATED!")
        print("="*80)
        
        # Show summary
        total_questions = sum(len(s.get('questions', [])) for s in questionnaire.get('sections', []))
        print(f"\n📋 Generated {len(questionnaire.get('sections', []))} sections")
        print(f"📋 Total {total_questions} questions")
        
        return questionnaire
        
    except json.JSONDecodeError as e:
        print(f"\n⚠️ JSON parsing failed: {e}")
        return {
            'error': 'JSON parsing failed',
            'raw_output': str(result)[:1000],
            'status': 'error'
        }


if __name__ == "__main__":
    print("Agent Follow-up (Hybrid Approach) - Ready!")
    print("Generates intelligent follow-up questionnaires by analyzing treatment plans")