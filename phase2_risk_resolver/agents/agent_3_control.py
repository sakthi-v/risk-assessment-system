"""
Agent 3 ULTIMATE FIXED: Control Discovery & Evaluation Agent
- Discovers control framework from RAG (intelligent, no hardcoding)
- Uses questionnaire answers to identify existing controls and gaps
- FIXED: Gets correct risk rating from Agent 2
- FIXED: Uses correct residual risk formula (risk_rating - control_rating)
- Outputs COMPLETE structure for detailed UI displays including calculations
"""
from crewai import Agent, Task, Crew
from crewai.tools import tool
from crewai import LLM
import json
from typing import Dict, Any
import os

from ..config.agent_definitions import AGENT_3_CONTROL_DISCOVERY
from ..tools.memory_rag_tool import search_with_memory


@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base with memory caching"""
    return search_with_memory(query)


def create_control_discovery_agent(api_key: str) -> Agent:
    """Create Truly Agentic Control Discovery Agent"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_VERBOSE"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.0
    )
    
    agent = Agent(
        role=AGENT_3_CONTROL_DISCOVERY["role"],
        goal=AGENT_3_CONTROL_DISCOVERY["goal"],
        backstory=AGENT_3_CONTROL_DISCOVERY["backstory"],
        tools=[search_knowledge_base],
        llm=llm,
        verbose=False,
        allow_delegation=False
    )
    
    return agent


