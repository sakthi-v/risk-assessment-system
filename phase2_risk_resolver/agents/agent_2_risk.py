"""
Agent 2 ULTIMATE: Risk Quantification Agent
- Discovers methodology from RAG (intelligent, no hardcoding)
- Uses questionnaire answers for probability assessment
- Outputs CORRECT structure for detailed UI displays
"""
from crewai import Agent, Task, Crew
from crewai.tools import tool
from crewai import LLM
import json
from typing import Dict, Any
import os
from pathlib import Path

from ..config.agent_definitions import AGENT_2_RISK_QUANTIFICATION
from ..tools.memory_rag_tool import search_with_memory


@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base with memory caching"""
    return search_with_memory(query)


def create_risk_quantification_agent(api_key: str) -> Agent:
    """Create Truly Agentic Risk Quantification Agent"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_VERBOSE"] = "false"
    
    llm = LLM(
    model="gemini/gemini-3-flash-preview",
    api_key=api_key,
    temperature=0.0
    )
    
    agent = Agent(
        role=AGENT_2_RISK_QUANTIFICATION["role"],
        goal=AGENT_2_RISK_QUANTIFICATION["goal"],
        backstory=AGENT_2_RISK_QUANTIFICATION["backstory"],
        tools=[search_knowledge_base],
        llm=llm,
        verbose=False,
        allow_delegation=False
    )
    
    return agent

