"""
📊 Agent 2 Follow-up - Risk Recalculation
Recalculates residual risk after control improvements during follow-up
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

def create_agent_2_followup(api_key: str) -> Agent:
    """Create Agent 2 for risk recalculation"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.0
    )
    
    agent = Agent(
        role="Risk Quantification Analyst (Follow-up)",
        goal="Recalculate residual risk based on improved control effectiveness",
        backstory="""You are a risk quantification expert conducting follow-up assessments.
        You recalculate residual risk based on the new control rating after implementation,
        using the organization's risk methodology and formulas.""",
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return agent


def run_agent_2_followup(api_key: str, risk_data: Dict[str, Any], new_control_rating: float, max_retries: int = 3) -> Dict[str, Any]:
    """
    Recalculate residual risk after control improvements
    
    Args:
        api_key: Gemini API key
        risk_data: Original risk data from database
        new_control_rating: New control rating from Agent 3 follow-up
    
    Returns:
        Dict with new residual risk and analysis
    """
    
    print("\n" + "="*80)
    print("📊 AGENT 2 FOLLOW-UP: RECALCULATING RESIDUAL RISK")
    print("="*80)
    
    # Extract data
    risk_id = risk_data.get('risk_id', 'Unknown')
    inherent_risk = risk_data.get('inherent_risk_rating', 0)
    original_control_rating = risk_data.get('control_rating', 0)
    original_residual_risk = risk_data.get('residual_risk_rating', 0)
    
    # Run crew with API rotation
    for attempt in range(max_retries):
        try:
            current_key = api_key if attempt == 0 else get_active_api_key()
            agent = create_agent_2_followup(current_key)
            
            # Create task inside loop (needs agent reference)
            task = Task(
                description=f"""
                RECALCULATE RESIDUAL RISK FOR: {risk_id}
                
                ORIGINAL ASSESSMENT:
                - Risk Rating: {inherent_risk}/5 (unchanged - threat doesn't change)
                - Original Control Rating: {original_control_rating}/5
                - Original Residual Risk: {original_residual_risk}/5
                
                FOLLOW-UP ASSESSMENT:
                - NEW Control Rating: {new_control_rating}/5
                - Control Improvement: +{new_control_rating - original_control_rating}
                
                YOUR TASK:
                Recalculate the residual risk using the organization's formula:
                
                FORMULA (per organizational methodology):
                Residual Risk = Risk Rating - Control Rating
                
                Where:
                - Risk Rating = {inherent_risk}/5 (unchanged - threat doesn't change)
                - Control Rating = {new_control_rating}/5 (improved after implementation)
                
                CALCULATION:
                1. New Residual Risk = {inherent_risk} - {new_control_rating}
                2. Ensure result is between 0 and 5
                3. Calculate risk reduction percentage
                
                OUTPUT FORMAT (JSON only):
                {{
                    "inherent_risk_rating": {inherent_risk},
                    "original_control_rating": {original_control_rating},
                    "new_control_rating": {new_control_rating},
                    "original_residual_risk": {original_residual_risk},
                    "new_residual_risk": <1-5 with decimals>,
                    "risk_reduction": <difference>,
                    "risk_reduction_percentage": <0-100>,
                    "risk_level_before": "Extreme/High/Moderate/Low",
                    "risk_level_after": "Extreme/High/Moderate/Low",
                    "risk_trend": "Improved/Same/Worsened",
                    "calculation_explanation": "Brief explanation of calculation",
                    "recommendation": "Brief recommendation based on new risk level"
                }}
                """,
                expected_output="JSON with new residual risk and analysis",
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
                new_key = handle_api_error(e, "Agent 2 Follow-up")
                if new_key:
                    print(f"🔄 Retrying Agent 2 (attempt {attempt + 2}/{max_retries})...")
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
        
        risk_calculation = json.loads(result_text)
        
        print("\n" + "="*80)
        print("✅ AGENT 2 FOLLOW-UP COMPLETE!")
        print("="*80)
        print(f"Original Residual Risk: {original_residual_risk}/5")
        print(f"NEW Residual Risk: {risk_calculation.get('new_residual_risk')}/5")
        print(f"Risk Reduction: {risk_calculation.get('risk_reduction_percentage')}%")
        print(f"Trend: {risk_calculation.get('risk_trend')}")
        
        return risk_calculation
        
    except json.JSONDecodeError as e:
        print(f"\n⚠️ JSON parsing failed: {e}")
        
        # Fallback calculation using correct formula
        new_residual = max(0, min(5, inherent_risk - new_control_rating))
        risk_reduction = original_residual_risk - new_residual
        risk_reduction_pct = (risk_reduction / original_residual_risk * 100) if original_residual_risk > 0 else 0
        
        return {
            'inherent_risk_rating': inherent_risk,
            'original_control_rating': original_control_rating,
            'new_control_rating': new_control_rating,
            'original_residual_risk': original_residual_risk,
            'new_residual_risk': round(new_residual, 2),
            'risk_reduction': round(risk_reduction, 2),
            'risk_reduction_percentage': round(risk_reduction_pct, 1),
            'risk_trend': 'Improved' if risk_reduction > 0 else 'Same',
            'calculation_explanation': f'Residual = {inherent_risk} - {new_control_rating} = {new_residual:.2f}',
            'raw_output': str(result)[:500]
        }


if __name__ == "__main__":
    print("Agent 2 Follow-up - Risk Recalculation Ready!")