def create_control_discovery_task(agent: Agent, asset_data: Dict[str, Any],
                                  impact_results: Dict[str, Any],
                                  risk_results: Dict[str, Any]) -> Task:
    """Create Control Discovery Task - FIXED VERSION with Correct Risk Rating and Residual Formula"""
    
    # Extract questionnaire answers
    questionnaire_answers = asset_data.get('questionnaire_answers', {})
    has_questionnaire = bool(questionnaire_answers)
    
    # Build questionnaire context
    questionnaire_context = ""
    if has_questionnaire:
        questionnaire_context = "\n═══════════════════════════════════════════════════════════════════════════════\n"
        questionnaire_context += "QUESTIONNAIRE ANSWERS - USE FOR CONTROL IDENTIFICATION!\n"
        questionnaire_context += "═══════════════════════════════════════════════════════════════════════════════\n\n"
        
        answer_count = 0
        for q_id, q_data in questionnaire_answers.items():
            if isinstance(q_data, dict):
                answer_count += 1
                question = q_data.get('question_text', q_id)
                answer = q_data.get('answer', 'No answer')
                section = q_data.get('section', '')
                
                questionnaire_context += f"**Question {answer_count}:** {question}\n"
                questionnaire_context += f"**User's Answer:** {answer}\n"
                if section:
                    questionnaire_context += f"**Section:** {section}\n"
                
                # Highlight control-related answers
                answer_lower = str(answer).lower()
                if any(word in answer_lower for word in ['yes', 'enabled', 'implemented', 'active', 'configured']):
                    questionnaire_context += "**→ EXISTING CONTROL identified!**\n"
                elif any(word in answer_lower for word in ['no', 'not', 'missing', 'none', 'disabled']):
                    questionnaire_context += "**→ CONTROL GAP identified!**\n"
                
                questionnaire_context += "\n" + "-"*80 + "\n\n"
        
        questionnaire_context += "═══════════════════════════════════════════════════════════════════════════════\n"
        questionnaire_context += "CRITICAL: Use these answers to:\n"
        questionnaire_context += "1. Identify EXISTING controls (user said 'yes', 'enabled', etc.)\n"
        questionnaire_context += "2. Identify GAPS (user said 'no', 'missing', etc.)\n"
        questionnaire_context += "3. DON'T assume controls exist without questionnaire evidence!\n"
        questionnaire_context += "4. DON'T recommend controls user said already exist!\n"
        questionnaire_context += "═══════════════════════════════════════════════════════════════════════════════\n\n"
    else:
        questionnaire_context = "\n(No questionnaire - identify controls from general knowledge)\n\n"
    
    # Build asset and risk context - SAFE VERSION
    basic_info = {
        'asset_name': asset_data.get('asset_name'),
        'asset_type': asset_data.get('asset_type'),
        'asset_owner': asset_data.get('asset_owner'),
    }
    
    # Get risk summary
    risk_summary = risk_results.get('summary', {})
    threat_risks = risk_results.get('threat_risk_quantification', [])
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # FIX #1: BUILD COMPLETE THREAT SUMMARY WITH ALL RISK DATA FROM AGENT 2
    # ═══════════════════════════════════════════════════════════════════════════════
    
    threat_summary_list = []
    for t in threat_risks:
        threat_name = t.get('threat', 'Unknown')
        
        # Extract risk evaluation rating (BOTH text and numeric) - FIXED!
        risk_eval = t.get('risk_evaluation_rating', {})
        if isinstance(risk_eval, dict):
            risk_level = risk_eval.get('level', 'N/A')
            risk_rating_numeric = risk_eval.get('rating', 0)  # ✅ GET NUMERIC RATING!
        else:
            risk_level = str(risk_eval) if risk_eval else 'N/A'
            risk_rating_numeric = int(risk_eval) if isinstance(risk_eval, (int, float)) else 0
        
        # Extract risk value
        risk_val = t.get('risk_value', {})
        if isinstance(risk_val, dict):
            risk_value_numeric = risk_val.get('value', 0)  # ✅ GET RISK VALUE!
        else:
            risk_value_numeric = risk_val if isinstance(risk_val, (int, float)) else 0
        
        # Extract risk impact
        risk_imp = t.get('risk_impact', {})
        if isinstance(risk_imp, dict):
            risk_impact_numeric = risk_imp.get('rating', 0)
        else:
            risk_impact_numeric = int(risk_imp) if isinstance(risk_imp, (int, float)) else 0
        
        # Extract risk probability
        risk_prob = t.get('risk_probability', {})
        if isinstance(risk_prob, dict):
            risk_probability_numeric = risk_prob.get('rating', 0)
        else:
            risk_probability_numeric = int(risk_prob) if isinstance(risk_prob, (int, float)) else 0
        
        threat_summary_list.append({
            'threat': threat_name,
            'risk_level': risk_level,                     # Text: "EXTREME"
            'risk_rating': risk_rating_numeric,           # ✅ Numeric: 5
            'risk_value': risk_value_numeric,             # ✅ Numeric: 25
            'risk_impact': risk_impact_numeric,           # ✅ Numeric: 5
            'risk_probability': risk_probability_numeric  # ✅ Numeric: 5
        })
    
    task = Task(
        description=f"""
        ═══════════════════════════════════════════════════════════════════════════════
        AGENT 3: INTELLIGENT CONTROL DISCOVERY & EVALUATION (FIXED VERSION)
        ═══════════════════════════════════════════════════════════════════════════════
        
        You are an EXPERT control analyst who DISCOVERS the organization's control 
        framework and USES questionnaire data to accurately identify controls and gaps.
        
        ═══════════════════════════════════════════════════════════════════════════════
        ASSET & RISK CONTEXT FROM AGENT 2
        ═══════════════════════════════════════════════════════════════════════════════
        
        Asset: {json.dumps(basic_info, indent=2)}
        
        Risk Assessment Summary:
        {json.dumps(risk_summary, indent=2)}
        
        Threats with COMPLETE Risk Data (USE THESE ACTUAL VALUES!):
        {json.dumps(threat_summary_list, indent=2)}
        
        ═══════════════════════════════════════════════════════════════════════════════
        CRITICAL: USE ACTUAL RISK RATINGS FROM AGENT 2!
        ═══════════════════════════════════════════════════════════════════════════════
        
        The threat risk data above contains the ACTUAL risk ratings calculated by Agent 2.
        For each threat, you will find:
        - risk_rating: The numeric risk evaluation rating (e.g., 5) ← USE THIS!
        - risk_value: The calculated risk value (e.g., 25)
        - risk_impact: The impact rating (e.g., 5)
        - risk_probability: The probability rating (e.g., 5)
        
        YOU MUST USE THESE ACTUAL VALUES IN YOUR OUTPUT!
        
        For example, if Agent 2 calculated:
        - risk_rating: 5
        - risk_value: 25
        
        Then your output MUST show:
        - "risk_evaluation_rating": 5  (NOT 4 or any other hardcoded value!)
        - Use risk_rating (5) in residual risk calculation (NOT risk_value 25!)
        
        DO NOT use hardcoded example values!
        DO NOT assume risk ratings!
        USE THE EXACT DATA FROM AGENT 2 PROVIDED ABOVE!
        
        ═══════════════════════════════════════════════════════════════════════════════
        RESIDUAL RISK FORMULA (CRITICAL - FOLLOW EXACTLY!)
        ═══════════════════════════════════════════════════════════════════════════════
        
        Per organizational Excel template, residual risk is calculated as:
        
        **Residual Risk Value = Risk Evaluation Rating - Control Rating**
        
        From the threat data above:
        - risk_rating: This is the Risk Evaluation Rating (e.g., 5) ← USE THIS!
        - risk_value: This is Impact × Probability (e.g., 25) ← DO NOT USE FOR RESIDUAL!
        
        CORRECT calculation:
        1. Get risk_rating from threat data (e.g., 5)
        2. Calculate control_rating (weighted average, e.g., 1.92)
        3. Residual Risk Value = risk_rating - control_rating
        4. Example: 5 - 1.92 = 3.08 ✅
        
        WRONG calculations:
        ❌ residual_risk_value = risk_value - (control_rating × 0.5)
        ❌ residual_risk_value = 25 - ...
        ❌ DO NOT multiply control_rating by any factor!
        ❌ DO NOT use risk_value (25) in this formula!
        
        CORRECT: residual_risk_value = risk_rating - control_rating
        
        {questionnaire_context}
        
        ═══════════════════════════════════════════════════════════════════════════════
        YOUR MISSION: DISCOVER FRAMEWORK & EVALUATE CONTROLS
        ═══════════════════════════════════════════════════════════════════════════════
        
        STEP 1: DISCOVER CONTROL FRAMEWORK
        
        Search knowledge base to find:
        - What control framework do they use? (ISO 27001, NIST, CIS, etc.)
        - What control categories? (Technical, Administrative, Physical?)
        - What control types? (Preventive, Detective, Corrective, Compensating?)
        - How do they rate control effectiveness? (1-5 scale? High/Medium/Low?)
        - How do they calculate control ratings?
        - How do they calculate residual risk?
        
        Example searches:
        - "control framework"
        - "control categories"
        - "control effectiveness rating"
        - "residual risk calculation"
        
        ═══════════════════════════════════════════════════════════════════════════════
        STEP 2: IDENTIFY EXISTING CONTROLS (FROM QUESTIONNAIRE!) - THREAT-SPECIFIC!
        ═══════════════════════════════════════════════════════════════════════════════
        
        CRITICAL: Map controls to threats based on RELEVANCE!
        
        For EACH threat separately, identify ONLY controls that DIRECTLY mitigate that specific threat:
        
        Example - Ransomware/Malware Attack:
        ✅ RELEVANT: EDR/Antivirus (directly prevents malware)
        ✅ RELEVANT: Patch Management (prevents exploitation)
        ✅ RELEVANT: Email Filtering (prevents phishing)
        ❌ NOT RELEVANT: Full Disk Encryption (doesn't prevent ransomware)
        ❌ NOT RELEVANT: Physical Security Policies (doesn't prevent malware)
        
        Example - Physical Theft:
        ✅ RELEVANT: Full Disk Encryption (protects stolen data)
        ✅ RELEVANT: Physical Security Policies (prevents theft)
        ✅ RELEVANT: Remote Wipe (mitigates theft impact)
        ❌ NOT RELEVANT: EDR/Antivirus (doesn't prevent physical theft)
        ❌ NOT RELEVANT: MFA (doesn't prevent physical theft)
        
        Example - Unauthorized Data Breach via Credentials:
        ✅ RELEVANT: MFA (prevents credential compromise)
        ✅ RELEVANT: Access Controls (limits breach scope)
        ✅ RELEVANT: Session Monitoring (detects unauthorized access)
        ❌ NOT RELEVANT: Physical Security Policies (doesn't prevent credential breach)
        ❌ NOT RELEVANT: Backup (doesn't prevent breach)
        
        Example - Data Loss/Corruption:
        ✅ RELEVANT: Automated Backup (recovers lost data)
        ✅ RELEVANT: EDR/Antivirus (prevents malware corruption)
        ✅ RELEVANT: RAID/Redundancy (prevents hardware failure loss)
        ❌ NOT RELEVANT: MFA (doesn't prevent data loss)
        ❌ NOT RELEVANT: Physical Security (doesn't prevent corruption)
        
        For each RELEVANT control, provide:
        - control_id (from framework if applicable, e.g., "AC-2")
        - control_name (descriptive name)
        - category (Preventive/Detective/Corrective from framework)
        - current_rating (1-5 or High/Medium/Low based on effectiveness)
        - source ("Questionnaire" or "Organization Policy")
        - relevance_justification (WHY this control mitigates THIS specific threat)
        
        ═══════════════════════════════════════════════════════════════════════════════
        STEP 3: CALCULATE CONTROL RATINGS
        ═══════════════════════════════════════════════════════════════════════════════
        
        For each threat, calculate:
        
        1. **Control Category Averages:**
           - preventive_avg = average rating of all Preventive controls
           - detective_avg = average rating of all Detective controls  
           - corrective_avg = average rating of all Corrective controls
        
        2. **Weighted Control Rating:**
           - weighted_preventive = preventive_avg × 1.0
           - weighted_detective = detective_avg × 0.75
           - weighted_corrective = corrective_avg × 0.5
           - average_weighted = (weighted_preventive + weighted_detective + weighted_corrective) / 3
           - control_rating = average_weighted as NUMERIC value (e.g., 1.92)
           - control_rating_text = map numeric to text: 0-1.5="WEAK", 1.6-2.5="LIMITED", 2.6-3.5="ADEQUATE", 3.6-4.5="STRONG", 4.6-5="VERY STRONG"
        
        3. **Residual Risk (FIXED FORMULA):**
           - residual_risk_value = risk_rating - control_rating
           - Example: 5 (from Agent 2) - 1.92 (calculated) = 3.08 ✅
           - residual_risk_classification = map to risk level (Low/Medium/High/Critical)
           - DO NOT use: risk_value - (control_rating × 0.5) ❌
        
        ═══════════════════════════════════════════════════════════════════════════════
        STEP 4: IDENTIFY CONTROL GAPS
        ═══════════════════════════════════════════════════════════════════════════════
        
        Based on questionnaire:
        - User said "No MFA" → GAP: Multi-factor authentication missing
        - User said "No monitoring" → GAP: Security monitoring missing
        
        Don't recommend controls that questionnaire shows already exist!
        
        ═══════════════════════════════════════════════════════════════════════════════
        OUTPUT FORMAT - COMPLETE STRUCTURE FOR UI DISPLAY
        ═══════════════════════════════════════════════════════════════════════════════
        
        Return ONLY valid JSON in this EXACT structure:
        
        {{
            "discovery_summary": {{
                "control_framework": "discovered framework name",
                "control_categories": ["discovered categories"],
                "control_types": ["Preventive", "Detective", "Corrective", "Compensating"],
                "effectiveness_scale": {{
                    "type": "discovered scale",
                    "range": "1-5 or High/Medium/Low",
                    "definitions": "how effectiveness is measured"
                }},
                "control_rating_method": "discovered calculation method",
                "residual_risk_method": "Risk Evaluation Rating - Control Rating",
                "questionnaire_answers_used": {has_questionnaire}
            }},
            "threat_control_evaluation": [
                {{
                    "threat": "Threat name",
                    "vulnerabilities": ["vulnerability list"],
                    "controls_identified": [
                        {{
                            "control_id": "AC-2",
                            "control_name": "AES-256 Encryption at Rest",
                            "category": "Preventive",
                            "current_rating": 4,
                            "source": "Questionnaire",
                            "evidence": "User confirmed: 'Yes - AES-256 encryption enabled'",
                            "effectiveness": "HIGH"
                        }}
                    ],
                    "control_rating_calculation": {{
                        "weighted_preventive": "2.5 × 1.0 = 2.5",
                        "weighted_detective": "3.0 × 0.75 = 2.25",
                        "weighted_corrective": "2.0 × 0.5 = 1.0",
                        "average_weighted": 1.92,
                        "control_rating": 1.92,
                        "control_rating_text": "LIMITED"
                    }},
                    "control_category_averages": {{
                        "preventive_avg": 2.5,
                        "detective_avg": 3.0,
                        "corrective_avg": 2.0
                    }},
                    "risk_evaluation_rating": {{use_actual_value_from_agent_2_threat_data}},
                    "residual_risk": {{
                        "risk_evaluation_rating": {{use_risk_rating_from_threat_data_above}},
                        "control_rating": 1.92,
                        "residual_risk_value": {{risk_rating - control_rating}},
                        "residual_risk_classification": "MEDIUM",
                        "calculation": "Risk Evaluation Rating {{risk_rating}} - Control Rating 1.92 = {{result}}",
                        "formula": "risk_evaluation_rating - control_rating"
                    }},
                    "control_gaps": [
                        {{
                            "gap_description": "Multi-Factor Authentication missing",
                            "evidence": "User indicated: 'Username/Password only - No MFA'",
                            "impact": "Increases unauthorized access probability",
                            "severity": "HIGH"
                        }}
                    ],
                    "recommended_controls": [
                        {{
                            "control_id": "AC-3",
                            "control_name": "Implement MFA for all database users",
                            "control_type": "Preventive",
                            "priority": "HIGH",
                            "rationale": "Addresses critical gap - 50+ users without MFA accessing Highly Confidential data",
                            "expected_effectiveness": 4
                        }}
                    ]
                }}
            ],
            "summary": {{
                "total_threats_evaluated": 1,
                "total_controls_identified": 10,
                "average_control_rating": 1.92,
                "high_residual_risks": 0
            }}
        }}
        
        ═══════════════════════════════════════════════════════════════════════════════
        CRITICAL REQUIREMENTS
        ═══════════════════════════════════════════════════════════════════════════════
        
        ✅ DO:
        1. Use Search Knowledge Base tool to discover control framework
        2. Use questionnaire answers to identify existing controls
        3. Map controls to threats based on DIRECT RELEVANCE (don't apply all controls to all threats!)
        4. Rate controls based on discovered scale
        5. Calculate weighted control rating: (P×1.0 + D×0.75 + C×0.5) / 3
        6. Use ACTUAL risk_rating from Agent 2 threat data
        7. Calculate residual risk: risk_rating - control_rating (FIXED FORMULA!)
        8. Identify gaps from questionnaire
        9. Recommend controls for gaps only
        10. Return valid JSON only
        
        ❌ DON'T:
        1. Hardcode risk ratings (use actual values from threat data!)
        2. Use wrong residual formula (no × 0.5 factor!)
        3. Use risk_value (25) in residual calculation (use risk_rating!)
        4. Assume controls exist without questionnaire evidence
        5. Recommend controls user said already exist
        6. Apply ALL controls to ALL threats (map controls based on relevance!)
        7. Include controls that don't directly mitigate the specific threat
        8. Return text outside JSON structure
        
        ═══════════════════════════════════════════════════════════════════════════════
        REMEMBER: FIXED FORMULAS
        ═══════════════════════════════════════════════════════════════════════════════
        
        1. risk_evaluation_rating = {{actual value from Agent 2 threat data}}
        2. residual_risk_value = risk_rating - control_rating
        3. Example: 5 - 1.92 = 3.08 ✅
        
        Return ONLY the JSON object!
        """,
        expected_output="""RETURN ONLY VALID JSON - NO EXPLANATORY TEXT!
        
        You MUST return ONLY the JSON object starting with { and ending with }.
        DO NOT include any explanatory text before or after the JSON.
        DO NOT include markdown code blocks.
        DO NOT include any commentary.
        
        Just return the pure JSON object with the complete control evaluation structure.
        """,
        agent=agent
    )
    
    return task


