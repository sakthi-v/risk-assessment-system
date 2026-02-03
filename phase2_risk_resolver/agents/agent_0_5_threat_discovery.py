"""
Agent 0.5: Intelligent Threat & Vulnerability Discovery Agent
- Analyzes questionnaire answers to identify security gaps
- Uses Threat Vocabulary Database as reference (not rigid checklist)
- Creates contextual, specific threat descriptions
- Generates intelligent risk statements
- Discovers threats from RAG knowledge base
"""
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import json
from typing import Dict, Any
import os

from ..tools.rag_tool import search_knowledge_base_function


@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base"""
    return search_knowledge_base_function(query)


def create_threat_discovery_agent(api_key: str) -> Agent:
    """Create Intelligent Threat Discovery Agent"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.3  # Slightly higher for creative threat descriptions
    )
    
    agent = Agent(
        role="Senior Threat Intelligence & Risk Analyst",
        goal="Intelligently discover and articulate specific, contextual threats and vulnerabilities by analyzing asset characteristics and security gaps",
        backstory="""You are a senior cybersecurity and risk analyst with 20+ years of experience in threat intelligence, vulnerability assessment, and risk analysis.

Your expertise includes:
- Identifying realistic threat scenarios based on asset characteristics
- Understanding how security gaps create exploitable vulnerabilities
- Articulating threats in business context (not just technical jargon)
- Creating specific, actionable risk statements
- Connecting multiple weaknesses to identify compound risks

Your approach is INTELLIGENT and CONTEXTUAL:
1. You analyze questionnaire answers to understand the asset deeply
2. You identify security gaps, weaknesses, and missing controls
3. You use Threat Vocabulary Database as reference (not rigid checklist)
4. You create SPECIFIC threat descriptions using actual asset details
5. You generate proper risk statements for risk register

You DON'T just copy predefined threats - you THINK about what could realistically happen to THIS specific asset given its characteristics and gaps.""",
        tools=[search_knowledge_base],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return agent


def create_threat_discovery_task(agent: Agent, asset_data: Dict[str, Any]) -> Task:
    """Create intelligent threat discovery task"""
    
    # Extract questionnaire answers
    questionnaire_answers = asset_data.get('questionnaire_answers', {})
    
    # Build context from answers
    answers_context = "\n═══════════════════════════════════════════════════════════════════════════════\n"
    answers_context += "QUESTIONNAIRE ANSWERS - ANALYZE THESE TO DISCOVER THREATS\n"
    answers_context += "═══════════════════════════════════════════════════════════════════════════════\n\n"
    
    if questionnaire_answers:
        answers_context += "Asset owner provided these FACTS:\n\n"
        
        for q_id, q_data in questionnaire_answers.items():
            if isinstance(q_data, dict):
                question = q_data.get('question_text', q_id)
                answer = q_data.get('answer', 'No answer')
                section = q_data.get('section', '')
                
                answers_context += f"[{section}] Q: {question}\n"
                answers_context += f"Answer: {answer}\n\n"
    else:
        answers_context += "No questionnaire answers available.\n"
    
    # Basic asset info
    basic_asset_info = {
        'asset_name': asset_data.get('asset_name'),
        'asset_type': asset_data.get('asset_type'),
        'asset_owner': asset_data.get('asset_owner'),
        'location': asset_data.get('location'),
        'description': asset_data.get('description')
    }
    
    task = Task(
        description=f"""
YOU MUST RETURN ONLY VALID JSON. NO MARKDOWN, NO TABLES, NO EXPLANATORY TEXT.

BASIC ASSET INFORMATION:
{json.dumps(basic_asset_info, indent=2)}

{answers_context}

═══════════════════════════════════════════════════════════════════════════════
YOUR MISSION - INTELLIGENT THREAT DISCOVERY
═══════════════════════════════════════════════════════════════════════════════

You will intelligently discover threats and vulnerabilities by:
1. Analyzing questionnaire answers to understand asset characteristics
2. Identifying security gaps, weaknesses, and missing controls
3. Using Threat Vocabulary Database as reference vocabulary
4. Creating SPECIFIC, CONTEXTUAL threat descriptions
5. Generating proper risk statements for risk register

═══════════════════════════════════════════════════════════════════════════════
PHASE 1: DISCOVER THREAT VOCABULARY DATABASE
═══════════════════════════════════════════════════════════════════════════════

Query 1: "What is the Threat Vulnerability Database? What threats are documented?"

Search for the organizational threat database/library. You're looking for:
- List of threat categories (e.g., Electronic Sabotage, Physical Theft, etc.)
- Associated vulnerabilities for each threat
- Threat descriptions

This is your REFERENCE VOCABULARY - not a rigid checklist!

Query 2: "What are common vulnerabilities and security weaknesses documented?"

Search for vulnerability lists, security weaknesses, control gaps.

═══════════════════════════════════════════════════════════════════════════════
PHASE 2: ANALYZE QUESTIONNAIRE ANSWERS
═══════════════════════════════════════════════════════════════════════════════

Carefully analyze ALL questionnaire answers to identify:

SECURITY GAPS (Missing Controls):
- No MFA? → Authentication weakness
- No encryption? → Data exposure risk
- No backups? → Data loss risk
- No monitoring? → Detection gap
- No patching? → Vulnerability exploitation risk

ASSET CHARACTERISTICS (Risk Amplifiers):
- Stores PII/PHI/financial data? → High-value target
- Internet-facing? → Increased exposure
- Many users? → Larger attack surface
- Business critical? → High impact if compromised
- Shared facility? → Physical security risk

EXISTING CONTROLS (Risk Reducers):
- MFA enabled? → Reduces unauthorized access
- Encryption in place? → Reduces data exposure
- Regular backups? → Reduces data loss impact
- Monitoring active? → Improves detection

═══════════════════════════════════════════════════════════════════════════════
PHASE 3: INTELLIGENT THREAT IDENTIFICATION
═══════════════════════════════════════════════════════════════════════════════

For EACH significant security gap or risk factor you identified:

1. THINK: What could realistically happen?
   - What threat actors could exploit this?
   - What attack vectors are possible?
   - What's the realistic threat scenario?

2. REFERENCE: Check Threat Vocabulary Database
   - Does this match a documented threat category?
   - What vulnerabilities are associated?
   - Use the vocabulary as reference

3. CREATE CONTEXTUAL DESCRIPTION:
   - Use SPECIFIC details from questionnaire answers
   - Include actual numbers, data types, configurations
   - Explain the realistic threat scenario
   - Connect multiple gaps if they compound the risk

EXAMPLES OF GOOD CONTEXTUAL DESCRIPTIONS:

❌ BAD (Generic):
"Security risk to database"

✅ GOOD (Contextual):
"Ransomware attack targeting the internet-facing customer database containing 50,000 PII records. Without MFA protection and with weekly-only backups, attackers could encrypt the database and demand ransom, causing data unavailability for up to 7 days and potential permanent data loss if backups are also compromised."

❌ BAD (Generic):
"Physical theft risk"

✅ GOOD (Contextual):
"Physical theft of employee laptop containing unencrypted financial reports from shared office building with basic lock-only access control. Lack of full-disk encryption means stolen device could expose Q4 financial data, customer contracts, and employee PII to unauthorized parties."

═══════════════════════════════════════════════════════════════════════════════
PHASE 4: CREATE RISK STATEMENTS
═══════════════════════════════════════════════════════════════════════════════

For each threat, create a proper risk statement:

Format: "Risk of [THREAT EVENT] to [ASSET] due to [VULNERABILITY/GAP], 
         potentially causing [IMPACT]"

Examples:

"Risk of ransomware attack on customer PII database due to lack of MFA and inadequate backup frequency, potentially causing data unavailability, regulatory penalties, and reputational damage"

"Risk of unauthorized data breach exposing 50,000 customer records due to missing encryption at rest and weak authentication controls, potentially causing GDPR violations and customer trust loss"

"Risk of physical theft of manufacturing robot control system from shared facility due to inadequate access controls, potentially causing production line shutdown and safety hazards"

═══════════════════════════════════════════════════════════════════════════════
PHASE 5: DISCOVER ADDITIONAL THREATS FROM RAG
═══════════════════════════════════════════════════════════════════════════════

Query 3: "What are common security threats and risks for [asset_type]?"

Search for asset-type-specific threats that may not be in the Threat Vocabulary Database.

Query 4: "What are industry-specific threats for [relevant industry/domain]?"

If the asset relates to specific industries (healthcare, finance, manufacturing), search for those threats.

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT (RETURN ONLY THIS JSON)
═══════════════════════════════════════════════════════════════════════════════

{{
  "analysis_summary": {{
    "asset_understanding": "Your understanding of this asset and its context",
    "key_security_gaps": ["List of significant security gaps identified"],
    "key_risk_amplifiers": ["Asset characteristics that increase risk"],
    "existing_controls": ["Controls that are in place"],
    "threat_vocabulary_discovered": ["Threat categories found in database"],
    "searches_performed": ["List all RAG searches you made"]
  }},
  
  "threats_discovered": [
    {{
      "threat_id": "T1",
      "threat_category": "Category from Threat Vocabulary Database (if applicable)",
      "threat_name": "Specific, descriptive threat name",
      "contextual_description": "DETAILED description using SPECIFIC details from questionnaire answers. Include numbers, data types, configurations. Explain realistic threat scenario. 3-5 sentences minimum.",
      "vulnerabilities_identified": [
        "Specific vulnerability 1 with context",
        "Specific vulnerability 2 with context",
        "Specific vulnerability 3 with context"
      ],
      "evidence_from_questionnaire": [
        "Q_ID: Question text → Answer that reveals this vulnerability",
        "Q_ID: Question text → Answer that reveals this vulnerability"
      ],
      "risk_statement": "Proper risk statement: Risk of [event] to [asset] due to [vulnerability], potentially causing [impact]",
      "threat_source": "Threat Vocabulary Database | RAG Discovery | Intelligent Analysis"
    }}
  ]
}}

═══════════════════════════════════════════════════════════════════════════════
CRITICAL REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

✅ DO:
1. Analyze ALL questionnaire answers thoroughly
2. Identify 3-7 significant threats (not all 19 from database!)
3. Create SPECIFIC, CONTEXTUAL descriptions using actual details
4. Use numbers, data types, configurations from answers
5. Explain realistic threat scenarios
6. Connect multiple gaps to show compound risks
7. Generate proper risk statements
8. Use Threat Vocabulary Database as reference vocabulary
9. Discover additional threats from RAG if relevant
10. Show evidence from questionnaire for each threat

❌ DON'T:
1. Copy generic threat descriptions
2. List all 19 threats from database without analysis
3. Create threats without evidence from questionnaire
4. Use vague descriptions like "security risk to asset"
5. Ignore questionnaire answers
6. Assume threats without analyzing gaps
7. Create threats that don't match asset characteristics

═══════════════════════════════════════════════════════════════════════════════
EXAMPLE WORKFLOW
═══════════════════════════════════════════════════════════════════════════════

1. Read answers: "Stores 50,000 PII records, No MFA, No encryption, Internet-facing"

2. Identify gaps: Missing MFA, Missing encryption, High exposure

3. Reference Threat DB: "Electronic Sabotage", "Inappropriate Information Disclosure"

4. Create contextual threat:
   "Ransomware attack on internet-facing customer database containing 50,000 
   unencrypted PII records. Without MFA, attackers could compromise credentials 
   and encrypt the database, causing data unavailability and potential GDPR 
   violations affecting 50,000 customers."

5. Create risk statement:
   "Risk of ransomware attack on customer PII database due to lack of MFA and 
   encryption, potentially causing data breach, regulatory penalties, and 
   reputational damage"

6. Return JSON with 3-7 intelligent, contextual threats

═══════════════════════════════════════════════════════════════════════════════
REMEMBER
═══════════════════════════════════════════════════════════════════════════════

You are an INTELLIGENT ANALYST, not a template filler!

- THINK about what could realistically happen to THIS asset
- USE specific details from questionnaire answers
- CREATE contextual descriptions, not generic ones
- REFERENCE Threat Vocabulary Database, don't just copy it
- DISCOVER additional threats from RAG if relevant
- GENERATE proper risk statements for risk register

Return ONLY the JSON object!
""",
        expected_output="Intelligent threat discovery with contextual descriptions and risk statements",
        agent=agent
    )
    
    return task


def run_threat_discovery(
    api_key: str,
    asset_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run Intelligent Threat Discovery
    
    Args:
        api_key: Gemini API key
        asset_data: Asset data with questionnaire answers
    
    Returns:
        dict: Discovered threats with contextual descriptions
    """
    
    print("=" * 80)
    print("🔍 INTELLIGENT THREAT & VULNERABILITY DISCOVERY")
    print("   ✅ Analyzes questionnaire answers")
    print("   ✅ Identifies security gaps and weaknesses")
    print("   ✅ Creates contextual threat descriptions")
    print("   ✅ Generates intelligent risk statements")
    print("   🚫 NOT just copying predefined threats!")
    print("=" * 80)
    
    agent = create_threat_discovery_agent(api_key)
    task = create_threat_discovery_task(agent, asset_data)
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
        memory=False
    )
    
    print("\n🔍 Agent is performing intelligent threat discovery...")
    print("   1. Discovering Threat Vocabulary Database")
    print("   2. Analyzing questionnaire answers")
    print("   3. Identifying security gaps")
    print("   4. Creating contextual threat descriptions")
    print("   5. Generating risk statements")
    print()
    
    result = crew.kickoff()
    
    print("\n" + "=" * 80)
    print("✅ INTELLIGENT THREAT DISCOVERY COMPLETED")
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
        if 'threats_discovered' in result_json:
            threats = result_json['threats_discovered']
            print(f"\n✅ Discovered {len(threats)} intelligent, contextual threats:")
            
            for i, threat in enumerate(threats, 1):
                print(f"\n   Threat {i}: {threat.get('threat_name', 'N/A')}")
                print(f"   Category: {threat.get('threat_category', 'N/A')}")
                print(f"   Risk Statement: {threat.get('risk_statement', 'N/A')[:100]}...")
        
        if 'analysis_summary' in result_json:
            summary = result_json['analysis_summary']
            gaps = summary.get('key_security_gaps', [])
            if gaps:
                print(f"\n🔍 Key Security Gaps Identified:")
                for gap in gaps[:3]:
                    print(f"   - {gap}")
        
        return result_json
        
    except json.JSONDecodeError as e:
        print(f"\n⚠️  JSON parsing failed: {e}")
        return {"error": "JSON parsing failed", "threats_discovered": []}
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        return {"error": str(e), "threats_discovered": []}


if __name__ == "__main__":
    import os
    api_key = os.getenv("GEMINI_API_KEY")
    
    test_asset = {
        'asset_name': 'Customer PII Database',
        'asset_type': 'Database Server',
        'questionnaire_answers': {
            'Q1': {'question_text': 'Does it store PII?', 'answer': 'Yes, 50,000 customer records'},
            'Q2': {'question_text': 'Is MFA enabled?', 'answer': 'No'},
            'Q3': {'question_text': 'Is encryption at rest enabled?', 'answer': 'No'},
            'Q4': {'question_text': 'Is it internet-facing?', 'answer': 'Yes'},
            'Q5': {'question_text': 'Backup frequency?', 'answer': 'Weekly'}
        }
    }
    
    result = run_threat_discovery(api_key, test_asset)
    print("\n✅ Intelligent threat discovery completed!")
    print(f"   Discovered {len(result.get('threats_discovered', []))} contextual threats")