def create_risk_quantification_task(agent: Agent, asset_data: Dict[str, Any], 
                                     impact_results: Dict[str, Any]) -> Task:
    """Create Pure Discovery Task for Risk Quantification - ULTIMATE VERSION"""
    
    # Extract questionnaire answers if available
    questionnaire_answers = asset_data.get('questionnaire_answers', {})
    has_questionnaire = bool(questionnaire_answers)
    
    # Build formatted questionnaire context
    questionnaire_context = ""
    if has_questionnaire:
        questionnaire_context = "\n═══════════════════════════════════════════════════════════════════════════════\n"
        questionnaire_context += "QUESTIONNAIRE ANSWERS - USE FOR PROBABILITY ASSESSMENT!\n"
        questionnaire_context += "═══════════════════════════════════════════════════════════════════════════════\n\n"
        questionnaire_context += "The asset owner provided answers about threat exposure, controls, and history.\n"
        questionnaire_context += "USE THESE to assess risk probability accurately!\n\n"
        
        answer_count = 0
        for q_id, q_data in questionnaire_answers.items():
            if isinstance(q_data, dict):
                answer_count += 1
                question = q_data.get('question_text', q_id)
                answer = q_data.get('answer', 'No answer')
                section = q_data.get('section', '')
                why_matters = q_data.get('why_this_matters', '')
                
                questionnaire_context += f"**Question {answer_count}:** {question}\n"
                questionnaire_context += f"**User's Answer:** {answer}\n"
                if section:
                    questionnaire_context += f"**Section:** {section}\n"
                if why_matters:
                    questionnaire_context += f"**Relevance:** {why_matters}\n"
                questionnaire_context += "\n" + "-"*80 + "\n\n"
        
        questionnaire_context += "═══════════════════════════════════════════════════════════════════════════════\n"
        questionnaire_context += f"CRITICAL: You have {answer_count} user responses.\n"
        questionnaire_context += "Use these to assess probability factors:\n"
        questionnaire_context += "- Internet exposure → External threat probability\n"
        questionnaire_context += "- Access controls → Insider threat probability\n"
        questionnaire_context += "- Monitoring capability → Detection probability\n"
        questionnaire_context += "- Historical incidents → Frequency data\n"
        questionnaire_context += "- Existing controls → Reduces probability\n"
        questionnaire_context += "CITE specific questionnaire answers in your probability reasoning!\n"
        questionnaire_context += "═══════════════════════════════════════════════════════════════════════════════\n\n"
    else:
        questionnaire_context = "\n(No questionnaire answers - assess probability based on general asset info)\n\n"
    
    # Build basic asset info
    basic_asset_info = {
        'asset_name': asset_data.get('asset_name'),
        'asset_type': asset_data.get('asset_type'),
        'asset_owner': asset_data.get('asset_owner'),
        'location': asset_data.get('location'),
        'description': asset_data.get('description', '')
    }
    
    # Build threats info safely
    threats = asset_data.get('threats_and_vulnerabilities', [])
    threats_summary = []
    for threat in threats:
        threat_name = threat.get('threat', 'Unknown')
        risk_stmt = threat.get('risk_statement', '')
        vulns = threat.get('vulnerabilities', [])
        vuln_list = [v.get('vulnerability', 'Unknown') if isinstance(v, dict) else str(v) for v in vulns]
        
        threats_summary.append({
            'threat': threat_name,
            'risk_statement': risk_stmt,
            'vulnerabilities': vuln_list
        })
    
    # Pre-build impact data to avoid unhashable dict error
    overall_ratings_data = impact_results.get('overall_ratings') or impact_results.get('overall_cia_ratings', {})
    threat_analysis_data = impact_results.get('threat_analysis') or impact_results.get('threat_cia_assessments', [])
    
    task = Task(
        description=f"""
        ═══════════════════════════════════════════════════════════════════════════════
        AGENT 2: INTELLIGENT RISK QUANTIFICATION
        ═══════════════════════════════════════════════════════════════════════════════
        
        You are an EXPERT risk quantification analyst who DISCOVERS the organization's 
        risk methodology from their documents and USES questionnaire data for accuracy.
        
        ═══════════════════════════════════════════════════════════════════════════════
        ASSET INFORMATION
        ═══════════════════════════════════════════════════════════════════════════════
        
        {json.dumps(basic_asset_info, indent=2)}
        
        ═══════════════════════════════════════════════════════════════════════════════
        THREATS TO ASSESS
        ═══════════════════════════════════════════════════════════════════════════════
        
        {json.dumps(threats_summary, indent=2)}
        
        ═══════════════════════════════════════════════════════════════════════════════
        IMPACT ASSESSMENT (FROM AGENT 1)
        ═══════════════════════════════════════════════════════════════════════════════
        
        Agent 1 assessed CIA impact. You will use their overall ratings for risk calculation.
        
        Overall Impact Ratings:
        {json.dumps(overall_ratings_data, indent=2)}
        
        Per-Threat Impact Assessments:
        {json.dumps(threat_analysis_data, indent=2)}
        
        {questionnaire_context}
        
        ═══════════════════════════════════════════════════════════════════════════════
        YOUR MISSION: DISCOVER & QUANTIFY RISK
        ═══════════════════════════════════════════════════════════════════════════════
        
        STEP 1: DISCOVER RISK QUANTIFICATION METHODOLOGY
        
        Search the knowledge base to find:
        - How do they quantify risk? (Quantitative/Qualitative/Semi-quantitative?)
        - What formula do they use? (Impact × Probability? Other?)
        - What scales do they use for Impact and Probability?
        - What are their risk levels? (Low/Medium/High? Other?)
        - What makes a risk "Acceptable" vs "Non-acceptable"?
        
        Example searches you might make:
        - "risk quantification methodology"
        - "risk calculation formula"
        - "probability rating scale"
        - "risk matrix"
        - "risk acceptance criteria"
        
        YOU DECIDE what searches to make!
        
        ═══════════════════════════════════════════════════════════════════════════════
        STEP 2: ASSESS PROBABILITY FOR EACH THREAT
        ═══════════════════════════════════════════════════════════════════════════════
        
        For each threat, assess PROBABILITY using:
        
        1. **Questionnaire Data (if available):**
           - Internet exposure answers → External threat probability
           - Access control answers → Insider threat probability
           - Monitoring answers → Detection capability
           - Historical incidents → Actual frequency
           - Existing controls → Probability reducers
           
           IMPORTANT: CITE specific questionnaire answers in reasoning!
           Good: "User indicated in questionnaire that database is VPN-only, reducing external attack probability"
           Bad: "Probability is medium" (without evidence)
        
        2. **Threat Nature:**
           - How common is this threat?
           - How motivated are threat actors?
           - How easy is exploitation?
        
        3. **Discovered Scale:**
           - Use the probability scale you discovered
           - Match to their definitions
        
        ═══════════════════════════════════════════════════════════════════════════════
        STEP 3: CALCULATE RISK VALUE
        ═══════════════════════════════════════════════════════════════════════════════
        
        For each threat:
        1. Take Impact rating from Agent 1
        2. Assign Probability rating (your assessment)
        3. Calculate Risk Value using discovered formula
        4. Map to Risk Level using discovered mapping
        5. Classify as Acceptable/Non-acceptable using discovered criteria
        
        ═══════════════════════════════════════════════════════════════════════════════
        OUTPUT FORMAT - MATCHES UI DISPLAY REQUIREMENTS
        ═══════════════════════════════════════════════════════════════════════════════
        
        Return ONLY valid JSON in this EXACT structure:
        
        {{
            "discovery_summary": {{
                "methodology": "discovered methodology name",
                "risk_calculation": {{
                    "method": "Formula/Matrix/Custom",
                    "formula": "discovered formula (e.g., Impact × Probability)",
                    "description": "how it works"
                }},
                "probability_scale": {{
                    "type": "discovered scale type",
                    "levels": ["level names discovered"],
                    "range": "numeric range if applicable"
                }},
                "impact_scale": {{
                    "type": "discovered scale type", 
                    "levels": ["level names discovered"],
                    "range": "numeric range if applicable"
                }},
                "risk_level_mapping": {{
                    "method": "how values map to levels",
                    "levels": ["discovered risk level names"],
                    "thresholds": "threshold definitions"
                }},
                "acceptance_criteria": "discovered criteria",
                "questionnaire_answers_used": {has_questionnaire}
            }},
            "summary": {{
                "total_threats_assessed": 3,
                "highest_risk_value": 20,
                "non_acceptable_risks_count": 2,
                "acceptable_risks_count": 1,
                "overall_risk_level": "HIGH"
            }},
            "threat_risk_quantification": [
                {{
                    "threat": "Threat name from input",
                    "vulnerabilities": ["vulnerability list from input"],
                    "risk_statement": "Risk statement from input",
                    "risk_impact": {{
                        "rating": 4,
                        "category": "High",
                        "reasoning": "Based on Agent 1 CIA assessment: Confidentiality=HIGH, Integrity=HIGH..."
                    }},
                    "risk_probability": {{
                        "rating": 5,
                        "category": "Very High",
                        "reasoning": "User indicated in questionnaire that database is internet-facing with 100+ users. Historical incidents show 3 attempts in last 6 months per questionnaire. Limited monitoring capability confirmed in questionnaire."
                    }},
                    "risk_value": {{
                        "value": 20,
                        "calculation": "4 (impact) × 5 (probability) = 20"
                    }},
                    "risk_evaluation_rating": {{
                        "rating": 5,
                        "level": "EXTREME",
                        "mapping_rationale": "Risk value 20 maps to EXTREME level per discovered risk matrix"
                    }},
                    "risk_classification": {{
                        "classification": "NON-ACCEPTABLE",
                        "criteria_applied": "discovered acceptance criteria",
                        "justification": "EXTREME risks are non-acceptable per organizational policy"
                    }}
                }}
            ],
            "rag_queries_performed": ["list of queries"],
            "rag_sources_consulted": ["list of sources"]
        }}
        
        ═══════════════════════════════════════════════════════════════════════════════
        CRITICAL REQUIREMENTS FOR UI DISPLAY
        ═══════════════════════════════════════════════════════════════════════════════
        
        The UI expects these EXACT fields:
        
        1. **summary** object with counts
        2. **threat_risk_quantification** array (not risk_assessments)
        3. Each threat needs:
           - risk_impact with rating and category
           - risk_probability with rating and category  
           - risk_value as object with value field
           - risk_evaluation_rating as object with rating field
        4. Use NUMERIC ratings (1-5) where applicable
        5. Include category names (Low, Medium, High, etc.)
        
        ═══════════════════════════════════════════════════════════════════════════════
        CRITICAL RULES
        ═══════════════════════════════════════════════════════════════════════════════
        
        DO:
        ✅ Discover methodology from RAG (don't assume)
        ✅ Use discovered scales and formulas exactly
        ✅ USE questionnaire answers for probability assessment
        ✅ CITE specific questionnaire answers in reasoning
        ✅ Calculate summary statistics
        ✅ Output exact structure for UI
        
        DON'T:
        ❌ Assume any formula (discover it!)
        ❌ Assume any scale (discover it!)
        ❌ Ignore questionnaire answers
        ❌ Write probability reasoning without citing questionnaire
        ❌ Change the output structure
        
        Your response must be ONLY the JSON object.
        """,
        expected_output="Risk quantification with discovered methodology and questionnaire-based probability assessment in UI-compatible format",
        agent=agent
    )
    
    return task


