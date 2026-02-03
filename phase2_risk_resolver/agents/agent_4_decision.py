"""
Agent 4: Management Decision Generator
Generates management decision options (TREAT/ACCEPT/TRANSFER/TERMINATE) for each threat
"""

import os
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any


@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """
    Search the knowledge base for risk management information.
    Use this to discover treatment options, risk owners, priority levels, etc.
    """
    from phase2_risk_resolver.tools.memory_rag_tool import search_with_memory
    return search_with_memory(query)


def create_management_decision_agent(api_key: str) -> Agent:
    """Create Agent for Management Decision Generation"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_VERBOSE"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.0
    )
    
    agent = Agent(
        role="Risk Management Decision Specialist",
        
        goal="""Discover treatment decision options from the organization's documents and 
        generate RICH, CONTEXTUAL Management Decision options for ALL threats in ONE analysis 
        to help users choose between TREAT/ACCEPT/TRANSFER/TERMINATE.""",
        
        backstory="""You are a specialist in risk management decisions who generates decision options
        to help stakeholders choose the appropriate treatment strategy (TREAT/ACCEPT/TRANSFER/TERMINATE).
        
        You create EXCEPTIONAL decision options that:
        
        1. **Show Rich Context:**
           - Display current risk status prominently
           - Show existing controls vs gaps
           - Explain why treatment is needed
           - Provide risk metrics and trends
        
        2. **Provide Detailed Control Information:**
           - For each recommended control, include:
             * Why it's needed (addresses which gap)
             * Effectiveness rating
             * Estimated cost
             * Implementation timeline
             * Expected risk reduction
             * Priority level
        
        3. **Smart Suggestions:**
           - Suggest priority based on risk level
           - Suggest timeline based on risk severity
           - Suggest budget based on control costs
           - Suggest risk owner based on asset type
        
        4. **CRITICAL - RICH Treatment Options:**
           - For EACH treatment option (TREAT/ACCEPT/TRANSFER/TERMINATE), provide:
             * FULL description (3-5 sentences explaining what it means)
             * DETAILED recommendation (when to use this option)
             * COMPREHENSIVE consequences (what happens if you choose this)
             * Estimated cost range
             * Typical timeline
             * Approval requirements
             * Monitoring requirements
           - Make options informative and decision-ready
           - Help users understand trade-offs clearly
        
        You discover from the knowledge base:
        - Treatment options (Treat/Accept/Transfer/Terminate)
        - Risk owner roles by asset type
        - Priority levels
        - Approval processes
        - Timeline expectations
        
        CRITICAL RULES:
        1. Process ALL threats in ONE analysis (not separately)
        2. Use the Search Knowledge Base tool extensively to discover their methodology
        3. Never assume - always search and learn
        4. NEVER generate simple 1-line descriptions - ALWAYS provide RICH, DETAILED information!""",
        
        tools=[search_knowledge_base],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return agent


def generate_management_decisions(
    api_key: str,
    asset_data: Dict[str, Any],
    agent_1_results: Dict[str, Any],
    agent_2_results: Dict[str, Any],
    agent_3_results: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate Management Decision options for ALL threats based on Agent 1-3 results
    
    Args:
        api_key: Gemini API key
        asset_data: Asset information
        agent_1_results: Impact assessment results
        agent_2_results: Risk quantification results
        agent_3_results: Control evaluation results
    
    Returns:
        Management Decision options for each threat in JSON format
    """
    
    try:
        agent = create_management_decision_agent(api_key)
        
        # Extract data from previous agents
        asset_name = asset_data.get('asset_name', 'Unknown Asset')
        
        threats = agent_2_results.get('threat_risk_quantification', [])
        control_eval = agent_3_results.get('threat_control_evaluation', [])
        
        if not threats:
            return {'error': 'No threats found in Agent 2 results'}
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        print("\n" + "="*80)
        print(f"🤖 AGENT 4: MEMORY CACHE APPROACH - {len(threats)} THREATS...")
        print("="*80)
        
        # Build context for ALL threats
        threats_context = []
        for idx, threat_data in enumerate(threats):
            threat_name = threat_data.get('threat', f'Threat {idx+1}')
            risk_rating = threat_data.get('risk_evaluation_rating', {}).get('rating', 0)
            risk_level = threat_data.get('risk_evaluation_rating', {}).get('level', 'Unknown')
            
            if idx < len(control_eval):
                control_data = control_eval[idx]
                existing_controls = control_data.get('controls_identified', [])
                recommended_controls = control_data.get('recommended_controls', [])
                control_rating = control_data.get('control_rating_calculation', {}).get('control_rating', 0)
                residual_risk = control_data.get('residual_risk', {}).get('residual_risk_value', 0)
                control_gaps = control_data.get('control_gaps', [])
            else:
                existing_controls = []
                recommended_controls = []
                control_rating = 0
                residual_risk = 0
                control_gaps = []
            
            threats_context.append({
                'threat_name': threat_name,
                'threat_index': idx + 1,
                'risk_rating': f"{risk_rating}/5",
                'risk_level': risk_level,
                'control_rating': f"{control_rating}/5",
                'residual_risk': f"{residual_risk}/5",
                'existing_controls': existing_controls,
                'recommended_controls': recommended_controls,
                'control_gaps': control_gaps
            })
        
        # Build dynamic threat keys example
        threat_keys_example = ", ".join([f'"threat_{i+1}": {{ ... }}' for i in range(len(threats))])
        
        context = f"""
# TASK: Generate Management Decision Options for ALL {len(threats)} Threats in ONE Analysis

## PHASE 1: DISCOVER FROM KNOWLEDGE BASE (with memory cache)

**Step 1:** Search for "Risk Treatment Decision options TREAT ACCEPT TRANSFER TERMINATE"
- What does each option mean? (Get FULL definitions - 3-5 sentences each)
- When is each option appropriate? (Get detailed recommendations)
- What are the consequences? (Get comprehensive impact descriptions)
- What are typical costs and timelines for each?
- What approvals are needed for each option?

**Step 2:** Search for "Risk owner roles approval workflow"
- Who approves treatment decisions?
- What roles are involved?

## PHASE 2: ALL THREATS CONTEXT

**Asset:** {asset_name}
**Total Threats:** {len(threats)}

{json.dumps(threats_context, indent=2)}

## PHASE 3: GENERATE DECISION OPTIONS FOR ALL THREATS

Generate decision options for ALL {len(threats)} threats in ONE JSON output.

**Required JSON Structure:**
```json
{{
  "threat_1": {{
    "threat_name": "...",
    "threat_index": 1,
    "risk_rating": "X/5",
    "residual_risk": "Y/5",
    "decision_options": [
      {{
        "value": "TREAT",
        "label": "Treat the Risk (Implement Controls)",
        "description": "FULL 3-5 sentence description...",
        "recommendation": "DETAILED 2-3 sentence recommendation...",
        "consequences": "COMPREHENSIVE 2-3 sentence consequences...",
        "estimated_cost": "$X - $Y",
        "typical_timeline": "X-Y months",
        "approval_required": "Who approves",
        "monitoring_required": "What monitoring"
      }},
      // SAME for ACCEPT, TRANSFER, TERMINATE (4 options total)
    ],
    "recommended_controls": [...],
    "control_gaps": [...]
  }},
  {threat_keys_example}
}}
```

**CRITICAL RULES:**
1. Process ALL {len(threats)} threats in ONE output
2. Each threat key: threat_1, threat_2, threat_3, ... threat_{len(threats)}
3. Each decision option MUST have ALL 9 fields (value, label, description, recommendation, consequences, estimated_cost, typical_timeline, approval_required, monitoring_required)
4. Use memory cache for searches (cache hits = no API calls)
5. Description MUST be 3-5 sentences
6. Recommendation MUST be 2-3 sentences
7. Consequences MUST be 2-3 sentences

**Output ONLY valid JSON, nothing else.**
"""
        
        task = Task(
            description=context,
            agent=agent,
            expected_output=f"Management Decision options for ALL {len(threats)} threats in JSON format"
        )
        
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=False
        )
        
        print(f"\n🤖 Agent 4 will use memory cache (like Agents 1-3)")
        print(f"   - Cache hits = No API calls")
        print(f"   - Cache misses = API calls + cache save")
        
        result = crew.kickoff()
        
        result_text = str(result)
        
        if '```json' in result_text:
            json_start = result_text.find('```json') + 7
            json_end = result_text.find('```', json_start)
            json_text = result_text[json_start:json_end].strip()
        elif '```' in result_text:
            json_start = result_text.find('```') + 3
            json_end = result_text.find('```', json_start)
            json_text = result_text[json_start:json_end].strip()
        else:
            json_text = result_text.strip()
        
        try:
            all_decisions = json.loads(json_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', json_text)
            if json_match:
                all_decisions = json.loads(json_match.group(0))
            else:
                return {'error': 'Could not parse JSON output', 'raw_output': result_text}
        
        print("\n" + "="*80)
        print("✅ MANAGEMENT DECISIONS GENERATED!")
        print("="*80)
        print(f"\n📋 Generated decisions for {len(all_decisions)} threat(s) using memory cache")
        
        for threat_key, decision in all_decisions.items():
            threat_name = decision.get('threat_name', 'Unknown')
            options_count = len(decision.get('decision_options', []))
            print(f"   • {threat_name}: {options_count} options")
        
        print("="*80 + "\n")
        
        # Build final response
        final_response = {
            'metadata': {
                'asset_name': asset_name,
                'generation_date': current_date,
                'total_threats': len(all_decisions),
                'processing_method': 'memory_cache_like_agents_1_3'
            },
            'management_decisions': all_decisions
        }
        
        return final_response
        
    except Exception as e:
        print(f"\n❌ Error in memory cache processing: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'error': str(e),
            'processing_method': 'memory_cache_like_agents_1_3'
        }


def run_management_decision_generator(api_key: str, asset_data: Dict, agent_1_results: Dict, agent_2_results: Dict, agent_3_results: Dict) -> Dict:
    """
    Main function to run Management Decision generator
    Called from main_app.py
    """
    return generate_management_decisions(api_key, asset_data, agent_1_results, agent_2_results, agent_3_results)


def run_risk_decision(api_key: str,
                     asset_data: Dict[str, Any],
                     impact_results: Dict[str, Any],
                     risk_results: Dict[str, Any],
                     control_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Alias for main_app.py compatibility - Generates Management Decision options
    """
    return generate_management_decisions(api_key, asset_data, impact_results, risk_results, control_results)


if __name__ == "__main__":
    print("Agent 4: Management Decision Generator")
    print("Generates decision options (TREAT/ACCEPT/TRANSFER/TERMINATE) for each threat")