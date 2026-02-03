"""
Agent 0: PURE AGENTIC Intelligence - FULLY CORRECTED VERSION
- NO CIA impact questions (Agent 1's job!)
- Asks ONLY for FACTS about the asset
- Asks ONLY for OVERALL OPINIONS (not detailed CIA ratings)
- Pure intelligence - handles ANY asset type user enters
"""
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import json
from typing import Dict, Any, Optional
import os

from ..config.agent_definitions import AGENT_0_QUESTIONNAIRE
from ..tools.rag_tool import search_knowledge_base_function


@tool("Search Knowledge Base")
def search_knowledge_base(query: str) -> str:
    """Search organizational knowledge base"""
    return search_knowledge_base_function(query)


def create_intelligent_agent(api_key: str) -> Agent:
    """Create Pure Intelligence Agent"""
    
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    
    llm = LLM(
        model="gemini/gemini-3-flash-preview",
        api_key=api_key,
        temperature=0.0
    )
    
    agent = Agent(
        role="Expert Risk Assessment Consultant - Data Collector",
        goal="Generate intelligent questionnaires that collect FACTS about assets and OVERALL OPINIONS from asset owners, without asking them to perform technical risk analysis",
        backstory="""You are a senior risk assessment consultant with 25+ years of experience.

Your role is to COLLECT INFORMATION, not to perform analysis.

You understand that:
1. Asset owners know the FACTS about their assets (what exists, what's configured, what's in place)
2. Asset owners can give OVERALL OPINIONS (how critical, how severe if lost)
3. Asset owners should NOT be asked to perform technical analysis (CIA ratings, control effectiveness, etc.)

Your questionnaires collect the RIGHT information so that RISK ANALYSTS can perform the analysis.

You are like a skilled interviewer:
- You ask the right questions to reveal risk factors
- You collect facts systematically
- You gather the owner's perspective
- You DON'T ask owners to do the analyst's job

When someone needs to assess a "Database Server" or "Manufacturing Robot" or ANY asset type:
1. You figure out what FACTS matter for risk (data stored, controls in place, dependencies)
2. You ask for those FACTS (not for risk ratings!)
3. You ask for OVERALL OPINION (overall impact/likelihood, not CIA breakdown)
4. You let the risk analysts do the CIA analysis later""",
        tools=[search_knowledge_base],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return agent


def create_pure_intelligence_task(agent: Agent, asset_type: Optional[str] = None) -> Task:
    """
    Create task that collects FACTS and OVERALL OPINIONS only
    Does NOT ask for CIA ratings or technical analysis
    """
    
    asset_context = f'for "{asset_type}"' if asset_type else "for risk assessment"
    
    task = Task(
        description=f"""
You are creating a risk assessment questionnaire {asset_context}.

═══════════════════════════════════════════════════════════════════════════════
YOUR MISSION
═══════════════════════════════════════════════════════════════════════════════

Create a questionnaire that collects:
1. FACTS about the asset (what exists, what's configured, what's in place)
2. OVERALL OPINIONS from the asset owner (overall criticality, overall impact, overall likelihood)

DO NOT ask for:
❌ CIA impact ratings (Confidentiality, Integrity, Availability) - Agent 1 will calculate these!
❌ Control effectiveness ratings - Agent 3 will calculate these!
❌ Risk calculations - Agent 2 will calculate these!
❌ Risk acceptability decisions - Agent 4 will decide these!

═══════════════════════════════════════════════════════════════════════════════
CRITICAL UNDERSTANDING - THE WORKFLOW
═══════════════════════════════════════════════════════════════════════════════

YOU (Agent 0):
   Collect FACTS: "Does it store PII? Is MFA enabled? Are backups done?"
   Collect OVERALL OPINION: "Overall, how severe would impact be? How likely?"
   ↓
AGENT 1 (CIA Analyst):
   Analyzes the FACTS you collected
   CALCULATES: Confidentiality = EXTREME, Integrity = EXTREME, Availability = EXTREME
   ↓
AGENT 2 (Risk Quantifier):
   Uses Agent 1's CIA analysis
   CALCULATES: Risk Value, Risk Rating
   ↓
AGENT 3 (Control Evaluator):
   Evaluates controls from FACTS you collected
   CALCULATES: Control effectiveness, Residual risk
   ↓
AGENT 4 (Decision Maker):
   DECIDES: Accept or Treat the risk

Don't ask users to do what Agents 1-4 will calculate!

═══════════════════════════════════════════════════════════════════════════════
YOUR INTELLIGENT APPROACH
═══════════════════════════════════════════════════════════════════════════════

STEP 1: UNDERSTAND THE ASSET TYPE
Think about "{asset_type if asset_type else 'assets in general'}":
- What is this type of asset?
- What FACTS determine if it's risky?
- What controls should exist?

STEP 2: DISCOVER ORGANIZATION'S METHODOLOGY AND ASSET STRUCTURE
Use Search Knowledge Base to learn:

A. ASSET IDENTIFICATION STRUCTURE (CRITICAL - ALWAYS ASK FIRST!):
- Search: "asset inventory structure", "asset identification fields", "asset type categories"
- Find: What fields identify an asset? (Asset Name? Asset Type? Asset ID? Owner? Location?)
- Find: What are the asset type categories? (Physical? Software? Information? Service? People?)
- Find: What other asset classification fields exist?

B. RISK ASSESSMENT METHODOLOGY:
- What rating scales do they use for overall impact/probability?
- What is their risk assessment process?
- What control frameworks do they reference?
- What terminology do they prefer?

STEP 3: GENERATE INTELLIGENT QUESTIONS

**CRITICAL: ALWAYS START WITH ASSET IDENTIFICATION SECTION!**

A. IDENTIFY THE ASSET (DISCOVERED FROM RAG - ALWAYS INCLUDE!)

Based on what you discovered from the knowledge base about asset identification:

1. **Asset Name Question** (REQUIRED - Always ask!):
   - Question ID: Use discovered field name (e.g., Q_ASSET_NAME, Q_ASSET_CLASS_NAME)
   - Question: "What is the specific name/title of this asset?"
   - Type: text
   - Help: Provide examples based on asset type user entered
   - Example: "e.g., Customer PII Database, Production Web Server, HR Laptop Fleet"

2. **Asset Type Question** (REQUIRED - Always ask!):
   - Question ID: Use discovered field name (e.g., Q_ASSET_TYPE, Q_TYPE_OF_ASSET)
   - Question: "What type of asset is this?"
   - Type: dropdown
   - Options: Use the asset type categories you discovered from RAG!
   - If you found categories like "Physical Asset", "Software Asset", "Information Asset", "Service Asset", "People Asset" → use those!
   - If you found different categories → use what you discovered!
   - CRITICAL: DO NOT hardcode categories - use what RAG returned!

3. **Other Asset Identification Fields** (if discovered from RAG):
   - Asset Owner/Asset Class Owner (if found in documents)
   - Location (if found in documents)
   - Asset ID (if found in documents)
   - Any other identification fields discovered from RAG

B. UNDERSTAND THE CONTEXT  
- What is its business criticality? (use discovered scale)
- What business processes depend on it?
- Who uses/accesses it? How many users?
- What is its business value? (use discovered scale)

C. COLLECT FACTS ABOUT RISK FACTORS
Ask FACTUAL questions about things that indicate risk level.

EXAMPLES for Database Server:
✅ GOOD (Facts):
- "What is the data classification of information stored?" (using org's classification scale)
- "Does this database store PII, PHI, or financial data?" (Yes/No/Type)
- "How many administrators have access?" (Number)
- "Is multi-factor authentication required?" (Yes/No)
- "Is data encrypted at rest?" (Yes/No/Partial)
- "Is data encrypted in transit?" (Yes/No/TLS version)
- "Are regular backups performed?" (Yes/No/Frequency)
- "Is the database accessible from the internet?" (Yes/No/Partially)
- "How many users access this database?" (Number/Range)
- "What applications depend on this database?" (List)

❌ BAD (Analysis - Don't ask!):
- "What is the Confidentiality impact rating?" ← Agent 1 calculates!
- "What is the Integrity impact rating?" ← Agent 1 calculates!
- "What is the Availability impact rating?" ← Agent 1 calculates!
- "Rate the control effectiveness (1-5)" ← Agent 3 calculates!

EXAMPLES for Physical Building:
✅ GOOD (Facts):
- "What is stored in this building?"
- "What physical access controls exist?" (Badge system, Guards, Biometric, None)
- "Is there 24/7 security monitoring?" (Yes/No)
- "Are there surveillance cameras?" (Yes/No/Coverage)
- "What is the building's fire suppression system?" (Sprinklers/Gas/None)

❌ BAD (Analysis - Don't ask!):
- "What is the Availability impact if building is unavailable?" ← Agent 1 calculates!

YOU figure out the right FACTUAL questions for "{asset_type if asset_type else 'this asset'}"!

D. COLLECT FACTS ABOUT EXISTING CONTROLS
Ask FACTUAL yes/no or descriptive questions about controls.

✅ GOOD (Facts about controls):
- "Is multi-factor authentication enabled?" (Yes/No)
- "Are access logs monitored?" (Yes/No/Frequency)
- "Are security patches applied regularly?" (Yes/No/Frequency)
- "Is there a disaster recovery plan?" (Yes/No)
- "Is there an incident response plan?" (Yes/No)

❌ BAD (Control effectiveness ratings - Don't ask!):
- "Rate the effectiveness of MFA (1-5)" ← Agent 3 calculates!
- "Rate the overall control effectiveness" ← Agent 3 calculates!

E. GATHER OVERALL RISK PERSPECTIVE (NOT CIA BREAKDOWN!)
Ask for the asset owner's OVERALL perspective only.
Use discovered rating scales from knowledge base.

✅ GOOD - Ask for OVERALL OPINION:

"Considering all identified risks and existing controls, what is the estimated 
overall 'Impact Rating' if this {asset_type or 'asset'} were to be severely 
compromised (e.g., data breach, prolonged outage, complete loss)?"

Options: Use organization's overall impact scale discovered from knowledge base
(Example: 1=Very Low, 2=Low, 3=Medium, 4=High, 5=Very High)

"Considering all identified threats and vulnerabilities, what is the estimated 
'Probability Rating' of a severe compromise occurring to this {asset_type or 'asset'} 
within the next year?"

Options: Use organization's probability scale discovered from knowledge base
(Example: 1=Very Low/Rare, 2=Low, 3=Medium, 4=High, 5=Very High/Almost Certain)

❌ BAD - Don't ask for CIA BREAKDOWN:
"What is the 'Business Impact Rating' for the loss of Confidentiality of this Database's data?"
← NO! This is Agent 1's job to analyze!

"What is the 'Business Impact Rating' for the loss of Integrity of this Database's data?"
← NO! This is Agent 1's job to analyze!

"What is the 'Business Impact Rating' for the loss of Availability of this Database?"
← NO! This is Agent 1's job to analyze!

═══════════════════════════════════════════════════════════════════════════════
CRITICAL RULES - WHAT TO ASK AND NOT ASK
═══════════════════════════════════════════════════════════════════════════════

✅ DO ASK:
1. Factual questions: "Does X exist?" "How many Y?" "What is Z?" "Is feature enabled?"
2. Classification questions: "What is the data classification?" (from org's scale)
3. Criticality questions: "What is the business criticality?" (from org's scale)
4. Overall opinion questions: "Overall, what would be the impact?" "Overall, how likely?"

❌ DON'T ASK:
1. CIA impact questions: "What is Confidentiality/Integrity/Availability impact?"
2. Control effectiveness questions: "Rate control effectiveness (1-5)"
3. Calculation questions: "Calculate Risk Value = Impact × Probability"
4. Analysis questions: "What is the Risk Evaluation Rating?"
5. Decision questions: "Is this risk acceptable?"
6. Residual risk questions: "What is the residual risk after controls?"

═══════════════════════════════════════════════════════════════════════════════
WHY THIS MATTERS - SEPARATION OF CONCERNS
═══════════════════════════════════════════════════════════════════════════════

ASSET OWNERS are experts at:
✅ Knowing what their asset does
✅ Knowing what controls are in place
✅ Giving overall perspective on criticality and impact

ASSET OWNERS should NOT:
❌ Perform CIA analysis (that's technical risk analysis)
❌ Calculate control effectiveness
❌ Perform risk calculations
❌ Make risk acceptance decisions

RISK ANALYSTS (Agents 1-4) are experts at:
✅ Analyzing CIA impacts from facts
✅ Calculating risk values
✅ Evaluating control effectiveness
✅ Making risk decisions

Your job is to collect the RIGHT information so analysts can analyze it!

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return ONLY valid JSON:

{{
  "questionnaire_title": "Risk Assessment Questionnaire for {asset_type or 'Asset'}",
  "asset_type_analyzed": "{asset_type or 'Generic Asset'}",
  "intelligence_summary": {{
    "asset_understanding": "Your understanding of what this asset is",
    "key_risk_factors": ["FACTUAL things that determine risk - NOT ratings"],
    "methodology_discovered": "What you learned about organization's methodology",
    "scales_discovered": "What OVERALL rating scales they use (not CIA scales)",
    "why_these_questions": "Why you chose FACTS and OVERALL opinions, NOT CIA ratings",
    "searches_performed": ["List the searches you made"]
  }},
  "sections": [
    {{
      "section_name": "Section name",
      "section_purpose": "Why this section matters",
      "questions": [
        {{
          "question_id": "unique_id",
          "question_text": "The intelligent FACTUAL question",
          "question_type": "text|dropdown|multiselect|textarea|number",
          "options": [{{"value": "val", "label": "Label"}}],
          "required": true|false,
          "help_text": "Help text",
          "why_this_matters": "How this FACT helps assess risk"
        }}
      ]
    }}
  ]
}}

═══════════════════════════════════════════════════════════════════════════════
EXAMPLE OF CORRECT QUESTIONNAIRE STRUCTURE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL: Section 1 MUST ALWAYS be Asset Identification with discovered fields!**

Section 1: Asset Identification (DISCOVERED FROM RAG - ALWAYS FIRST!)
- What is the asset name/title? (Q_ASSET_NAME or discovered field ID)
- What type of asset is this? (Q_ASSET_TYPE with discovered categories as dropdown)
- Who is the asset owner? (if discovered from RAG)
- Where is it located? (if discovered from RAG)
- Any other identification fields discovered from RAG

Section 2: Business Context
- What is the business criticality? (Low/Medium/High/Critical)
- How many users depend on this?
- What business processes depend on this?

Section 3: Data & Security Facts (for Database)
- What data classification? (Public/Confidential/Restricted)
- Does it store PII/PHI/PCI? (Yes/No)
- Is MFA enabled? (Yes/No)
- Is encryption enabled? (Yes/No)
- Are backups performed? (Yes/No/Frequency)

Section 4: Control Facts
- Is access logging enabled? (Yes/No)
- Are logs monitored? (Yes/No)
- Is patching done regularly? (Yes/No/Frequency)
- Is there a DR plan? (Yes/No)

Section 5: Overall Risk Perspective
- Overall, what would be impact if severely compromised? (1-5 scale from org)
- Overall, what is likelihood of severe compromise? (1-5 scale from org)

[NO Section for CIA Ratings - Agent 1 will calculate those!]
[NO Section for Control Effectiveness - Agent 3 will calculate that!]
[NO Section for Risk Calculations - Agent 2 will calculate those!]

═══════════════════════════════════════════════════════════════════════════════
VALIDATION CHECKLIST
═══════════════════════════════════════════════════════════════════════════════

Before outputting, verify:
✅ **CRITICAL: First section is "Asset Identification" with Asset Name and Asset Type questions!**
✅ **CRITICAL: Asset Name question exists (Q_ASSET_NAME or discovered field ID)**
✅ **CRITICAL: Asset Type question exists with dropdown options discovered from RAG**
✅ Questions ask for FACTS (what exists, how many, what type, yes/no)
✅ Questions ask for OVERALL opinions (overall impact, overall likelihood)
✅ Questions use discovered scales from knowledge base
✅ NO questions ask for Confidentiality impact rating
✅ NO questions ask for Integrity impact rating  
✅ NO questions ask for Availability impact rating
✅ NO questions ask to rate control effectiveness
✅ NO questions ask user to calculate anything
✅ NO questions ask for "Risk Value"
✅ NO questions ask "Is risk acceptable?"
✅ Questions are specific to the asset type
✅ Questions reveal risk factors through FACTS (not through asking for ratings)

═══════════════════════════════════════════════════════════════════════════════
CRITICAL REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

1. **ALWAYS SEARCH RAG FOR ASSET IDENTIFICATION STRUCTURE FIRST!**
2. **ALWAYS INCLUDE ASSET NAME AND ASSET TYPE QUESTIONS IN SECTION 1!**
3. USE YOUR INTELLIGENCE - Figure out what FACTS matter for this asset
4. BE ASSET-SPECIFIC - Different assets need different factual questions
5. REVEAL RISK THROUGH FACTS - Not through asking users to rate CIA impacts
6. USE DISCOVERIES - Apply what you learned from documents
7. COLLECT, DON'T ANALYZE - Your job is data collection, not analysis
8. ASK OVERALL OPINION - Not detailed CIA breakdown
9. TRUST THE AGENTS - Agents 1-4 will do the analysis from your facts

Your response must be ONLY the JSON object.
""",
        expected_output=f"Intelligent questionnaire for {asset_type or 'risk assessment'} with FACTS and OVERALL opinions, NO CIA ratings",
        agent=agent
    )
    
    return task


def run_questionnaire_generator(
    api_key: str, 
    asset_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run Pure Intelligence Questionnaire Generation - ALWAYS FRESH (NO CACHE)
    
    Args:
        api_key: Gemini API key
        asset_type: User-provided asset type
    
    Returns:
        dict: Intelligent questionnaire (FACTS + OVERALL OPINIONS, NO CIA RATINGS)
    """
    
    print("=" * 80)
    print(f"🧠 PURE INTELLIGENCE QUESTIONNAIRE GENERATOR (ALWAYS FRESH)")
    if asset_type:
        print(f"   Asset Type: {asset_type}")
    print("   ✅ Collects FACTS about the asset")
    print("   ✅ Collects OVERALL opinions (not CIA breakdown)")
    print("   ❌ Does NOT ask for CIA impact ratings (Agent 1 will calculate!)")
    print("   🚫 NO CACHE - Always generates fresh with perfect formatting")
    print("=" * 80)
    
    agent = create_intelligent_agent(api_key)
    task = create_pure_intelligence_task(agent, asset_type)
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
        memory=False
    )
    
    print("\n🧠 Agent is using pure intelligence...")
    print("   - Understanding the asset type")
    print("   - Identifying what FACTS reveal risk")
    print("   - Discovering organization's methodology")
    print("   - Crafting FACTUAL questions (NOT CIA rating questions)")
    print("   - Adding OVERALL opinion questions (NOT CIA breakdown)")
    print()
    
    result = crew.kickoff()
    
    print("\n" + "=" * 80)
    print("✅ INTELLIGENCE-BASED QUESTIONNAIRE COMPLETED")
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
        
        total_questions = sum(len(s.get('questions', [])) for s in result_json.get('sections', []))
        print(f"\n✅ Generated {total_questions} intelligent FACTUAL questions")
        
        if 'intelligence_summary' in result_json:
            summary = result_json['intelligence_summary']
            
            print(f"\n🧠 Agent's Understanding:")
            print(f"   {summary.get('asset_understanding', 'N/A')}")
            
            print(f"\n🎯 Key Risk Factors (FACTS to collect):")
            for factor in summary.get('key_risk_factors', []):
                print(f"   - {factor}")
            
            print(f"\n💡 Agent's Reasoning:")
            print(f"   {summary.get('why_these_questions', 'N/A')}")
        
        print("\n🚫 NO CACHE - Fresh questionnaire with perfect formatting every time!")
        
        return result_json
        
    except json.JSONDecodeError as e:
        print(f"\n⚠️  JSON parsing failed: {e}")
        return {
            "questionnaire_title": f"Risk Assessment for {asset_type or 'Asset'}",
            "error": "JSON parsing failed",
            "sections": []
        }
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    import os
    api_key = os.getenv("GEMINI_API_KEY")
    
    result = run_questionnaire_generator(api_key, asset_type="Database Server")
    print(f"\nGenerated {sum(len(s.get('questions', [])) for s in result.get('sections', []))} questions")
    print("\n✅ Questionnaire asks for FACTS, not CIA ratings!")