def run_control_discovery(api_key: str,
                          asset_data: Dict[str, Any],
                          impact_results: Dict[str, Any],
                          risk_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run Control Discovery & Evaluation with FIXED risk rating and residual formula
    """
    
    print("=" * 80)
    print("🔒 CONTROL EVALUATION - FIXED VERSION")
    print("   ✅ Fixed: Gets correct risk rating from Agent 2")
    print("   ✅ Fixed: Uses correct residual formula (risk_rating - control_rating)")
    print("=" * 80)
    
    agent = create_control_discovery_agent(api_key)
    task = create_control_discovery_task(agent, asset_data, impact_results, risk_results)
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
        memory=False
    )
    
    result = crew.kickoff()
    
    print("\n" + "=" * 80)
    print("✅ CONTROL EVALUATION COMPLETE WITH FIXES")
    print("=" * 80)
    
    try:
        result_text = str(result)
        
        # Clean up markdown formatting
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
        
        result_json = json.loads(result_text)
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # POST-PROCESS: AUTO-GENERATE control_gaps FROM LOW-RATED CONTROLS
        # ═══════════════════════════════════════════════════════════════════════════════
        if 'threat_control_evaluation' in result_json:
            for threat_eval in result_json['threat_control_evaluation']:
                # Check if control_gaps already exists and is populated
                if not threat_eval.get('control_gaps'):
                    # Auto-generate gaps from low-rated controls (rating 1-2)
                    control_gaps = []
                    
                    for ctrl in threat_eval.get('controls_identified', []):
                        rating = ctrl.get('current_rating', 5)
                        
                        # Controls rated 1-2 are WEAK/DEFICIENT = GAPS!
                        if rating <= 2:
                            gap = {
                                'gap_description': f"{ctrl.get('control_name', 'Control')} is weak/deficient (rated {rating}/5)",
                                'control_id': ctrl.get('control_id', 'N/A'),
                                'current_rating': rating,
                                'evidence': ctrl.get('rating_justification', 'Low effectiveness rating'),
                                'impact': f"Insufficient protection - control effectiveness only {rating}/5",
                                'severity': 'HIGH' if rating == 1 else 'MEDIUM'
                            }
                            control_gaps.append(gap)
                    
                    # Add to threat evaluation
                    threat_eval['control_gaps'] = control_gaps
                    
                    print(f"\n🔧 AUTO-GENERATED {len(control_gaps)} control gaps from low-rated controls")
        
        # Print summary
        if 'threat_control_evaluation' in result_json and result_json['threat_control_evaluation']:
            eval_data = result_json['threat_control_evaluation'][0]
            
            controls_count = len(eval_data.get('controls_identified', []))
            control_rating = eval_data.get('control_rating_calculation', {}).get('control_rating', 'N/A')
            risk_rating = eval_data.get('risk_evaluation_rating', 'N/A')
            residual = eval_data.get('residual_risk', {})
            residual_value = residual.get('residual_risk_value', 'N/A')
            
            print(f"\n✅ Controls Found: {controls_count}")
            print(f"✅ Control Rating: {control_rating}")
            print(f"✅ Risk Rating (from Agent 2): {risk_rating}")
            print(f"✅ Residual Risk Value: {residual_value}")
            print(f"   Formula: {risk_rating} - {control_rating} = {residual_value}")
        
        return result_json
        
    except json.JSONDecodeError as e:
        print(f"\n⚠️  JSON parsing failed: {e}")
        return {
            "error": "JSON parsing failed",
            "raw_output": str(result)[:500]
        }
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    print("Agent 3 Control Discovery & Evaluation - FIXED VERSION")
    print("✅ Correctly receives risk rating from Agent 2")
    print("✅ Uses correct residual risk formula")