def run_risk_quantification(api_key: str, asset_data: Dict[str, Any], 
                            impact_results: Dict[str, Any]) -> Dict[str, Any]:
    """Run Intelligent Risk Quantification - ULTIMATE VERSION"""
    
    questionnaire_count = len(asset_data.get('questionnaire_answers', {}))
    
    print("=" * 80)
    print(f"🤖 AGENT 2: INTELLIGENT RISK QUANTIFICATION (ULTIMATE)")
    print(f"   Asset: {asset_data.get('asset_name')}")
    if questionnaire_count > 0:
        print(f"   ✅ Using {questionnaire_count} questionnaire answers for probability assessment!")
    else:
        print(f"   ℹ️ No questionnaire - assessing probability based on asset info")
    print("=" * 80)
    
    agent = create_risk_quantification_agent(api_key)
    task = create_risk_quantification_task(agent, asset_data, impact_results)
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=False,
        memory=False
    )
    
    print("\n🔍 Agent discovering risk methodology...")
    print("   - Searching for risk calculation formulas")
    print("   - Finding probability scales")
    print("   - Learning risk level mappings")
    if questionnaire_count > 0:
        print(f"   - Analyzing {questionnaire_count} questionnaire responses for probability")
    print()
    
    result = crew.kickoff()
    
    result_text = str(result)
    
    # Try to extract JSON - handle multiple extraction strategies
    try:
        # Strategy 1: Look for ```json blocks
        if '```json' in result_text:
            json_start = result_text.find('```json') + 7
            json_end = result_text.find('```', json_start)
            json_str = result_text[json_start:json_end].strip()
        # Strategy 2: Look for ``` blocks
        elif '```' in result_text:
            json_start = result_text.find('```') + 3
            json_end = result_text.find('```', json_start)
            json_str = result_text[json_start:json_end].strip()
        # Strategy 3: Find first { and last }
        else:
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx <= start_idx:
                raise ValueError("No JSON object found in response")
            
            json_str = result_text[start_idx:end_idx]
        
        # Parse JSON
        result_dict = json.loads(json_str)
        
        # Parse JSON
        result_dict = json.loads(json_str)
            
        print("\n✅ Risk quantification complete!")
        if questionnaire_count > 0:
            print(f"   ✅ Used {questionnaire_count} questionnaire answers for probability")
        print(f"   📊 Assessed {len(result_dict.get('threat_risk_quantification', []))} threats")
        print(f"   ⚠️ Non-acceptable risks: {result_dict.get('summary', {}).get('non_acceptable_risks_count', 0)}")
        
        return result_dict
            
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parsing error: {str(e)}")
        print(f"\n📄 Raw Output\n")
        print(result_text[:2000])  # Show first 2000 chars
        return {"error": f"JSON parsing failed: {str(e)}", "raw_response": result_text}
    except Exception as e:
        print(f"⚠️ Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}", "raw_response": result_text}