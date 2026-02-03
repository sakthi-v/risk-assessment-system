"""
Agent 1: FULLY UPDATED - WITH BUSINESS VALUE & CRITICALITY RAG DISCOVERY
- Discovers CIA rating scales from RAG ✅
- Calculates CIA ratings from facts ✅
- Discovers Business Value calculation from RAG ✅ (ENHANCED!)
- Discovers Criticality classification from RAG ✅ (ENHANCED!)
- Applies discovered methodologies to calculate all values ✅
"""
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import json
from typing import Dict, Any
import os

from ..config.agent_definitions import AGENT_1_IMPACT_ASSESSMENT
from ..tools.memory_rag_tool import search_with_memory


@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base with memory caching"""
    return search_with_memory(query)


def create_impact_agent(api_key: str) -> Agent:
    """Create CIA Impact Assessment Agent with full RAG discovery"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.0
    )
    
    agent = Agent(
        role="CIA Impact Assessment Analyst with Full Methodology Discovery",
        goal="Discover and apply CIA methodology, Business Value calculation, and Criticality classification entirely from organizational RAG documents",
        backstory="""You are a senior information security risk analyst who specializes in discovering and applying organizational methodologies from documentation.

Your approach is FULLY RAG-BASED:
1. You search organizational documents to discover methodologies
2. You never assume or hardcode - you always search first
3. You apply discovered methodologies precisely as documented
4. You calculate CIA ratings, Business Value, and Criticality from facts

You understand that organizations have:
- CIA rating scales (you discover the scale)
- CIA definitions (you discover the definitions)
- Business Value matrices (you discover the matrix/formula)
- Criticality classification tables (you discover the mapping)

You are a DISCOVERY EXPERT - you find these in documents and apply them correctly.""",
        tools=[search_knowledge_base],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return agent


def create_impact_task(agent: Agent, asset_data: Dict[str, Any]) -> Task:
    """Create task with full Business Value and Criticality RAG discovery"""
    
    # Extract questionnaire answers
    questionnaire_answers = asset_data.get('questionnaire_answers', {})
    
    # Build questionnaire facts context
    facts_context = "\n═══════════════════════════════════════════════════════════════════════════════\n"
    facts_context += "QUESTIONNAIRE FACTS - ANALYZE THESE TO CALCULATE CIA!\n"
    facts_context += "═══════════════════════════════════════════════════════════════════════════════\n\n"
    
    if questionnaire_answers:
        facts_context += "The asset owner provided these FACTS:\n\n"
        
        for q_id, q_data in questionnaire_answers.items():
            if isinstance(q_data, dict):
                question = q_data.get('question_text', q_id)
                answer = q_data.get('answer', 'No answer')
                section = q_data.get('section', '')
                
                facts_context += f"\n[{section}] Q: {question}\n"
                facts_context += f"Answer: {answer}\n"
        
        facts_context += "\n"
        facts_context += "YOU MUST ANALYZE THESE FACTS TO CALCULATE CIA RATINGS.\n"
    else:
        facts_context += "No questionnaire answers available.\n"
    
    # Basic asset info
    basic_asset_info = {
        'asset_name': asset_data.get('asset_name'),
        'asset_type': asset_data.get('asset_type'),
        'asset_owner': asset_data.get('asset_owner'),
        'location': asset_data.get('location'),
        'description': asset_data.get('description'),
        'threats_and_vulnerabilities': asset_data.get('threats_and_vulnerabilities', [])
    }
    
    task = Task(
        description=f"""
YOU MUST RETURN ONLY VALID JSON. NO MARKDOWN, NO TABLES, NO EXPLANATORY TEXT.

BASIC ASSET INFORMATION:
{json.dumps(basic_asset_info, indent=2)}

{facts_context}

═══════════════════════════════════════════════════════════════════════════════
YOUR COMPLETE MISSION - FULL RAG DISCOVERY
═══════════════════════════════════════════════════════════════════════════════

You will discover ALL methodologies from RAG documents:
1. CIA rating scale and definitions
2. CIA-to-Business-Value calculation matrix/formula
3. Business-Value-to-Criticality classification mapping

Then apply ALL discovered methodologies to calculate:
1. CIA ratings (Confidentiality, Integrity, Availability)
2. Asset Business Value (from CIA ratings)
3. Asset Criticality Classification (from Business Value)

═══════════════════════════════════════════════════════════════════════════════
PHASE 1: DISCOVER CIA METHODOLOGY
═══════════════════════════════════════════════════════════════════════════════

Query 1: "What impact assessment methodology is used? CIA? DREAD? Custom?"

Learn the framework (likely CIA - Confidentiality, Integrity, Availability).

Query 2: "What rating scale is used for CIA impact ratings? What are the levels?"

Discover the scale, examples:
- 4-level: Insignificant, Moderate, Serious, Extreme
- 5-level: Very Low, Low, Medium, High, Very High
- 5-level numeric: 1, 2, 3, 4, 5

Query 3: "What are the definitions for each CIA impact level?"

Get precise definitions for EACH level to help you classify.

═══════════════════════════════════════════════════════════════════════════════
PHASE 2: DISCOVER BUSINESS VALUE CALCULATION (CRITICAL!)
═══════════════════════════════════════════════════════════════════════════════

Query 4: "How is Asset Business Value calculated or determined from 
         CIA impact ratings? Is there a matrix, chart, or formula?"

SEARCH FOR:
- Asset Value Chart
- Asset Business Value Matrix
- CIA combination matrix
- Formula to derive Business Value from C, I, A

Expected to discover something like:
"Once the Business Impact Ratings for the compromise of the C, I and A 
of the asset are determined then the overall Asset Business Value is 
determined by Asset Value Chart..."

The discovered matrix might show:
- Insignificant + Insignificant + Insignificant = Very Low
- Moderate + Moderate + Moderate = Low
- Serious + Serious + Serious = High
- Extreme + Extreme + Extreme = Very High
- ... (various combinations)

Query 5: "What are the Asset Business Value levels? What values can 
         Asset Business Value take?"

Discover the possible values, likely:
- Very Low
- Low
- Medium
- High
- Very High

═══════════════════════════════════════════════════════════════════════════════
PHASE 3: DISCOVER CRITICALITY CLASSIFICATION (CRITICAL!)
═══════════════════════════════════════════════════════════════════════════════

Query 6: "How is Asset Criticality Classification determined from 
         Asset Business Value?"

SEARCH FOR:
- Criticality Classification Table
- Asset Classification guidelines
- Business Value to Criticality mapping

Expected to discover something like:
"Based on the Asset Business Value, classify the assets for criticality 
as per the following table..."

The discovered mapping likely shows:
- Very Low → Insignificant
- Low → Low Critical
- Medium → Medium Critical
- High → High Critical
- Very High → Very High Critical

Query 7: "What are the Asset Criticality Classification levels?"

Discover the possible classifications, likely:
- Insignificant
- Low Critical
- Medium Critical
- High Critical
- Very High Critical

═══════════════════════════════════════════════════════════════════════════════
PHASE 4: CALCULATE CIA RATINGS FROM FACTS
═══════════════════════════════════════════════════════════════════════════════

For EACH threat, analyze questionnaire facts to determine CIA ratings:

CONFIDENTIALITY ANALYSIS:
Look at facts about:
- Data classification
- PII/PHI/PCI/financial data storage
- Number of records
- Encryption (at rest, in transit)
- Access controls (MFA, authentication)
- Regulatory requirements

Apply discovered CIA definitions to assign rating.

INTEGRITY ANALYSIS:
Look at facts about:
- Data criticality for business decisions
- Change control processes
- Data validation mechanisms
- Audit logging
- Access controls
- Business process dependencies

Apply discovered CIA definitions to assign rating.

AVAILABILITY ANALYSIS:
Look at facts about:
- Business criticality
- Backup status and frequency
- Redundancy/failover mechanisms
- Disaster recovery plan
- Number of users/dependencies
- Recovery time objectives

Apply discovered CIA definitions to assign rating.

═══════════════════════════════════════════════════════════════════════════════
PHASE 5: CALCULATE ASSET-LEVEL CIA (OVERALL FOR ASSET)
═══════════════════════════════════════════════════════════════════════════════

IMPORTANT: You must calculate TWO types of CIA assessments:

1. THREAT-LEVEL CIA (Per-Threat Risk Impact) - Already done in Phase 4
   - Each threat gets its own C, I, A ratings
   - This represents the Risk Impact for that specific threat scenario
   - Used for Risk Assessment (Risk = Impact × Probability)

2. ASSET-LEVEL CIA (Overall Asset Assessment) - Calculate now:
   - Find MAXIMUM CIA value across ALL threats for the asset
   - Example: If Threat 1 has C=Extreme(5), I=Extreme(5), A=Serious(4)
              And Threat 2 has C=Serious(4), I=Moderate(3), A=Extreme(5)
              Then Asset-level CIA = C=Extreme(5), I=Extreme(5), A=Extreme(5)
   - This represents WORST-CASE scenario for the asset (ISO 27005 approach)
   - Used for Asset Business Value and Criticality Classification

═══════════════════════════════════════════════════════════════════════════════
PHASE 6: CALCULATE BUSINESS VALUE FROM ASSET-LEVEL CIA
═══════════════════════════════════════════════════════════════════════════════

Use ASSET-LEVEL CIA (from Phase 5) to calculate Business Value:

Using the discovered Asset Value Chart/Matrix from Phase 2:

1. Take your calculated ASSET-LEVEL CIA ratings (maximum across threats):
   Example: Confidentiality = Extreme, Integrity = Extreme, Availability = Extreme

2. Look up this combination in the discovered matrix:
   Example: Extreme + Extreme + Extreme = Very High

3. Assign the Business Value:
   Asset Business Value = Very High

CRITICAL NOTES:
- Use the EXACT matrix/formula discovered from RAG
- Do NOT assume or hardcode the matrix
- Reference the discovered chart in your reasoning
- If multiple combinations possible, use the one from the chart
- Business Value is calculated from ASSET-LEVEL CIA (maximum), not individual threat CIA

═══════════════════════════════════════════════════════════════════════════════
PHASE 7: CALCULATE CRITICALITY FROM BUSINESS VALUE
═══════════════════════════════════════════════════════════════════════════════

Using the discovered Criticality Classification Table from Phase 3:

1. Take your calculated Business Value:
   Example: Business Value = Very High

2. Look up this value in the discovered mapping:
   Example: Very High → Very High Critical

3. Assign the Criticality:
   Asset Criticality Classification = Very High Critical

CRITICAL NOTES:
- Use the EXACT mapping discovered from RAG
- Do NOT assume or hardcode the mapping
- Reference the discovered table in your reasoning

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT (RETURN ONLY THIS JSON)
═══════════════════════════════════════════════════════════════════════════════

{{
  "discovery_summary": {{
    "cia_methodology": "CIA (Confidentiality, Integrity, Availability)",
    "cia_rating_scale": "4-level: Insignificant, Moderate, Serious, Extreme (discovered scale)",
    "cia_definitions_source": "Asset Management Guidelines (or discovered source)",
    "business_value_calculation_method": "Asset Value Chart/Matrix (discovered method)",
    "business_value_levels": ["Very Low", "Low", "Medium", "High", "Very High"],
    "business_value_source": "Asset Management Guidelines - Asset Value Chart",
    "criticality_classification_method": "Business Value to Criticality Mapping (discovered method)",
    "criticality_levels": ["Insignificant", "Low Critical", "Medium Critical", "High Critical", "Very High Critical"],
    "criticality_source": "Asset Inventorization Guideline - Criticality Classification Table",
    "searches_performed": ["List all RAG searches you made"]
  }},
  
  "threat_analysis": [
    {{
      "threat_id": "threat_1",
      "threat_name": "Name from asset data",
      "threat_description": "Description from asset data",
      
      "impact_assessment": {{
        "confidentiality": {{
          "rating": "Extreme|Serious|Moderate|Insignificant (discovered scale)",
          "numeric_value": 5,
          "reasoning": "DETAILED: Based on questionnaire answer [cite specific answer] stating [specific fact], 
                       and answer [cite another] indicating [another fact], unauthorized disclosure would [impact]. 
                       This meets the discovered definition for 'Extreme': [cite discovered definition]."
        }},
        "integrity": {{
          "rating": "Extreme|Serious|Moderate|Insignificant",
          "numeric_value": 5,
          "reasoning": "DETAILED: Based on facts about [cite facts], unauthorized modification would [impact]."
        }},
        "availability": {{
          "rating": "Extreme|Serious|Moderate|Insignificant",
          "numeric_value": 5,
          "reasoning": "DETAILED: Based on facts about [cite facts], unavailability would [impact]."
        }}
      }},
      
      "overall_impact_calculation": {{
        "confidentiality_numeric": 5,
        "integrity_numeric": 5,
        "availability_numeric": 5,
        "calculation_method": "max(C, I, A) or discovered method",
        "calculation": "max(5, 5, 5) = 5",
        "overall_impact": "5 - Very High",
        "overall_impact_numeric": 5
      }}
    }}
  ],
  
  "asset_cia_ratings": {{
    "confidentiality": {{
      "rating": "Extreme (maximum across all threats)",
      "numeric_value": 5,
      "reasoning": "Asset-level CIA: Maximum C value across all threats. Threat 1: Extreme(5), Threat 2: Serious(4), Threat 3: Moderate(3) → Asset C = Extreme(5)",
      "threat_breakdown": ["Threat 1: Extreme(5)", "Threat 2: Serious(4)", "Threat 3: Moderate(3)"]
    }},
    "integrity": {{
      "rating": "Extreme (maximum across all threats)",
      "numeric_value": 5,
      "reasoning": "Asset-level CIA: Maximum I value across all threats. Threat 1: Extreme(5), Threat 2: Extreme(5), Threat 3: Serious(4) → Asset I = Extreme(5)",
      "threat_breakdown": ["Threat 1: Extreme(5)", "Threat 2: Extreme(5)", "Threat 3: Serious(4)"]
    }},
    "availability": {{
      "rating": "Extreme (maximum across all threats)",
      "numeric_value": 5,
      "reasoning": "Asset-level CIA: Maximum A value across all threats. Threat 1: Extreme(5), Threat 2: Extreme(5), Threat 3: Serious(4) → Asset A = Extreme(5)",
      "threat_breakdown": ["Threat 1: Extreme(5)", "Threat 2: Extreme(5)", "Threat 3: Serious(4)"]
    }},
    "calculation_note": "Asset-level CIA is calculated as MAXIMUM across all threat-level CIA ratings. This represents the worst-case impact scenario for the asset and is used for Asset Business Value and Criticality Classification per organizational Asset Management Guidelines."
  }},
  
  "asset_business_value": {{
    "cia_combination": "Extreme, Extreme, Extreme (from calculated CIA)",
    "cia_combination_key": "Extreme|Extreme|Extreme",
    "business_value_rating": "Very High (from discovered Asset Value Chart)",
    "business_value_numeric": 5,
    "calculation_method": "Asset Value Chart (discovered from Asset Management Guidelines)",
    "calculation_details": "Per discovered Asset Value Chart: CIA combination (Extreme, Extreme, Extreme) maps to Business Value 'Very High'",
    "source_reference": "Asset Management Guidelines - Asset Value Chart",
    "reasoning": "Based on calculated CIA ratings (Confidentiality: Extreme, Integrity: Extreme, Availability: Extreme), 
                 per the discovered Asset Value Chart in organizational guidelines, the Asset Business Value is 'Very High'."
  }},
  
  "asset_criticality": {{
    "criticality_classification": "Very High Critical (from discovered Criticality Table)",
    "business_value_input": "Very High",
    "calculation_method": "Criticality Classification Table (discovered from Asset Inventorization Guideline)",
    "calculation_details": "Per discovered Criticality Classification Table: Business Value 'Very High' maps to Criticality 'Very High Critical'",
    "source_reference": "Asset Inventorization Guideline - Criticality Classification Table",
    "reasoning": "Based on calculated Asset Business Value 'Very High', per the discovered Criticality Classification Table 
                 in organizational Asset Inventorization Guideline, the Asset Criticality Classification is 'Very High Critical'."
  }}
}}

═══════════════════════════════════════════════════════════════════════════════
CRITICAL REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

✅ DO:
1. Search RAG for CIA scale, definitions
2. Search RAG for Business Value calculation method/matrix
3. Search RAG for Criticality classification mapping
4. Calculate CIA ratings from questionnaire facts
5. Calculate Business Value from CIA using discovered matrix
6. Calculate Criticality from Business Value using discovered mapping
7. Provide detailed reasoning citing facts and discovered methodologies
8. Return numeric overall_impact_numeric for risk formula
9. Include source references for all discovered methodologies

❌ DON'T:
1. Hardcode any matrices or mappings
2. Assume Business Value without discovering how to calculate it
3. Assume Criticality without discovering the mapping
4. Use CIA ratings from questionnaire (calculate them yourself!)
5. Return N/A for any calculated values

═══════════════════════════════════════════════════════════════════════════════
EXAMPLE WORKFLOW
═══════════════════════════════════════════════════════════════════════════════

1. Search: "CIA rating scale?" → Discover: "4-level: Insignificant, Moderate, Serious, Extreme"

2. Analyze facts → Calculate: C=Extreme, I=Extreme, A=Extreme

3. Search: "How to calculate Business Value from CIA?" → Discover: "Asset Value Chart shows..."

4. Apply discovered chart: Extreme+Extreme+Extreme → Business Value = "Very High"

5. Search: "How to classify Criticality?" → Discover: "Criticality Table shows..."

6. Apply discovered table: Very High → Criticality = "Very High Critical"

7. Return complete JSON with all calculated values and source references

═══════════════════════════════════════════════════════════════════════════════
REMEMBER
═══════════════════════════════════════════════════════════════════════════════

You are a RAG DISCOVERY EXPERT. You discover ALL methodologies from documents:
- CIA scales ✅
- CIA definitions ✅
- Business Value calculation ✅ (via RAG, not hardcoded!)
- Criticality classification ✅ (via RAG, not hardcoded!)

Then you apply ALL discovered methodologies to calculate everything!

Return ONLY the JSON object!
""",
        expected_output="Complete CIA assessment with Business Value and Criticality calculated from discovered RAG methodologies",
        agent=agent
    )
    
    return task


def run_impact_assessment(
    api_key: str,
    asset_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run CIA Impact Assessment with full Business Value and Criticality RAG discovery
    """
    
    print("=" * 80)
    print("🎯 CIA IMPACT ASSESSMENT - FULL RAG DISCOVERY")
    print("   ✅ Discovers CIA scales from RAG")
    print("   ✅ Calculates CIA ratings from facts")
    print("   ✅ Discovers Business Value calculation from RAG")
    print("   ✅ Calculates Business Value from CIA")
    print("   ✅ Discovers Criticality classification from RAG")
    print("   ✅ Calculates Criticality from Business Value")
    print("   🚫 NO HARDCODING - Everything discovered from documents!")
    print("=" * 80)
    
    agent = create_impact_agent(api_key)
    task = create_impact_task(agent, asset_data)
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
        memory=False
    )
    
    print("\n🎯 Agent is performing FULL RAG discovery...")
    print("   1. Discovering CIA methodology")
    print("   2. Calculating CIA from facts")
    print("   3. Discovering Business Value calculation")
    print("   4. Calculating Business Value")
    print("   5. Discovering Criticality classification")
    print("   6. Calculating Criticality")
    print()
    
    result = crew.kickoff()
    
    print("\n" + "=" * 80)
    print("✅ COMPLETE CIA ASSESSMENT WITH BUSINESS VALUE & CRITICALITY")
    print("=" * 80)
    
    try:
        result_text = str(result)
        
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            parts = result_text.split("```")
            if len(parts) >= 2:
                result_text = parts[1].strip()
        
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            result_text = result_text[start_idx:end_idx]
        
        result_json = json.loads(result_text)
        
        # Print summary
        if 'threat_analysis' in result_json and result_json['threat_analysis']:
            first_threat = result_json['threat_analysis'][0]
            impact = first_threat.get('impact_assessment', {})
            
            print(f"\n✅ CIA Ratings (CALCULATED):")
            print(f"   Confidentiality: {impact.get('confidentiality', {}).get('rating', 'N/A')}")
            print(f"   Integrity: {impact.get('integrity', {}).get('rating', 'N/A')}")
            print(f"   Availability: {impact.get('availability', {}).get('rating', 'N/A')}")
            
            overall = first_threat.get('overall_impact_calculation', {})
            print(f"\n✅ Overall Impact: {overall.get('overall_impact_numeric', 'N/A')}")
        
        if 'asset_business_value' in result_json:
            bv = result_json['asset_business_value']
            print(f"\n✅ Asset Business Value: {bv.get('business_value_rating', 'N/A')}")
            print(f"   (Calculated from CIA using discovered {bv.get('calculation_method', 'method')})")
        
        if 'asset_criticality' in result_json:
            crit = result_json['asset_criticality']
            print(f"\n✅ Asset Criticality: {crit.get('criticality_classification', 'N/A')}")
            print(f"   (Calculated from Business Value using discovered {crit.get('calculation_method', 'method')})")
        
        return result_json
        
    except json.JSONDecodeError as e:
        print(f"\n⚠️  JSON parsing failed: {e}")
        return {"error": "JSON parsing failed"}
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    import os
    api_key = os.getenv("GEMINI_API_KEY")
    
    test_asset = {
        'asset_name': 'Test Database',
        'asset_type': 'Database Server',
        'questionnaire_answers': {
            'Q1': {'question_text': 'Does it store PII?', 'answer': 'Yes'},
            'Q2': {'question_text': 'Is MFA enabled?', 'answer': 'No'},
            'Q3': {'question_text': 'Are backups performed?', 'answer': 'No'}
        }
    }
    
    result = run_impact_assessment(api_key, test_asset)
    print("\n✅ Agent discovered and applied all methodologies from RAG!")
    print("   - CIA scales ✅")
    print("   - Business Value calculation ✅")
    print("   - Criticality classification ✅")