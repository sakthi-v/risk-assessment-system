"""
🔧 Agent 3 Follow-up - Control Re-evaluation
Re-evaluates control effectiveness after implementation during follow-up
"""

from crewai import Agent, Task, Crew, LLM
import json
from typing import Dict, Any
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api_key_manager import handle_api_error, get_active_api_key

def create_agent_3_followup(api_key: str) -> Agent:
    """Create Agent 3 for control re-evaluation"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.0
    )
    
    agent = Agent(
        role="Control Effectiveness Evaluator (Follow-up)",
        goal="Re-evaluate control effectiveness after implementation and calculate new control rating",
        backstory="""You are a cybersecurity control assessment expert conducting follow-up evaluations.
        You analyze which controls have been implemented, assess their effectiveness, and calculate
        an updated control rating based on actual implementation status.""",
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return agent


def run_agent_3_followup(api_key: str, risk_data: Dict[str, Any], followup_answers: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    """
    Re-evaluate controls after follow-up
    
    Args:
        api_key: Gemini API key
        risk_data: Original risk data from database
        followup_answers: User's follow-up questionnaire answers
    
    Returns:
        Dict with new control rating and analysis
    """
    
    print("\n" + "="*80)
    print("🔧 AGENT 3 FOLLOW-UP: RE-EVALUATING CONTROLS")
    print("="*80)
    
    # Extract data
    risk_id = risk_data.get('risk_id', 'Unknown')
    original_control_rating = risk_data.get('control_rating', 0)
    treatment_actions = risk_data.get('treatment_actions', [])
    
    # Handle NULL or empty treatment_actions
    if treatment_actions is None:
        treatment_actions = []
    elif isinstance(treatment_actions, str):
        try:
            treatment_actions = json.loads(treatment_actions)
        except:
            treatment_actions = []
    
    # If still empty, create dummy actions from treatment_plan
    if not treatment_actions:
        treatment_plan = risk_data.get('treatment_plan', '')
        if treatment_plan:
            treatment_actions = [
                {'action': 'Implement treatment plan', 'description': treatment_plan[:200]}
            ]
        else:
            treatment_actions = [
                {'action': 'Implement controls', 'description': 'No specific actions recorded'}
            ]
    
    # Run crew with API rotation
    for attempt in range(max_retries):
        try:
            current_key = api_key if attempt == 0 else get_active_api_key()
            agent = create_agent_3_followup(current_key)
            
            # Create task inside loop (needs agent reference)
            task = Task(
                description=f"""
                RE-EVALUATE CONTROL EFFECTIVENESS FOR RISK: {risk_id}
                
                ORIGINAL ASSESSMENT:
                - Original Control Rating: {original_control_rating}/5
                - Treatment Actions Planned: {len(treatment_actions)} controls
                
                TREATMENT ACTIONS:
                {json.dumps(treatment_actions, indent=2)}
                
                FOLLOW-UP ANSWERS (Implementation Status):
                {json.dumps(followup_answers, indent=2)}
                
                YOUR TASK:
                1. Analyze which controls have been implemented
                2. Assess the effectiveness of implemented controls
                3. Calculate NEW control rating (1-5 scale)
                
                CALCULATION LOGIC:
                - Count how many controls are "Completed" or "In Progress"
                - Weight by effectiveness ratings provided
                - Calculate: (Implemented Controls / Total Controls) * 5
                - Adjust based on effectiveness ratings
                
                OUTPUT FORMAT (JSON only):
                {{
                    "controls_analyzed": <number>,
                    "controls_implemented": <number>,
                    "controls_in_progress": <number>,
                    "controls_not_started": <number>,
                    "implementation_percentage": <0-100>,
                    "new_control_rating": <1-5 with decimals>,
                    "original_control_rating": {original_control_rating},
                    "control_improvement": <difference>,
                    "effectiveness_summary": "Brief summary of control effectiveness",
                    "key_improvements": ["improvement 1", "improvement 2"],
                    "remaining_gaps": ["gap 1", "gap 2"]
                }}
                """,
                expected_output="JSON with new control rating and analysis",
                agent=agent
            )
            
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=True,
                memory=False
            )
            
            result = crew.kickoff()
            break
            
        except Exception as e:
            if attempt < max_retries - 1:
                new_key = handle_api_error(e, "Agent 3 Follow-up")
                if new_key:
                    print(f"🔄 Retrying Agent 3 (attempt {attempt + 2}/{max_retries})...")
                    continue
            raise
    
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
        
        control_evaluation = json.loads(result_text)
        
        print("\n" + "="*80)
        print("✅ AGENT 3 FOLLOW-UP COMPLETE!")
        print("="*80)
        print(f"Original Control Rating: {original_control_rating}/5")
        print(f"NEW Control Rating: {control_evaluation.get('new_control_rating')}/5")
        print(f"Improvement: +{control_evaluation.get('control_improvement')}")
        print(f"Implementation: {control_evaluation.get('implementation_percentage')}%")
        
        return control_evaluation
        
    except json.JSONDecodeError as e:
        print(f"\n⚠️ JSON parsing failed: {e}")
        
        # Fallback calculation
        total_controls = len(treatment_actions)
        implemented = 0
        
        for answer_key, answer_value in followup_answers.items():
            if 'status' in answer_key.lower():
                if 'COMPLETED' in str(answer_value).upper():
                    implemented += 1
        
        implementation_pct = (implemented / total_controls * 100) if total_controls > 0 else 0
        new_rating = (implemented / total_controls * 5) if total_controls > 0 else original_control_rating
        
        return {
            'controls_analyzed': total_controls,
            'controls_implemented': implemented,
            'implementation_percentage': implementation_pct,
            'new_control_rating': round(new_rating, 1),
            'original_control_rating': original_control_rating,
            'control_improvement': round(new_rating - original_control_rating, 1),
            'effectiveness_summary': f'{implemented} out of {total_controls} controls implemented',
            'raw_output': str(result)[:500]
        }


if __name__ == "__main__":
    print("Agent 3 Follow-up - Control Re-evaluation Ready!")
