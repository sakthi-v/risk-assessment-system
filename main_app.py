"""
Risk Resolver - Integrated Streamlit Application
Phase 1: RAG Knowledge Base
Phase 2: Complete 6-Agent Risk Assessment Pipeline (TRULY AGENTIC)
Includes Agent 0: Questionnaire Generator
"""

import streamlit as st
import google.generativeai as genai
from pathlib import Path
import tempfile
import os
import time
from typing import List, Dict
import json
import pickle
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px 
from datetime import datetime

# Document processing libraries
from docx import Document
import PyPDF2
import openpyxl
from openpyxl import load_workbook

# Vector store and embeddings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Phase 2 imports - UPDATED FOR TRULY AGENTIC AGENTS
import sys
sys.path.insert(0, str(Path(__file__).parent))

from phase2_risk_resolver.config.settings import KNOWLEDGE_BASE_DIR, OUTPUTS_DIR
from phase2_risk_resolver.tools.rag_tool import initialize_rag

# API Key Management with Auto-Rotation
from api_key_manager import get_api_key_manager, get_active_api_key
from agent_executor import execute_agent_with_retry, execute_all_agents_with_retry
from database_manager import get_database_connection

# Session Management - Auto-save and restore
from session_manager import get_session_manager, auto_save_session, show_session_restore_ui

# UPDATED IMPORTS - New function names and Agent 0
from phase2_risk_resolver.agents.agent_0_questionnaire import run_questionnaire_generator
from phase2_risk_resolver.agents.agent_0_5_threat_discovery import run_threat_discovery  # NEW!
from phase2_risk_resolver.agents.agent_1_cia import run_impact_assessment  # Changed!
from phase2_risk_resolver.agents.agent_2_risk import run_risk_quantification
from phase2_risk_resolver.agents.agent_3_control import run_control_discovery
from phase2_risk_resolver.agents.agent_4_decision import run_risk_decision
from phase2_risk_resolver.agents.agent_4_acceptance_questionnaire import generate_acceptance_questionnaire
from phase2_risk_resolver.agents.agent_4_acceptance_form import generate_acceptance_form
from phase2_risk_resolver.agents.agent_4_transfer_questionnaire import generate_transfer_questionnaire
from phase2_risk_resolver.agents.agent_4_transfer_form import generate_transfer_form
from phase2_risk_resolver.agents.agent_4_terminate_questionnaire import generate_terminate_questionnaire
from phase2_risk_resolver.agents.agent_4_terminate_form import generate_terminate_form
# Phase 5: Risk Register UI
from risk_register_page import render_risk_register_page
from followup_page import render_followup_page

# Configure page
st.set_page_config(
    page_title="Risk Resolver - Truly Agentic AI System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===================================================================
# PASSWORD PROTECTION - Admin Access Only
# ===================================================================
from dotenv import load_dotenv
load_dotenv()

params = st.query_params
is_questionnaire_form = params.get('page') == 'form' and params.get('token')

if not is_questionnaire_form:
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔒 Risk Assessment System")
        st.markdown("### Admin Login Required")
        st.info("ℹ️ This system is password-protected. Please enter the admin password to continue.")
        
        password = st.text_input("Password", type="password", key="login_password")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("🔓 Login", type="primary", use_container_width=True):
                admin_password = os.getenv('ADMIN_PASSWORD', 'RiskApp2024!Secure')
                if password == admin_password:
                    st.session_state.authenticated = True
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("❌ Incorrect password. Please try again.")
        with col2:
            st.caption("Forgot password? Contact system administrator.")
        st.stop()

# ===================================================================
# URL PARAMETER CHECK - Show only form if ?page=form&token=...
# ===================================================================
if params.get('page') == 'form' and params.get('token'):
    from questionnaire_form_page import show_questionnaire_form
    show_questionnaire_form(params.get('token'))
    st.stop()

# ===================================================================
# FOLLOW-UP NOTIFICATION CHECK (Automatic on App Load)
# ===================================================================
try:
    from phase2_risk_resolver.database.followup_checker import get_risks_needing_followup
    
    # Check for risks needing follow-up (5 days threshold)
    risks_needing_followup = get_risks_needing_followup(days_threshold=5)
    
    if risks_needing_followup:
        # Display alert at top of page
        st.warning(f"⚠️ **{len(risks_needing_followup)} risk(s) need follow-up!** These risks were created 5+ days ago and require follow-up assessment.")
        
        with st.expander("📋 View Risks Needing Follow-up", expanded=False):
            for risk in risks_needing_followup:
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                with col1:
                    st.caption(f"**Risk ID:** {risk['risk_id']}")
                with col2:
                    st.caption(f"**Asset:** {risk['asset_name']}")
                with col3:
                    st.caption(f"**Decision:** {risk['treatment_decision']}")
                with col4:
                    st.caption(f"**{risk['days_since_creation']} days ago**")
            
            st.info("💡 Go to Follow-up page to complete follow-up questionnaires for these risks.")
except Exception as e:
    # Silently fail if database doesn't exist yet
    pass

# ===================================================================
# PERSISTENT STORAGE PATHS
# ===================================================================
KNOWLEDGE_BASE_DIR = Path("knowledge_base")
KNOWLEDGE_BASE_DIR.mkdir(exist_ok=True)

KB_DOCUMENTS_FILE = KNOWLEDGE_BASE_DIR / "documents.pkl"
KB_VECTORIZER_FILE = KNOWLEDGE_BASE_DIR / "vectorizer.pkl"
KB_VECTORS_FILE = KNOWLEDGE_BASE_DIR / "document_vectors.pkl"
KB_METADATA_FILE = KNOWLEDGE_BASE_DIR / "metadata.json"

# Initialize session state - UPDATED VARIABLE NAMES
if 'documents' not in st.session_state:
    st.session_state.documents = []
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'vectorizer' not in st.session_state:
    st.session_state.vectorizer = None
if 'document_vectors' not in st.session_state:
    st.session_state.document_vectors = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'kb_loaded' not in st.session_state:
    st.session_state.kb_loaded = False
if 'rag_initialized' not in st.session_state:
    st.session_state.rag_initialized = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Home"
if 'sample_assets' not in st.session_state:
    st.session_state.sample_assets = []
if 'selected_asset' not in st.session_state:
    st.session_state.selected_asset = None

# UPDATED SESSION STATE - Changed variable names for truly agentic agents
if 'questionnaire_result' not in st.session_state:
    st.session_state.questionnaire_result = None
if 'questionnaire_answers' not in st.session_state:
    st.session_state.questionnaire_answers = {}
if 'impact_result' not in st.session_state:  # Changed from cia_result
    st.session_state.impact_result = None
if 'risk_result' not in st.session_state:
    st.session_state.risk_result = None
if 'control_result' not in st.session_state:
    st.session_state.control_result = None
if 'decision_result' not in st.session_state:
    st.session_state.decision_result = None
if 'output_result' not in st.session_state:  # Changed from excel_result
    st.session_state.output_result = None


# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

def format_risk_rating(rating):
    """Format risk rating to ensure it's always X/5 format (not X/5/5)"""
    if not rating:
        return "N/A"
    rating_str = str(rating)
    # If already has /5, return as-is
    if '/5' in rating_str:
        # Remove duplicate /5 if present (e.g., "4/5/5" -> "4/5")
        parts = rating_str.split('/5')
        return f"{parts[0]}/5"
    # Otherwise add /5
    return f"{rating_str}/5"

# ===================================================================
# HEATMAP VISUALIZATION FUNCTION
# ===================================================================

def create_risk_heatmap(threats):
    """Create interactive 5x5 risk heatmap"""
    
    # Initialize 5x5 matrix with empty lists
    matrix = [[[] for _ in range(5)] for _ in range(5)]
    
    # Place threats in matrix
    for threat in threats:
        impact = threat['impact'] - 1  # Convert 1-5 to 0-4
        probability = threat['probability'] - 1
        row_index = 4 - impact  # Flip so high impact is at top
        col_index = probability
        matrix[row_index][col_index].append(threat['name'][:30])
    
    # Create heatmap data
    z_values = []
    hover_text = []
    annotations = []
    
    for row_idx, row in enumerate(matrix):
        z_row = []
        hover_row = []
        
        for col_idx, cell in enumerate(row):
            impact = 5 - row_idx
            probability = col_idx + 1
            risk_value = impact * probability
            
            z_row.append(risk_value)
            
            if cell:
                hover_text_str = f"<b>Impact: {impact}, Probability: {probability}</b><br>"
                hover_text_str += f"<b>Risk Value: {risk_value}</b><br><br>"
                hover_text_str += "<br>".join([f"� {threat}" for threat in cell])
            else:
                hover_text_str = f"<b>Impact: {impact}, Probability: {probability}</b><br>"
                hover_text_str += f"<b>Risk Value: {risk_value}</b><br><br>No threats"
            
            hover_row.append(hover_text_str)
            
            if cell:
                annotations.append(
                    dict(
                        x=col_idx,
                        y=row_idx,
                        text=f"<b>{len(cell)} threat(s)</b>",
                        showarrow=False,
                        font=dict(color='white', size=10, family='Arial Black'),
                        xanchor='center',
                        yanchor='middle'
                    )
                )
        
        z_values.append(z_row)
        hover_text.append(hover_row)
    
    # Create figure
    fig = go.Figure(data=go.Heatmap(
        z=z_values,
        x=['1<br>(Rare)', '2<br>(Unlikely)', '3<br>(Possible)', '4<br>(Likely)', '5<br>(Almost<br>Certain)'],
        y=['5<br>(Catastrophic)', '4<br>(Major)', '3<br>(Moderate)', '2<br>(Minor)', '1<br>(Insignificant)'],
        hovertext=hover_text,
        hoverinfo='text',
        colorscale=[
            [0.0, '#28a745'],   # Green
            [0.24, '#28a745'],
            [0.24, '#ffc107'],  # Yellow
            [0.48, '#ffc107'],
            [0.48, '#fd7e14'],  # Orange
            [0.72, '#fd7e14'],
            [0.72, '#dc3545'],  # Red
            [1.0, '#dc3545']
        ],
        showscale=True,
        colorbar=dict(
            title=dict(
                text="<b>Risk Level</b>",
                side="right"
            ),
            tickmode="array",
            tickvals=[1, 6, 12, 18, 25],
            ticktext=["1 (Low)", "6", "12 (Medium)", "18 (High)", "25 (Extreme)"],
            len=0.7,
            thickness=15
        )
    ))
    
    # Add annotations
    fig.update_layout(annotations=annotations)
    
    # Update layout
    fig.update_layout(
        title=dict(
            text="<b>Risk Heatmap Matrix (5�5)</b>",
            x=0.5,
            xanchor='center',
            font=dict(size=20, color='#2c3e50')
        ),
        xaxis=dict(
            title=dict(
                text="<b>Probability 📊</b>",
                font=dict(size=14, color='#2c3e50')
            ),
            side='bottom',
            tickfont=dict(size=11)
        ),
        yaxis=dict(
            title=dict(
                text="<b>⚠️ Impact</b>",
                font=dict(size=14, color='#2c3e50')
            ),
            tickfont=dict(size=11)
        ),
        height=600,
        font=dict(size=12),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='white'
    )
    
    # Make cells square
    fig.update_xaxes(constrain='domain')
    fig.update_yaxes(scaleanchor='x', scaleratio=1)
    
    return fig


# ===================================================================
# KNOWLEDGE BASE FUNCTIONS
# ===================================================================

def load_knowledge_base():
    """Load the knowledge base from disk"""
    try:
        if not all([
            KB_DOCUMENTS_FILE.exists(),
            KB_VECTORIZER_FILE.exists(),
            KB_VECTORS_FILE.exists(),
            KB_METADATA_FILE.exists()
        ]):
            return None, None, None, None
        
        with open(KB_DOCUMENTS_FILE, 'rb') as f:
            documents = pickle.load(f)
        with open(KB_VECTORIZER_FILE, 'rb') as f:
            vectorizer = pickle.load(f)
        with open(KB_VECTORS_FILE, 'rb') as f:
            document_vectors = pickle.load(f)
        with open(KB_METADATA_FILE, 'r') as f:
            metadata = json.load(f)
        
        return documents, vectorizer, document_vectors, metadata
    except Exception as e:
        st.error(f"Error loading knowledge base: {str(e)}")
        return None, None, None, None

def knowledge_base_exists():
    """Check if a saved knowledge base exists"""
    return all([
        KB_DOCUMENTS_FILE.exists(),
        KB_VECTORIZER_FILE.exists(),
        KB_VECTORS_FILE.exists(),
        KB_METADATA_FILE.exists()
    ])

# ===================================================================
# ASSET DATA PROCESSING
# ===================================================================

def extract_assets_from_excel(uploaded_file) -> List[Dict]:
    """Extract asset information from uploaded Excel file"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        df = pd.read_excel(tmp_path)
        os.unlink(tmp_path)
        
        assets = []
        for idx, row in df.iterrows():
            if pd.isna(row.get('asset_name', None)):
                continue
            
            asset = {
                'asset_name': str(row.get('asset_name', '')),
                'asset_type': str(row.get('asset_type', '')),
                'asset_owner': str(row.get('asset_owner', '')),
                'location': str(row.get('location', '')),
                'description': str(row.get('description', '')),
                'threats_and_vulnerabilities': []
            }
            
            if 'threats_json' in row and not pd.isna(row['threats_json']):
                try:
                    asset['threats_and_vulnerabilities'] = json.loads(row['threats_json'])
                except:
                    pass
            
            assets.append(asset)
        
        return assets
        
    except Exception as e:
        st.error(f"Error reading Excel file: {str(e)}")
        return []

def extract_assets_from_json(uploaded_file) -> List[Dict]:
    """Extract asset information from uploaded JSON file"""
    try:
        content = uploaded_file.read()
        data = json.loads(content)
        
        if isinstance(data, dict):
            return [data]
        elif isinstance(data, list):
            return data
        else:
            st.error("Invalid JSON format")
            return []
            
    except Exception as e:
        st.error(f"Error reading JSON file: {str(e)}")
        return []

# ===================================================================
# PAGE: HOME
# ===================================================================

def render_home_page():
    """Render home page with system status"""
    st.title("🎯 Risk Resolver - Truly Agentic AI System")
    st.markdown("### Automated Risk Assessment powered by Adaptive AI Agents")
    
    st.markdown("---")
    
    # System Status
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📚 Knowledge Base",
            value="Ready" if st.session_state.processed else "Not Loaded",
            delta=f"{len(st.session_state.documents)} docs" if st.session_state.processed else "Upload needed"
        )
    
    with col2:
        agents_ready = "6 Agents" if st.session_state.rag_initialized else "Initializing"
        st.metric(
            label="🤖 Agent System",
            value=agents_ready,
            delta="Truly Agentic"
        )
    
    with col3:
        completed = sum([
            1 if st.session_state.impact_result else 0,
            1 if st.session_state.risk_result else 0,
            1 if st.session_state.control_result else 0,
            1 if st.session_state.decision_result else 0
        ])
        st.metric(
            label="✅ Completed",
            value=f"{completed}/4",
            delta="Agents executed"
        )
    
    with col4:
        st.metric(
            label="📊 Assets Loaded",
            value=len(st.session_state.sample_assets),
            delta="Ready for assessment"
        )
    
    st.markdown("---")
    
    # NEW: Highlight Truly Agentic Feature
    st.info("ℹ️ **Truly Agentic System** - Agents learn YOUR methodology from documents! No hardcoding.")
    
    # Quick Start Guide
    st.markdown("### 📖 Quick Start Guide")

    st.markdown("""
    **Phase 1: Knowledge Base Setup** (One-time)
    1. Upload your Risk Management documents (PDFs, DOCX, Excel)
    2. System creates a searchable knowledge base
    
    **Phase 2: Complete Risk Assessment** (Repeatable)
    
    **Option A: Upload Asset Data File**
    1. Upload Excel/JSON with asset data
    2. Run Agents 1-4 for complete assessment
    
    **Option B: Fill Questionnaire** 
    1. Generate questionnaire (Agent 0)
    2. Fill questionnaire based on your methodology
    3. Submit and run Agents 1-4
    
    **Agents:**
    - 0️⃣ **Agent 0**: Questionnaire Generator (learns your process)
    - 1️⃣ **Agent 1**: Impact Assessment (discovers your methodology)
    - 2️⃣ **Agent 2**: Risk Quantification (learns your formula)
    - 3️⃣ **Agent 3**: Control Discovery (identifies your frameworks)
    - 4️⃣ **Agent 4**: Risk Decision (applies your treatment options)
    """)

# ===================================================================
# PAGE: KNOWLEDGE BASE
# ===================================================================

def render_knowledge_base_page(api_key):
    """Render Knowledge Base management page"""
    st.title("📚 Knowledge Base Management")
    
    if st.session_state.processed:
        st.success(f"✅ Knowledge Base Active: {len(st.session_state.documents)} documents loaded")
        
        with st.expander("📄 View Loaded Documents"):
            for doc in st.session_state.documents:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{doc['filename']}**")
                with col2:
                    st.code(doc['file_type'])
        
        st.markdown("---")
        st.subheader("❓ Ask Questions")
        
        if 'rag_system' not in st.session_state and api_key:
            from phase1_rag_app import RAGSystem
            rag_system = RAGSystem(api_key)
            rag_system.documents = st.session_state.documents
            rag_system.document_texts = [doc['text'] for doc in st.session_state.documents]
            rag_system.document_names = [doc['filename'] for doc in st.session_state.documents]
            rag_system.vectorizer = st.session_state.vectorizer
            rag_system.document_vectors = st.session_state.document_vectors
            st.session_state.rag_system = rag_system
        
        for chat in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(chat['question'])
            with st.chat_message("assistant"):
                st.write(chat['answer'])
                if 'sources' in chat:
                    with st.expander("📚 Sources"):
                        for source in chat['sources']:
                            st.markdown(f"- **{source['filename']}** (Relevance: {source['similarity']:.2%})")
        
        question = st.chat_input("Ask a question about your documents...")
        
        if question and api_key:
            with st.chat_message("user"):
                st.write(question)
            
            with st.chat_message("assistant"):
                with st.spinner("Searching..."):
                    relevant_docs = st.session_state.rag_system.retrieve_relevant_documents(question, top_k=7)
                    
                    if not relevant_docs:
                        answer = "I couldn't find relevant information to answer this question."
                        st.write(answer)
                    else:
                        answer = st.session_state.rag_system.generate_answer(question, relevant_docs)
                        st.write(answer)
                        
                        with st.expander("📚 Sources"):
                            for doc in relevant_docs:
                                st.markdown(f"- **{doc['filename']}** (Relevance: {doc['similarity']:.2%})")
                        
                        st.session_state.chat_history.append({
                            'question': question,
                            'answer': answer,
                            'sources': relevant_docs
                        })
    
    else:
        st.warning("⚠️ Knowledge base not found. Please upload documents to create it.")
        st.info("ℹ️ Go to sidebar to upload and process documents")

# ===================================================================
# PAGE: RISK ASSESSMENT
# ===================================================================

def render_risk_assessment_page(api_key):
    """Render Risk Assessment page with complete 6-agent pipeline"""
    st.title("🎯 Risk Assessment - Truly Agentic 6-Agent Pipeline")
    
    # 💾 SESSION RESTORE UI - Show at top of page
    show_session_restore_ui()
    
    # Check prerequisites
    if not st.session_state.processed:
        st.error("❌ Knowledge Base not loaded! Please upload documents first.")
        st.info("ℹ️ Go to 'Knowledge Base' page to upload documents")
        return
    
    if not api_key:
        st.error("❌ API Key required! Please enter your Gemini API key in the sidebar.")
        return
    
    # Initialize RAG for agents if needed (with current API key)
    if not st.session_state.rag_initialized:
        with st.spinner("⏳ Initializing Truly Agentic Agent System..."):
            try:
                from phase2_risk_resolver.tools.rag_tool import initialize_rag
                initialize_rag(api_key, KNOWLEDGE_BASE_DIR)
                st.session_state.rag_initialized = True
                st.success("✅ Agent system initialized with discovery capabilities!")
            except Exception as e:
                st.error(f"Failed to initialize: {str(e)}")
                return
    else:
        # Re-initialize RAG with current API key if it changed
        try:
            from phase2_risk_resolver.tools.rag_tool import update_rag_api_key
            update_rag_api_key(api_key)
        except:
            pass
    
    st.markdown("---")
    st.header(" Generate Intelligent Questionnaire")

    st.info("💡 **Don't have asset data?** Tell us what asset type you want to assess, and our AI will intelligently figure out what questions to ask!")

    # Pure text input - NO dropdown!
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("### What Asset Do You Want to Assess?")
        st.caption("💡 **Enter a description** (e.g., 'Database Server', 'Employee Laptop') - AI will ask for specific name and type in the questionnaire!")
        
        asset_type_input = st.text_input(
            "Asset Description",
            placeholder="e.g., Database Server, Web Application, Employee Laptop, Manufacturing Equipment, Cloud Service, Office Building, Research Lab, AI Model, Smart Contract, IoT Sensor...",
            key="asset_type_input",
            help="Enter a description of the asset. The AI will generate a questionnaire that asks for the specific asset name and asset type (Physical/Software/Information/Service/People)."
        )
        
        # Examples to help users
        with st.expander("💡 Need ideas? See examples"):
            st.markdown("""
            **Technology Assets:**
            - Database Server, Web Application, Mobile App, API Service
            - Cloud Infrastructure, Network Device, Firewall
            - IoT Device, Smart Sensor, Edge Computing Node
            
            **Physical Assets:**
            - Office Building, Data Center, Manufacturing Equipment
            - Vehicle Fleet, Warehouse, Laboratory Equipment
            
            **Information Assets:**
            - Customer Database, Intellectual Property, Research Data
            - Source Code Repository, Document Management System
            
            **Human Assets:**
            - Key Personnel, Executive Team, Technical Expert
            - Contractor, Third-Party Consultant
            
            **Business Assets:**
            - Business Process, Supply Chain, Vendor Relationship
            - Brand, Reputation, Customer Relationships
            
            **And literally ANY other asset you can think of!**
            The AI will figure it out! 🤖
            """)

    with col2:
        st.markdown("### AI Status")
        if asset_type_input and asset_type_input.strip():
            st.success(f"✅ **Will assess:**\n\n{asset_type_input}")
            st.caption("AI will intelligently determine relevant questions")
        else:
            st.info("ℹ️ **Generic mode**")
            st.caption("Leave blank for generic questionnaire")

    # Generate button
    generate_button_text = f"🤖 Generate Intelligent Questionnaire{' for ' + asset_type_input if asset_type_input and asset_type_input.strip() else ''}"

    if st.button(generate_button_text, type="primary", use_container_width=True, disabled=False):
        
        final_asset_type = asset_type_input.strip() if asset_type_input else None
        
        with st.spinner(f"🤖 AI is thinking about '{final_asset_type}' and intelligently determining what questions to ask..."):
            try:
                result = execute_agent_with_retry(
                    run_questionnaire_generator,
                    "Agent 0: Questionnaire Generator",
                    asset_type=final_asset_type
                )
                
                if 'error' in result:
                    st.error(f"❌ Error: {result['error']}")
                    if 'raw_output' in result:
                        with st.expander("View Raw Output"):
                            st.text(result['raw_output'])
                else:
                    st.session_state.questionnaire_result = result
                    st.session_state.current_asset_type = final_asset_type
                    st.success(f"✅ AI has intelligently generated a questionnaire for: {final_asset_type or 'Generic Asset'}!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error generating questionnaire: {str(e)}")
                import traceback
                with st.expander("View Error Details"):
                    st.code(traceback.format_exc())

    # Display questionnaire if generated
    if st.session_state.questionnaire_result:
        st.markdown("---")
        st.subheader("📝 AI-Generated Questionnaire")
        
        questionnaire = st.session_state.questionnaire_result
        current_asset = st.session_state.get('current_asset_type', 'Asset')
        
        # 📧 EMAIL OPTION - Send questionnaire to stakeholder
        st.info("💡 **Choose how to fill the questionnaire:**")
        
        col_option1, col_option2 = st.columns(2)
        
        with col_option1:
            st.markdown("### 📧 Option 1: Send via Email")
            st.caption("Send questionnaire to asset owner/stakeholder")
            
            recipient_email = st.text_input(
                "Recipient Email Address",
                placeholder="stakeholder@company.com",
                key="recipient_email_input",
                help="Email address of the person who will fill the questionnaire"
            )
            
            if st.button("📧 Send Questionnaire Email", type="primary", disabled=not recipient_email):
                with st.spinner(f"📧 Sending email to {recipient_email}..."):
                    try:
                        from email_sender import send_questionnaire_email
                        
                        result = send_questionnaire_email(
                            recipient_email=recipient_email,
                            asset_name=current_asset or 'Asset',
                            questionnaire=questionnaire,
                            questionnaire_type='Agent0'
                        )
                        
                        if result and result.get('success'):
                            st.success(f"✅ Email sent successfully to {recipient_email}!")
                            st.info(f"📋 **Tracking Token:** {result['token']}")
                            st.caption("The recipient will receive a link to fill the questionnaire online.")
                        else:
                            error_msg = result.get('error', 'Unknown error') if result else 'No response'
                            st.error(f"❌ Failed to send email: {error_msg}")
                            with st.expander("💡 Troubleshooting"):
                                st.markdown("""
                                **Common Issues:**
                                - Outlook not installed or not running
                                - Outlook not configured with email account
                                - Windows security blocking COM automation
                                - Antivirus blocking script access to Outlook
                                
                                **Solutions:**
                                1. Open Outlook manually and ensure it's working
                                2. Check if you can send emails from Outlook normally
                                3. Run this app as Administrator
                                4. Check Windows Firewall/Antivirus settings
                                """)
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        import traceback
                        with st.expander("🔍 Error Details"):
                            st.code(traceback.format_exc())
        
        with col_option2:
            st.markdown("### ✍️ Option 2: Fill Manually")
            st.caption("Fill the questionnaire yourself right now")
            st.info("👇 Scroll down to see the questionnaire form below")
        
        st.markdown("---")
        
        # Show AI's intelligence summary
        if 'intelligence_summary' in questionnaire:
            with st.expander("🧠 AI's Intelligence - How it figured out what to ask", expanded=True):
                intelligence = questionnaire['intelligence_summary']
                
                # Asset Understanding
                st.markdown("### 🧠 AI's Understanding of the Asset")
                st.info(intelligence.get('asset_understanding', 'N/A'))
                
                # Key Risk Factors
                st.markdown("### 🎯 Key Risk Factors Identified")
                st.success("The AI identified these factors as critical for assessing this asset's risk:")
                risk_factors = intelligence.get('key_risk_factors', [])
                if risk_factors:
                    for i, factor in enumerate(risk_factors, 1):
                        st.markdown(f"{i}. **{factor}**")
                else:
                    st.caption("No specific factors listed")
                
                # Methodology Discovery
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 📋 Organization's Methodology")
                    st.info(intelligence.get('methodology_discovered', 'N/A'))
                    
                    st.markdown("### 📊 Rating Scales Found")
                    st.info(intelligence.get('scales_discovered', 'N/A'))
                
                with col2:
                    st.markdown("### 🧠 AI's Reasoning")
                    st.success(intelligence.get('why_these_questions', 'The AI crafted these questions based on its expertise in risk assessment'))
                    
                    # Searches performed
                    if 'searches_performed' in intelligence:
                        st.markdown("### 🔍 Searches AI Performed")
                        searches = intelligence['searches_performed']
                        if searches:
                            for i, search in enumerate(searches, 1):
                                st.caption(f"{i}. {search}")
        
        # Instructions
        st.markdown("---")
        st.success(f"✅ **Fill out the questionnaire below for your {current_asset}, then click Submit to create asset data for risk assessment!**")
        
        # Create form
        with st.form("questionnaire_form"):
            answers = {}
            
            for section_idx, section in enumerate(questionnaire.get('sections', [])):
                st.markdown(f"### 📋 {section.get('section_name', f'Section {section_idx + 1}')}")
                
                # Section purpose
                if section.get('section_purpose'):
                    st.caption(f"**Purpose:** {section['section_purpose']}")
                
                # Section description
                if section.get('section_description'):
                    st.caption(section['section_description'])
                
                st.markdown("---")  # Spacing
                
                for question in section.get('questions', []):
                    q_id = question.get('question_id')
                    q_text = question.get('question_text')
                    q_type = question.get('question_type', 'text')
                    q_options = question.get('options', [])
                    q_help = question.get('help_text', '')
                    q_required = question.get('required', False)
                    
                    # Add "why this matters" to help text
                    if question.get('why_this_matters'):
                        q_help += f"\n\n💡 Why this matters: {question['why_this_matters']}"
                    
                    # Display question based on type
                    if q_type == 'text':
                        answers[q_id] = st.text_input(
                            q_text,
                            key=f"q_{q_id}",
                            help=q_help
                        )
                    
                    elif q_type == 'textarea':
                        answers[q_id] = st.text_area(
                            q_text,
                            key=f"q_{q_id}",
                            help=q_help,
                            height=100
                        )
                    
                    elif q_type == 'dropdown' or q_type == 'select':
                        # Extract labels from option dictionaries
                        display_options = []
                        value_to_label_map = {}
                        
                        for opt in q_options:
                            if isinstance(opt, dict):
                                label = opt.get('label', opt.get('value', str(opt)))
                                value = opt.get('value', label)
                                display_options.append(label)
                                value_to_label_map[label] = value
                            else:
                                display_options.append(str(opt))
                                value_to_label_map[str(opt)] = opt
                        
                        if not q_required:
                            display_options = ['-- Select --'] + display_options
                        
                        selected_label = st.selectbox(
                            q_text,
                            options=display_options,
                            key=f"q_{q_id}",
                            help=q_help
                        )
                        
                        if selected_label == '-- Select --':
                            answers[q_id] = None
                        else:
                            answers[q_id] = value_to_label_map.get(selected_label, selected_label)
                        
                        # ✅ FIX: Show text box if "Other" option is selected (works in forms)
                        if selected_label and selected_label != '-- Select --':
                            selected_lower = str(selected_label).lower()
                            # Check if option contains "other" or "specify" keywords
                            if any(keyword in selected_lower for keyword in ['other', 'specify', 'please specify', 'describe']):
                                other_text = st.text_area(
                                    f"Please specify/describe:",
                                    key=f"q_{q_id}_other",
                                    height=80,
                                    placeholder="Enter your description here...",
                                    help="Provide additional details for your selection"
                                )
                                # Store the additional text with the answer
                                if other_text:
                                    answers[q_id] = f"{selected_label}: {other_text}"
                    
                    elif q_type == 'multiselect':
                        # Extract labels for multiselect
                        display_options = []
                        value_to_label_map = {}
                        
                        for opt in q_options:
                            if isinstance(opt, dict):
                                label = opt.get('label', opt.get('value', str(opt)))
                                value = opt.get('value', label)
                                display_options.append(label)
                                value_to_label_map[label] = value
                            else:
                                display_options.append(str(opt))
                                value_to_label_map[str(opt)] = opt
                        
                        selected_labels = st.multiselect(
                            q_text,
                            options=display_options,
                            key=f"q_{q_id}",
                            help=q_help
                        )
                        
                        answers[q_id] = [value_to_label_map.get(lbl, lbl) for lbl in selected_labels]
                    
                    elif q_type == 'number':
                        answers[q_id] = st.number_input(
                            q_text,
                            key=f"q_{q_id}",
                            help=q_help,
                            min_value=0
                        )
                    
                    elif q_type == 'rating' or q_type == 'rating_scale':
                        scale = question.get('scale', '1-5')
                        if '-' in scale:
                            try:
                                min_val, max_val = map(int, scale.split('-'))
                            except:
                                min_val, max_val = 1, 5
                        else:
                            min_val, max_val = 1, 5
                        
                        answers[q_id] = st.slider(
                            q_text,
                            min_value=min_val,
                            max_value=max_val,
                            key=f"q_{q_id}",
                            help=q_help
                        )
                    
                    else:  # Default to text
                        answers[q_id] = st.text_input(
                            q_text,
                            key=f"q_{q_id}",
                            help=q_help
                        )
            
            # Submit button
            submitted = st.form_submit_button(
                "✅ Submit Questionnaire & Create Asset Data", 
                type="primary", 
                use_container_width=True
            )
        
        # Process submission
        if submitted:
            st.session_state.questionnaire_answers = answers
            
            with st.spinner("⏳ Converting your answers to asset data format..."):
                try:
                    # Create ENHANCED asset_data with ALL questionnaire answers
                    asset_data = {
                        'asset_name': '',
                        'asset_type': '',  # Will be extracted from Q_ASSET_TYPE
                        'asset_owner': '',
                        'location': '',
                        'description': '',
                        
                        # 🆕 NEW: Store ALL questionnaire answers with full context
                        'questionnaire_answers': {},
                        
                        # 🆕 NEW: Store questionnaire metadata
                        'questionnaire_metadata': {
                            'asset_type_assessed': current_asset,
                            'questionnaire_title': questionnaire.get('questionnaire_title', 'Risk Assessment Questionnaire'),
                            'completed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'total_questions': sum(len(s.get('questions', [])) for s in questionnaire.get('sections', [])),
                            'total_answers': 0
                        },
                        
                        'threats_and_vulnerabilities': []
                    }
                    
                    answer_count = 0
                    
                    # Extract information from answers AND store ALL answers with context
                    for q_id, answer in answers.items():
                        if not answer or answer == '-- Select --':
                            continue
                        
                        answer_count += 1
                        
                        # Find the question to get full context
                        for section in questionnaire.get('sections', []):
                            for question in section.get('questions', []):
                                if question.get('question_id') == q_id:
                                    q_text = question.get('question_text', '').lower()
                                    
                                    # 🆕 NEW: Store answer with full question context
                                    asset_data['questionnaire_answers'][q_id] = {
                                        'question_text': question.get('question_text'),
                                        'answer': answer,
                                        'question_type': question.get('question_type'),
                                        'section': section.get('section_name'),
                                        'help_text': question.get('help_text', ''),
                                        'why_this_matters': question.get('why_this_matters', '')
                                    }
                                    
                                    # 🔧 FIX: Map to basic fields for backwards compatibility
                                    # Asset Name
                                    if any(word in q_text.lower() for word in ['name', 'title', 'called', 'identifier']) and 'type' not in q_text.lower() and 'owner' not in q_text.lower():
                                        if not asset_data['asset_name']:
                                            asset_data['asset_name'] = str(answer)
                                    
                                    # Asset Type
                                    elif any(word in q_text.lower() for word in ['type of asset', 'asset type', 'asset category', 'type', 'category']) or 'type' in q_id.lower() or 'category' in q_id.lower():
                                        if not asset_data['asset_type']:
                                            asset_data['asset_type'] = str(answer)
                                    
                                    # Asset Owner
                                    elif any(word in q_text for word in ['owner', 'responsible', 'managed by', 'contact']):
                                        if not asset_data['asset_owner']:
                                            asset_data['asset_owner'] = str(answer)
                                    
                                    # Location
                                    elif any(word in q_text for word in ['location', 'where', 'hosted', 'deployed', 'site']):
                                        if not asset_data['location']:
                                            asset_data['location'] = str(answer)
                                    
                                    # Description
                                    elif any(word in q_text for word in ['describe', 'description', 'what is', 'purpose', 'function']):
                                        if not asset_data['description']:
                                            asset_data['description'] = str(answer)
                                    
                                    break
                    
                    # Update answer count
                    asset_data['questionnaire_metadata']['total_answers'] = answer_count
                    
                    # Set defaults if not filled
                    if not asset_data['asset_name']:
                        asset_data['asset_name'] = f"New {current_asset}" if current_asset else "New Asset"
                    
                    # 🔧 FIX: Set asset_type default if not extracted from questionnaire
                    if not asset_data['asset_type']:
                        asset_data['asset_type'] = current_asset or 'Unknown Asset'
                    
                    # 🆕 NEW: Call Agent 0.5 to discover intelligent threats from questionnaire answers
                    st.info("ℹ️ **Agent 0.5 is analyzing your answers to discover specific threats...**")
                    
                    with st.spinner("🤖 Agent 0.5: Intelligent Threat Discovery..."):
                        try:
                            threat_discovery_result = execute_agent_with_retry(
                                run_threat_discovery,
                                "Agent 0.5: Threat Discovery",
                                asset_data=asset_data
                            )
                            
                            if 'error' in threat_discovery_result or not threat_discovery_result.get('threats_discovered'):
                                st.warning("⚠️ Agent 0.5 couldn't discover threats. Using placeholder.")
                                # Fallback to placeholder
                                asset_data['threats_and_vulnerabilities'] = [{
                                    'threat': f"Risk assessment required for {asset_data['asset_name']}",
                                    'risk_statement': f'Comprehensive risk assessment based on {answer_count} questionnaire responses',
                                    'vulnerabilities': [{
                                        'vulnerability': 'To be assessed by Agent 1',
                                        'description': f'Agent 1 will analyze {answer_count} questionnaire answers to identify specific threats and vulnerabilities'
                                    }]
                                }]
                            else:
                                # ✅ SUCCESS: Use discovered threats
                                discovered_threats = threat_discovery_result['threats_discovered']
                                
                                # Convert to threats_and_vulnerabilities format
                                asset_data['threats_and_vulnerabilities'] = []
                                for threat in discovered_threats:
                                    asset_data['threats_and_vulnerabilities'].append({
                                        'threat': threat.get('threat_name', 'Unknown Threat'),
                                        'threat_category': threat.get('threat_category', 'N/A'),
                                        'contextual_description': threat.get('contextual_description', ''),
                                        'risk_statement': threat.get('risk_statement', ''),
                                        'vulnerabilities': [
                                            {'vulnerability': vuln, 'description': vuln}
                                            for vuln in threat.get('vulnerabilities_identified', [])
                                        ],
                                        'evidence': threat.get('evidence_from_questionnaire', []),
                                        'threat_source': threat.get('threat_source', 'Agent 0.5')
                                    })
                                
                                # Store full discovery result for later use
                                asset_data['threat_discovery_result'] = threat_discovery_result
                                
                                st.success(f"✅ Agent 0.5 discovered {len(discovered_threats)} specific threats!")
                                
                        except Exception as e:
                            st.error(f"❌ Agent 0.5 error: {str(e)}")
                            # Fallback to placeholder
                            asset_data['threats_and_vulnerabilities'] = [{
                                'threat': f"Risk assessment required for {asset_data['asset_name']}",
                                'risk_statement': f'Comprehensive risk assessment based on {answer_count} questionnaire responses',
                                'vulnerabilities': [{
                                    'vulnerability': 'To be assessed by Agent 1',
                                    'description': f'Agent 1 will analyze {answer_count} questionnaire answers to identify specific threats and vulnerabilities'
                                }]
                            }]
                    
                    # Add to session state
                    st.session_state.sample_assets = [asset_data]
                    st.session_state.questionnaire_answers_stored = answers
                    # ✅ FIX: Clear any previous email questionnaire token (manual questionnaire has no token)
                    if 'loaded_questionnaire_token' in st.session_state:
                        del st.session_state.loaded_questionnaire_token
                    
                    st.success(f"✅ Asset data created: **{asset_data['asset_name']}**")
                    st.success(f"✅ Captured **{answer_count} detailed answers** from questionnaire!")
                    st.info("ℹ️ **Agent 1 will analyze all your answers to assess CIA impact!**")
                    
                    # Show what was captured
                    with st.expander("📄 View Complete Asset Data (with ALL Questionnaire Answers)"):
                        st.json(asset_data)
                    
                    # Show summary of captured data
                    with st.expander("📋 Summary of Captured Information"):
                        st.markdown("### Basic Asset Info:")
                        st.markdown(f"- **Name:** {asset_data['asset_name']}")
                        st.markdown(f"- **Type:** {asset_data['asset_type']}")
                        st.markdown(f"- **Owner:** {asset_data['asset_owner'] or 'Not specified'}")
                        st.markdown(f"- **Location:** {asset_data['location'] or 'Not specified'}")
                        
                        st.markdown(f"### Questionnaire Answers: {answer_count} captured")
                        for q_id, q_data in asset_data['questionnaire_answers'].items():
                            st.markdown(f"**Q:** {q_data['question_text']}")
                            st.markdown(f"**A:** {q_data['answer']}")
                            st.markdown("---")
                    
                    st.info("ℹ️ **Scroll down to 'Step 1: Upload Asset Data' to continue!**")
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error converting questionnaire: {str(e)}")
                    import traceback
                    with st.expander("View Error Details"):
                        st.code(traceback.format_exc())

    # 🔧 FIXED: Step 1 - Upload Asset Data (starts here, NO else:)
    st.markdown("---")
    st.header("1️⃣ Step 1: Upload Asset Data File (Alternative)")
    
    st.info("ℹ️ **Already have asset data?** Upload Excel or JSON file directly.")
    
    # 📧 NEW: Check Pending Questionnaires Section
    with st.expander("📧 Check Pending Questionnaires (Email Responses)", expanded=True):
        col_caption, col_refresh = st.columns([4, 1])
        with col_caption:
            st.caption("View questionnaires sent via email and load completed responses")
        with col_refresh:
            if st.button("🔄 Refresh", key="refresh_pending_q", help="Check for new completed questionnaires"):
                st.rerun()
        
        try:
            from email_sender import get_all_pending_questionnaires
            import sqlite3
            
            pending_list = get_all_pending_questionnaires()
            
            if not pending_list:
                st.info("ℹ️ No questionnaires sent yet. Use Agent 0 to generate and send questionnaires.")
            else:
                # Separate completed and pending - FIX: Case-insensitive comparison
                completed = [q for q in pending_list if q['status'].lower() == 'completed']
                pending = [q for q in pending_list if q['status'].lower() == 'pending']
                
                # 🔧 UPDATED: Separate questionnaires by type
                agent0_completed = [q for q in completed if q.get('questionnaire_type', 'Agent0') == 'Agent0']
                agent0_pending = [q for q in pending if q.get('questionnaire_type', 'Agent0') == 'Agent0']
                
                decision_completed = [q for q in completed if q.get('questionnaire_type', 'Agent0') in ['ACCEPT', 'TRANSFER', 'TERMINATE']]
                decision_pending = [q for q in pending if q.get('questionnaire_type', 'Agent0') in ['ACCEPT', 'TRANSFER', 'TERMINATE']]
                
                # 📋 Agent 0 Questionnaires Section
                st.markdown("### 📋 Agent 0 Questionnaires (Asset Data Collection)")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("✅ Completed", len(agent0_completed))
                with col2:
                    st.metric("⏳ Pending", len(agent0_pending))
                
                # Display Agent 0 completed questionnaires
                if agent0_completed:
                    st.success(f"✅ {len(agent0_completed)} Agent 0 Questionnaire(s) - Ready to Load")
                    
                    for q in agent0_completed:
                        col_info, col_action = st.columns([3, 1])
                        
                        with col_info:
                            st.markdown(f"**Asset:** {q['asset_name']}")
                            st.caption(f"📧 Sent to: {q['recipient_email']} | ⏰ Completed: {q.get('created_date', 'N/A')}")
                        
                        with col_action:
                            if st.button(f"📥 Load", key=f"load_{q['token']}", type="primary"):
                                with st.spinner("📥 Loading and analyzing questionnaire..."): 
                                    # Fetch answers from database
                                    conn = sqlite3.connect('database/risk_register.db')
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        SELECT answers, questions
                                        FROM pending_questionnaires
                                        WHERE token = ?
                                    """, (q['token'],))
                                    result = cursor.fetchone()
                                    conn.close()
                                    
                                    if result and result[0]:
                                        answers = json.loads(result[0])
                                        questions = json.loads(result[1])
                                        
                                        # 🔧 FIX: Ensure answers is a dict
                                        if isinstance(answers, str):
                                            answers = json.loads(answers)
                                        
                                        # ✅ FIX: Use EXACT same extraction logic as manual questionnaire (lines 1000-1050)
                                        asset_name = q['asset_name']
                                        asset_type = ''
                                        asset_owner = ''
                                        location = ''
                                        description = ''
                                        
                                        # Extract from answers using SAME logic as manual submission
                                        for q_id, q_data in answers.items():
                                            if isinstance(q_data, dict):
                                                q_text = q_data.get('question_text', '').lower()
                                                answer = q_data.get('answer', '')
                                                
                                                if not answer:  # Skip empty answers
                                                    continue
                                                
                                                # Asset Name - EXACT match from manual
                                                if any(word in q_text for word in ['name', 'title', 'called', 'identifier']) and 'type' not in q_text and 'owner' not in q_text:
                                                    if not asset_name or asset_name == q['asset_name']:
                                                        asset_name = str(answer)
                                                
                                                # Asset Type - EXACT match from manual
                                                elif any(word in q_text for word in ['type of asset', 'asset type', 'asset category', 'type', 'category']) or 'type' in q_id.lower() or 'category' in q_id.lower():
                                                    if not asset_type:
                                                        asset_type = str(answer)
                                                
                                                # Asset Owner - EXACT match from manual
                                                elif any(word in q_text for word in ['owner', 'responsible', 'managed by', 'contact']):
                                                    if not asset_owner:
                                                        asset_owner = str(answer)
                                                
                                                # Location - EXACT match from manual
                                                elif any(word in q_text for word in ['location', 'where', 'hosted', 'deployed', 'site']):
                                                    if not location:
                                                        location = str(answer)
                                                
                                                # Description - EXACT match from manual
                                                elif any(word in q_text for word in ['describe', 'description', 'what is', 'purpose', 'function']):
                                                    if not description:
                                                        description = str(answer)
                                        
                                        # Set defaults if not extracted (same as manual)
                                        if not asset_type:
                                            asset_type = 'Unknown'
                                        if not asset_owner:
                                            asset_owner = q['recipient_email']
                                        if not location:
                                            location = 'Remote'
                                        if not description:
                                            description = f"Asset assessed via email questionnaire"
                                        
                                        # Create asset_data from answers
                                        asset_data = {
                                            'asset_name': asset_name,
                                            'asset_type': asset_type,
                                            'asset_owner': asset_owner,
                                            'location': location,
                                            'description': description,
                                            'questionnaire_answers': answers,
                                            'questionnaire_metadata': {
                                                'source': 'email',
                                                'token': q['token'],
                                                'completed_date': q.get('created_date', 'N/A'),
                                                'total_answers': len(answers),
                                                'asset_type_assessed': asset_type  # ✅ FIX: Add asset_type for display
                                            },
                                            'threats_and_vulnerabilities': []
                                        }
                                        
                                        # 🤖 Run Agent 0.5 to discover threats
                                        st.info("🤖 Agent 0.5: Analyzing answers to discover threats...")
                                        
                                        try:
                                            threat_result = execute_agent_with_retry(
                                                run_threat_discovery,
                                                "Agent 0.5: Threat Discovery",
                                                asset_data=asset_data
                                            )
                                            
                                            if 'error' not in threat_result and threat_result.get('threats_discovered'):
                                                # Use discovered threats
                                                for threat in threat_result['threats_discovered']:
                                                    asset_data['threats_and_vulnerabilities'].append({
                                                        'threat': threat.get('threat_name', 'Unknown'),
                                                        'threat_category': threat.get('threat_category', 'N/A'),
                                                        'contextual_description': threat.get('contextual_description', ''),
                                                        'risk_statement': threat.get('risk_statement', ''),
                                                        'vulnerabilities': [
                                                            {'vulnerability': v, 'description': v}
                                                            for v in threat.get('vulnerabilities_identified', [])
                                                        ],
                                                        'evidence': threat.get('evidence_from_questionnaire', []),
                                                        'threat_source': 'Agent 0.5 (Email)'
                                                    })
                                                asset_data['threat_discovery_result'] = threat_result
                                                st.success(f"✅ Agent 0.5 discovered {len(threat_result['threats_discovered'])} threats!")
                                            else:
                                                # Fallback
                                                st.warning("⚠️ Agent 0.5 couldn't discover threats. Using placeholder.")
                                                asset_data['threats_and_vulnerabilities'] = [{
                                                    'threat': f"Risk assessment for {q['asset_name']}",
                                                    'risk_statement': 'Assessment based on email questionnaire',
                                                    'vulnerabilities': [{
                                                        'vulnerability': 'To be assessed by Agent 1',
                                                        'description': 'Agent 1 will analyze questionnaire answers'
                                                    }]
                                                }]
                                        except Exception as e:
                                            st.error(f"❌ Agent 0.5 error: {str(e)}")
                                            asset_data['threats_and_vulnerabilities'] = [{
                                                'threat': f"Risk assessment for {q['asset_name']}",
                                                'risk_statement': 'Assessment based on email questionnaire',
                                                'vulnerabilities': [{
                                                    'vulnerability': 'To be assessed by Agent 1',
                                                    'description': 'Agent 1 will analyze questionnaire answers'
                                                }]
                                            }]
                                        
                                        # Load into session state
                                        st.session_state.sample_assets = [asset_data]
                                        # ✅ FIX: Store questionnaire token for later removal
                                        st.session_state.loaded_questionnaire_token = q['token']
                                        st.success(f"✅ Loaded: {q['asset_name']}")
                                        st.info("📊 Scroll down to Step 2 to select and continue with Agent 1-4")

                # Display Agent 0 pending questionnaires
                if agent0_pending:
                    st.warning(f"⏳ {len(agent0_pending)} Agent 0 Questionnaire(s) - Waiting for Response")
                    
                    for q in agent0_pending:
                        st.markdown(f"**Asset:** {q['asset_name']}")
                        st.caption(f"📧 Sent to: {q['recipient_email']} | ⏰ Sent: {q.get('created_date', 'N/A')}")
                        st.caption(f"🔗 Token: {q['token']}")
                        st.markdown("---")
                
                st.markdown("---")
                
                # 🎯 Decision Questionnaires Section
                st.markdown("### 🎯 Decision Questionnaires (ACCEPT/TRANSFER/TERMINATE)")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("✅ Completed", len(decision_completed))
                with col2:
                    st.metric("⏳ Pending", len(decision_pending))
                
                # Display Decision completed questionnaires
                if decision_completed:
                    st.success(f"✅ {len(decision_completed)} Decision Questionnaire(s) - Ready to Process")
                    
                    for q in decision_completed:
                        col_info, col_action = st.columns([3, 1])
                        
                        with col_info:
                            decision_type = q.get('questionnaire_type', 'DECISION')
                            st.markdown(f"**Asset:** {q['asset_name']} - **{decision_type}**")
                            st.caption(f"📧 Sent to: {q['recipient_email']} | ⏰ Completed: {q.get('created_date', 'N/A')}")
                        
                        with col_action:
                            if q['questionnaire_type'] in ['ACCEPT', 'TRANSFER', 'TERMINATE']:
                                # 🆕 2-STEP WORKFLOW: Generate Form → Show Form → Save
                                form_key = f"email_form_{q['token']}"
                                
                                # STEP 1: Generate Form Button
                                if form_key not in st.session_state:
                                    if st.button(f"📋 Generate {q['questionnaire_type']} Form", key=f"gen_{q['token']}", type="primary"):
                                        with st.spinner(f"🤖 Generating {q['questionnaire_type']} form..."):
                                            try:
                                                conn = sqlite3.connect('database/risk_register.db')
                                                cursor = conn.cursor()
                                                cursor.execute("SELECT answers, questions, agent_results FROM pending_questionnaires WHERE token = ?", (q['token'],))
                                                result = cursor.fetchone()
                                                conn.close()
                                                
                                                if result and result[0]:
                                                    answers = json.loads(result[0])
                                                    questionnaire_structure = json.loads(result[1])
                                                    agent_results = json.loads(result[2]) if result[2] else None
                                                    
                                                    if isinstance(answers, str):
                                                        answers = json.loads(answers)
                                                    
                                                    if not agent_results:
                                                        st.error("❌ Agent results not found. Please run Agents 1-3 first.")
                                                    else:
                                                        threat_data = agent_results.get('threat_data', {})
                                                        
                                                        # Extract threat info correctly
                                                        threat_name = threat_data.get('threat', threat_data.get('threat_name', 'Unknown Threat'))
                                                        risk_rating = threat_data.get('risk_evaluation_rating', {}).get('rating', 0) if isinstance(threat_data.get('risk_evaluation_rating'), dict) else 0
                                                        residual_risk_value = 0
                                                        
                                                        # Try to get residual risk from agent_3
                                                        agent_3_results = agent_results.get('agent_3', {})
                                                        if 'threat_control_evaluation' in agent_3_results:
                                                            for ctrl in agent_3_results['threat_control_evaluation']:
                                                                if ctrl.get('threat') == threat_name:
                                                                    residual_risk_value = ctrl.get('residual_risk', {}).get('residual_risk_value', 0)
                                                                    break
                                                        
                                                        # Generate form based on type
                                                        if q['questionnaire_type'] == 'ACCEPT':
                                                            from phase2_risk_resolver.agents.agent_4_acceptance_form import generate_acceptance_form
                                                            
                                                            # ✅ FIX: Get actual risk_id from questionnaire or generate next available
                                                            actual_risk_id = 'RSK-001'  # Default
                                                            try:
                                                                # Try to get from questionnaire first
                                                                for section in questionnaire_structure.get('sections', []):
                                                                    for field in section.get('questions', section.get('fields', [])):
                                                                        if 'risk_id' in field.get('question_id', '').lower() or 'risk_id' in field.get('id', '').lower():
                                                                            actual_risk_id = field.get('value', 'RSK-001')
                                                                            break
                                                                
                                                                # If not found, generate next available from database
                                                                if actual_risk_id == 'RSK-001':
                                                                    conn_temp = sqlite3.connect('database/risk_register.db')
                                                                    cursor_temp = conn_temp.cursor()
                                                                    cursor_temp.execute("SELECT MAX(CAST(SUBSTR(risk_id, 5) AS INTEGER)) FROM risks WHERE risk_id LIKE 'RSK-%'")
                                                                    result_temp = cursor_temp.fetchone()
                                                                    next_num = (result_temp[0] or 0) + 1
                                                                    actual_risk_id = f"RSK-{next_num:03d}"
                                                                    conn_temp.close()
                                                            except:
                                                                actual_risk_id = 'RSK-001'
                                                            
                                                            # ✅ FIX: Get risk_category from Agent 2 results
                                                            selected_asset = agent_results.get('selected_asset', {'asset_name': q['asset_name'], 'asset_type': 'Unknown'})
                                                            risk_category = 'Security Risk'  # Default
                                                            try:
                                                                agent_2_results = agent_results.get('agent_2', {})
                                                                agent_2_threats = agent_2_results.get('threat_risk_quantification', [])
                                                                for t in agent_2_threats:
                                                                    if t.get('threat') == threat_name:
                                                                        risk_category = t.get('risk_category', selected_asset.get('asset_type', 'Security Risk'))
                                                                        break
                                                            except:
                                                                risk_category = selected_asset.get('asset_type', 'Security Risk')
                                                            
                                                            risk_context = {
                                                                'risk_id': actual_risk_id,
                                                                'risk_category': risk_category,
                                                                'asset_name': q['asset_name'],
                                                                'threat_name': threat_name,
                                                                'inherent_risk_rating': risk_rating,
                                                                'residual_risk_rating': residual_risk_value,
                                                                'control_gaps': threat_data.get('control_gaps', [])
                                                            }
                                                            form = generate_acceptance_form(risk_context, answers, questionnaire_structure, api_key)
                                                        elif q['questionnaire_type'] == 'TRANSFER':
                                                            from phase2_risk_resolver.agents.agent_4_transfer_form import generate_transfer_form
                                                            risk_context = {
                                                                'risk_id': 'RSK-001',
                                                                'asset_name': q['asset_name'],
                                                                'threat_name': threat_name
                                                            }
                                                            form = generate_transfer_form(risk_context, answers, questionnaire_structure, api_key)
                                                        elif q['questionnaire_type'] == 'TERMINATE':
                                                            from phase2_risk_resolver.agents.agent_4_terminate_form import generate_terminate_form
                                                            risk_context = {
                                                                'risk_id': 'RSK-001',
                                                                'asset_name': q['asset_name'],
                                                                'threat_name': threat_name
                                                            }
                                                            form = generate_terminate_form(risk_context, answers, questionnaire_structure, api_key)
                                                        
                                                        # Store form and data in session state
                                                        st.session_state[form_key] = {
                                                            'form': form,
                                                            'agent_results': agent_results,
                                                            'questionnaire_type': q['questionnaire_type']
                                                        }
                                                        st.success(f"✅ {q['questionnaire_type']} Form Generated!")
                                                        st.rerun()
                                                else:
                                                    st.error("❌ No answers found")
                                            except Exception as e:
                                                st.error(f"❌ Form generation failed: {str(e)}")
                                                import traceback
                                                with st.expander("Debug"):
                                                    st.code(traceback.format_exc())
                                
                                # STEP 2: Display Form (SAME AS MANUAL WORKFLOW)
                                if form_key in st.session_state:
                                    form_data = st.session_state[form_key]
                                    form = form_data['form']
                                    agent_results = form_data['agent_results']
                                    q_type = form_data['questionnaire_type']
                        
                        # BREAK OUT OF COLUMNS - Display form full-width
                        for q in decision_completed:
                            form_key = f"email_form_{q['token']}"
                            if form_key in st.session_state:
                                form_data = st.session_state[form_key]
                                form = form_data['form']
                                agent_results = form_data['agent_results']
                                q_type = form_data['questionnaire_type']
                                
                                st.markdown("---")
                                st.success(f"✅ {q_type} Form Generated - Review Below")
                                
                                # Clean HTML entities
                                import html
                                def clean_html_recursive(obj):
                                    if isinstance(obj, str):
                                        return html.unescape(obj)
                                    elif isinstance(obj, dict):
                                        return {k: clean_html_recursive(v) for k, v in obj.items()}
                                    elif isinstance(obj, list):
                                        return [clean_html_recursive(item) for item in obj]
                                    return obj
                                
                                form = clean_html_recursive(form)
                                
                                # Display form full-width
                                st.markdown(f"## 📋 {q_type} Form")
                                with st.expander(f"📄 View Details", expanded=True):
                                        emoji_map = {'metadata': '📋', 'risk_context': '⚠️', 'engagement_project': '🏢', 
                                                     'compensating_controls': '🛡️', 'justification': '📝', 
                                                     'approvals': '✅', 'signoff': '✍️', 'transfer_details': '🔄',
                                                     'third_party_information': '🏢', 'termination_details': '🚫'}
                                        
                                        st.markdown(f"### 📋 {q_type} Form")
                                        st.markdown("---")
                                        
                                        for key, value in form.items():
                                            emoji = emoji_map.get(key, '📌')
                                            section_title = key.replace('_', ' ').title()
                                            
                                            if key == 'metadata':
                                                if isinstance(value, dict):
                                                    for k, v in value.items():
                                                        st.write(f"**{k.replace('_', ' ').title()}:** {v}")
                                                continue
                                            
                                            st.markdown(f"### {emoji} {section_title}")
                                            
                                            def display_value(k, v):
                                                field_name = k.replace('_', ' ').title()
                                                if isinstance(v, dict):
                                                    st.markdown(f"**{field_name}:**")
                                                    for dk, dv in v.items():
                                                        st.write(f"  • **{dk.replace('_', ' ').title()}:** {dv}")
                                                elif isinstance(v, list) and v and isinstance(v[0], dict):
                                                    st.markdown(f"**{field_name}:**")
                                                    for idx, item in enumerate(v, 1):
                                                        label = item.get('name') or item.get('label') or item.get('gap_description') or item.get('control_name') or item.get('description') or f"Item {idx}"
                                                        if len(str(label)) > 50:
                                                            label = str(label)[:50] + "..."
                                                        with st.expander(f"🔹 {label}", expanded=False):
                                                            for ik, iv in item.items():
                                                                st.write(f"**{ik.replace('_', ' ').title()}:** {iv}")
                                                elif isinstance(v, list):
                                                    st.write(f"**{field_name}:** {', '.join(str(x) for x in v)}")
                                                else:
                                                    st.write(f"**{field_name}:** {v}")
                                            
                                            if isinstance(value, dict):
                                                for k, v in value.items():
                                                    display_value(k, v)
                                            elif isinstance(value, list):
                                                for item in value:
                                                    if isinstance(item, dict):
                                                        for ik, iv in item.items():
                                                            display_value(ik, iv)
                                                        st.write("---")
                                                    else:
                                                        st.write(f"- {item}")
                                            else:
                                                st.write(value)
                                        
                                        with st.expander("📄 Raw JSON", expanded=False):
                                            st.json(form)
                                
                                # STEP 2.5: Regenerate Form Button
                                col_save, col_regen = st.columns([3, 1])
                                with col_regen:
                                    if st.button(f"🔄 Regenerate", key=f"regen_{q['token']}", help="Regenerate form with updated data"):
                                        # Clear cached form
                                        if form_key in st.session_state:
                                            del st.session_state[form_key]
                                        st.success("✅ Form cleared! Click 'Generate Form' again.")
                                        st.rerun()
                                
                                # STEP 3: Save Button (only after form is shown)
                                with col_save:
                                    save_button = st.button(f"💾 Save to Risk Register", key=f"save_{q['token']}", type="primary", use_container_width=True)
                                
                                if save_button:
                                    with st.spinner("💾 Saving to Risk Register..."):
                                            try:
                                                # Retrieve answers from database
                                                conn = sqlite3.connect('database/risk_register.db')
                                                cursor = conn.cursor()
                                                cursor.execute("SELECT answers FROM pending_questionnaires WHERE token = ?", (q['token'],))
                                                answers_row = cursor.fetchone()
                                                conn.close()
                                                answers = json.loads(answers_row[0]) if answers_row and answers_row[0] else {}
                                                
                                                agent_1_results = agent_results.get('agent_1', {})
                                                agent_2_results = agent_results.get('agent_2', {})
                                                agent_3_results = agent_results.get('agent_3', {})
                                                selected_asset = agent_results.get('selected_asset', {'asset_name': q['asset_name']})
                                                threat_data = agent_results.get('threat_data', {})
                                                
                                                # Get threat name for filtering
                                                threat_name = threat_data.get('threat', threat_data.get('threat_name', 'Unknown Threat'))
                                                
                                                # ✅ FIX: Extract ORIGINAL Agent 2 threat data (not reformatted Agent 4 data)
                                                agent_2_threats = agent_2_results.get('threat_risk_quantification', [])
                                                original_threat = next((t for t in agent_2_threats if t.get('threat') == threat_name), threat_data)
                                                
                                                # Filter Agent 3 results to match this specific threat
                                                filtered_agent_3 = {'threat_control_evaluation': []}
                                                if 'threat_control_evaluation' in agent_3_results:
                                                    for ctrl in agent_3_results['threat_control_evaluation']:
                                                        if ctrl.get('threat') == threat_name:
                                                            filtered_agent_3['threat_control_evaluation'] = [ctrl]
                                                            break
                                                
                                                # Prepare decision data with form (same as manual workflow)
                                                if q_type == 'ACCEPT':
                                                    decision_data = {
                                                        'management_decision': 'ACCEPT',
                                                        'acceptance_form': form,
                                                        'rtp_answers': answers,
                                                        'completed': True
                                                    }
                                                elif q_type == 'TRANSFER':
                                                    decision_data = {
                                                        'management_decision': 'TRANSFER',
                                                        'transfer_form': form,
                                                        'rtp_answers': answers,
                                                        'completed': True
                                                    }
                                                elif q_type == 'TERMINATE':
                                                    decision_data = {
                                                        'management_decision': 'TERMINATE',
                                                        'terminate_form': form,
                                                        'rtp_answers': answers,
                                                        'completed': True
                                                    }
                                                
                                                from phase2_risk_resolver.database.save_to_register import save_assessment_to_risk_register
                                                filtered_agent_2 = {**agent_2_results, 'threat_risk_quantification': [original_threat]}
                                                risk_ids = save_assessment_to_risk_register(
                                                    asset_data=selected_asset,
                                                    agent_1_results=agent_1_results,
                                                    agent_2_results=filtered_agent_2,
                                                    agent_3_results=filtered_agent_3,
                                                    agent_4_results=decision_data
                                                )
                                                
                                                if risk_ids and len(risk_ids) > 0:
                                                    st.success(f"✅ Saved! Risk ID: {risk_ids[0]}")
                                                    # Update questionnaire status to 'saved' so it disappears from pending list
                                                    conn = sqlite3.connect('database/risk_register.db')
                                                    cursor = conn.cursor()
                                                    cursor.execute("UPDATE pending_questionnaires SET status = 'saved' WHERE token = ?", (q['token'],))
                                                    conn.commit()
                                                    conn.close()
                                                    st.balloons()
                                                    time.sleep(1)
                                                    st.rerun()
                                                else:
                                                    st.error("❌ Save returned no Risk IDs")
                                            except Exception as e:
                                                st.error(f"❌ Save failed: {str(e)}")
                                                import traceback
                                                with st.expander("Debug"):
                                                    st.code(traceback.format_exc())
                            elif q['questionnaire_type'] != 'Agent0':
                                # Skip unknown types silently
                                continue
                        
                        st.markdown("---")
                
                # Display Decision pending questionnaires
                if decision_pending:
                    st.warning(f"⏳ {len(decision_pending)} Decision Questionnaire(s) - Waiting for Response")
                    
                    for q in decision_pending:
                        decision_type = q.get('questionnaire_type', 'DECISION')
                        st.markdown(f"**Asset:** {q['asset_name']} - **{decision_type}**")
                        st.caption(f"📧 Sent to: {q['recipient_email']} | ⏰ Sent: {q.get('created_date', 'N/A')}")
                        st.caption(f"🔗 Token: {q['token']}")
                        st.markdown("---")
        
        except Exception as e:
            st.error(f"❌ Error loading questionnaires: {str(e)}")
    
    uploaded_asset_file = st.file_uploader(
        "Upload Asset Data",
        type=['xlsx', 'xls', 'json'],
        help="Upload Excel or JSON file with asset information"
    )
    
    if uploaded_asset_file:
        file_type = uploaded_asset_file.name.split('.')[-1].lower()
        
        if file_type in ['xlsx', 'xls']:
            assets = extract_assets_from_excel(uploaded_asset_file)
        elif file_type == 'json':
            assets = extract_assets_from_json(uploaded_asset_file)
        else:
            st.error("Unsupported file format")
            assets = []
        
        if assets:
            st.session_state.sample_assets = assets
            st.success(f"✅ Loaded {len(assets)} asset(s)")
    
    # 🔧 FIXED: Step 2 - Select Asset (defines selected_asset variable)
    if st.session_state.sample_assets:
        st.markdown("---")
        
        # 🔧 FIX: Auto-update selected_asset from sample_assets on page load
        if st.session_state.sample_assets and len(st.session_state.sample_assets) > 0:
            first_asset = st.session_state.sample_assets[0]
            # Update selected_asset to match current sample_assets data
            if not st.session_state.selected_asset or st.session_state.selected_asset.get('asset_name') != first_asset.get('asset_name'):
                st.session_state.selected_asset = first_asset
        
        # 📋 NEW: Display Questionnaire Answers Summary (if available)
        if st.session_state.sample_assets and len(st.session_state.sample_assets) > 0:
            first_asset = st.session_state.sample_assets[0]
            if 'questionnaire_answers' in first_asset and first_asset['questionnaire_answers']:
                st.success("✅ Questionnaire Completed - Review Your Answers")
                
                with st.expander("📋 View Questionnaire Answers", expanded=False):
                    answers = first_asset['questionnaire_answers']
                    
                    # 🔧 FIX: Ensure answers is a dict (might be JSON string from database)
                    if isinstance(answers, str):
                        answers = json.loads(answers)
                    
                    metadata = first_asset.get('questionnaire_metadata', {})
                    
                    # Summary metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("<p style='font-size:14px; margin-bottom:0;'>Questions Answered</p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:20px; font-weight:bold; margin-top:0;'>{metadata.get('total_answers', len(answers))}</p>", unsafe_allow_html=True)
                    with col2:
                        st.markdown("<p style='font-size:14px; margin-bottom:0;'>Asset Type</p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:20px; font-weight:bold; margin-top:0;'>{metadata.get('asset_type_assessed', 'N/A')}</p>", unsafe_allow_html=True)
                    with col3:
                        st.markdown("<p style='font-size:14px; margin-bottom:0;'>Completed</p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:20px; font-weight:bold; margin-top:0;'>{metadata.get('completed_date', 'N/A')[:10] if metadata.get('completed_date') else 'N/A'}</p>", unsafe_allow_html=True)
                    
                    st.markdown("---")
                    st.markdown("### Your Answers:")
                    
                    # 🔧 FIX: Handle both formats - simple dict {"Q1": "answer"} OR nested dict {"Q1": {"question_text": "...", "answer": "..."}}
                    if answers and isinstance(answers, dict):
                        # Check format by looking at first value
                        first_value = next(iter(answers.values()), None)
                        
                        if isinstance(first_value, dict):
                            # NEW FORMAT: Nested dict with metadata
                            current_section = None
                            for q_id, q_data in answers.items():
                                section = q_data.get('section', 'General')
                                
                                if section != current_section:
                                    st.markdown(f"#### 📌 {section}")
                                    current_section = section
                                
                                question_text = q_data.get('question_text', 'Question')
                                answer = q_data.get('answer', 'N/A')
                                
                                if isinstance(answer, list):
                                    answer_display = ', '.join(str(a) for a in answer) if answer else 'None selected'
                                else:
                                    answer_display = str(answer) if answer else 'Not answered'
                                
                                st.markdown(f"**Q:** {question_text}")
                                st.info(f"**A:** {answer_display}")
                                st.markdown("")  # Spacing
                        else:
                            # OLD FORMAT: Simple key-value pairs from email questionnaire
                            for q_id, answer in answers.items():
                                # Clean up question ID for display
                                question_display = q_id.replace('Q_', '').replace('_', ' ').title()
                                
                                if isinstance(answer, list):
                                    answer_display = ', '.join(str(a) for a in answer) if answer else 'None selected'
                                else:
                                    answer_display = str(answer) if answer else 'Not answered'
                                
                                st.markdown(f"**{question_display}:**")
                                st.info(answer_display)
                                st.markdown("")  # Spacing
                    else:
                        st.warning("No answers found")
        
        st.markdown("---")
        st.subheader("📋 Step 2: Select Asset for Assessment")
        
        asset_names = [asset['asset_name'] for asset in st.session_state.sample_assets]
        
        selected_asset_name = st.selectbox(
            "Choose an asset:",
            options=asset_names,
            index=0
        )
        
        selected_asset = next((a for a in st.session_state.sample_assets if a['asset_name'] == selected_asset_name), None)
        
        # 🔧 FIX: Store selected_asset in session state so it's available throughout the workflow
        st.session_state.selected_asset = selected_asset
        
        if selected_asset:
            # Display asset details
            with st.expander("📋 Asset Details", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Name:** {selected_asset['asset_name']}")
                    st.markdown(f"**Type:** {selected_asset['asset_type']}")
                    st.markdown(f"**Owner:** {selected_asset['asset_owner']}")
                
                with col2:
                    st.markdown(f"**Location:** {selected_asset['location']}")
                    # More accurate threat count
                    if 'questionnaire_answers' in selected_asset:
                        st.markdown(f"**Questionnaire Responses:** {len(selected_asset.get('questionnaire_answers', {}))}")
                    else:
                        st.markdown(f"**Threats:** {len(selected_asset.get('threats_and_vulnerabilities', []))}")
                
                if selected_asset.get('threats_and_vulnerabilities'):
                    st.markdown("**Threats & Vulnerabilities:**")
                    
                    # Check if this is from Agent 0.5 (has contextual_description)
                    has_contextual = any(t.get('contextual_description') for t in selected_asset['threats_and_vulnerabilities'])
                    
                    for idx, threat in enumerate(selected_asset['threats_and_vulnerabilities'], 1):
                        threat_name = threat['threat']
                        
                        # Make placeholder text more descriptive
                        if threat_name == 'To be assessed by agents':
                            threat_name = f"Security Assessment for {selected_asset['asset_type']}"
                        
                        # 🆕 NEW: Show contextual description if available (from Agent 0.5)
                        if has_contextual and threat.get('contextual_description'):
                            with st.expander(f"⚠️ Threat {idx}: {threat_name}", expanded=(idx == 1)):
                                # Contextual description
                                st.info(threat['contextual_description'])
                                
                                # Risk statement
                                if threat.get('risk_statement'):
                                    st.markdown("**Risk Statement:**")
                                    st.warning(threat['risk_statement'])
                                
                                # Vulnerabilities
                                if threat.get('vulnerabilities'):
                                    st.markdown("**Vulnerabilities Identified:**")
                                    for vuln in threat['vulnerabilities']:
                                        if isinstance(vuln, dict):
                                            st.markdown(f"- {vuln.get('vulnerability', 'N/A')}")
                                        else:
                                            st.markdown(f"- {vuln}")
                                
                                # Evidence from questionnaire
                                if threat.get('evidence'):
                                    st.markdown("**Evidence from Questionnaire:**")
                                    for evidence in threat['evidence'][:3]:  # Show first 3
                                        st.caption(f"📋 {evidence}")
                                
                                # Source
                                if threat.get('threat_source'):
                                    st.caption(f"📚 Source: {threat['threat_source']}")
                        else:
                            # Old format (placeholder)
                            st.markdown(f"- **{threat_name}**")
                            
                            # Show risk statement only if it's descriptive
                            risk_stmt = threat.get('risk_statement', '')
                            if risk_stmt and 'based on' not in risk_stmt.lower():
                                st.markdown(f"  - *Risk Statement:* {risk_stmt}")
                            elif 'questionnaire_answers' in selected_asset:
                                num_answers = len(selected_asset.get('questionnaire_answers', {}))
                                st.markdown(f"  - *Assessment Basis:* {num_answers} questionnaire responses analyzed")
                            
                            st.markdown(f"  - *Vulnerabilities:* {len(threat.get('vulnerabilities', []))} identified")
            
            # 🔧 FIXED: Step 3 - Run Assessments
            st.markdown("---")
            st.subheader("▶️ Step 3: Run Complete Risk Assessment Pipeline")
            
            # Clear individual agent buttons
            with st.expander("🗑️ Clear Individual Agent Results", expanded=False):
                st.caption("Clear specific agent results to re-run them")
                
                col_clear1, col_clear2, col_clear3, col_clear4, col_clear5 = st.columns(5)
                
                with col_clear1:
                    if st.button("🗑️ Clear Agent 1", use_container_width=True, disabled=not st.session_state.impact_result):
                        st.session_state.impact_result = None
                        st.success("✅ Agent 1 cleared")
                        st.rerun()
                
                with col_clear2:
                    if st.button("🗑️ Clear Agent 2", use_container_width=True, disabled=not st.session_state.risk_result):
                        st.session_state.risk_result = None
                        st.success("✅ Agent 2 cleared")
                        st.rerun()
                
                with col_clear3:
                    if st.button("🗑️ Clear Agent 3", use_container_width=True, disabled=not st.session_state.control_result):
                        st.session_state.control_result = None
                        st.success("✅ Agent 3 cleared")
                        st.rerun()
                
                with col_clear4:
                    if st.button("🗑️ Clear Agent 4", use_container_width=True, disabled=not st.session_state.decision_result):
                        st.session_state.decision_result = None
                        # Also clear Agent 4 workflow state
                        if 'treatment_decision' in st.session_state:
                            del st.session_state.treatment_decision
                        if 'treatment_plan' in st.session_state:
                            del st.session_state.treatment_plan
                        if 'rtp_answers' in st.session_state:
                            del st.session_state.rtp_answers
                        if 'acceptance_questionnaire' in st.session_state:
                            del st.session_state.acceptance_questionnaire
                        st.success("✅ Agent 4 cleared (including workflow)")
                        st.rerun()
                
                with col_clear5:
                    if st.button("🗑️ Clear Database", use_container_width=True, disabled=not st.session_state.output_result):
                        st.session_state.output_result = None
                        st.success("✅ Database save cleared")
                        st.rerun()
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            # Agent 1: Impact Assessment with Auto-Retry
            with col1:
                if st.button("🔍 Agent 1\nImpact", type="primary", use_container_width=True):
                    with st.spinner("🔍 Agent 1 discovering methodology..."):
                        result = execute_agent_with_retry(
                            run_impact_assessment,
                            "Agent 1: Impact Assessment",
                            asset_data=selected_asset
                        )
                        st.session_state.impact_result = result
                        if 'error' not in result:
                            st.success("✅ Done!")
                            # ✅ AUTO-SAVE SESSION
                            auto_save_session()
                        st.rerun()
            
            # Agent 2: Risk Quantification with Auto-Retry
            with col2:
                if st.button("📊 Agent 2\nRisk", type="primary", use_container_width=True, 
                            disabled=not st.session_state.impact_result):
                    with st.spinner("📊 Agent 2 quantifying risk..."):
                        result = execute_agent_with_retry(
                            run_risk_quantification,
                            "Agent 2: Risk Quantification",
                            asset_data=selected_asset,
                            impact_results=st.session_state.impact_result
                        )
                        st.session_state.risk_result = result
                        if 'error' not in result:
                            st.success("✅ Done!")
                            # ✅ AUTO-SAVE SESSION
                            auto_save_session()
                        st.rerun()
            
            # Agent 3: Control Discovery with Auto-Retry
            with col3:
                if st.button("🛡️ Agent 3\nControls", type="primary", use_container_width=True,
                            disabled=not st.session_state.risk_result):
                    with st.spinner("🛡️ Agent 3 discovering controls..."):
                        result = execute_agent_with_retry(
                            run_control_discovery,
                            "Agent 3: Control Discovery",
                            asset_data=selected_asset,
                            impact_results=st.session_state.impact_result,
                            risk_results=st.session_state.risk_result
                        )
                        st.session_state.control_result = result
                        if 'error' not in result:
                            st.success("✅ Done!")
                            # ✅ AUTO-SAVE SESSION
                            auto_save_session()
                        st.rerun()
            
            # Agent 4: Risk Decision with Auto-Retry
            with col4:
                if st.button("🎯 Agent 4\nDecision", type="primary", use_container_width=True,
                            disabled=not st.session_state.control_result):
                    # Clear previous Agent 4 workflow state
                    if 'treatment_decision' in st.session_state:
                        del st.session_state.treatment_decision
                    if 'treatment_plan' in st.session_state:
                        del st.session_state.treatment_plan
                    if 'rtp_answers' in st.session_state:
                        del st.session_state.rtp_answers
                    
                    with st.spinner("🎯 Agent 4 making decisions..."):
                        result = execute_agent_with_retry(
                            run_risk_decision,
                            "Agent 4: Risk Decision",
                            asset_data=selected_asset,
                            impact_results=st.session_state.impact_result,
                            risk_results=st.session_state.risk_result,
                            control_results=st.session_state.control_result
                        )
                        st.session_state.decision_result = result
                        if 'error' not in result:
                            st.success("✅ Done!")
                            # ✅ AUTO-SAVE SESSION
                            auto_save_session()
                        st.rerun()
            
            
            # Display Results
            st.markdown("---")
            st.markdown("## 📊 Assessment Results")
            
            # Show progress bar
            progress = sum([
                1 if st.session_state.impact_result else 0,  # Changed!
                1 if st.session_state.risk_result else 0,
                1 if st.session_state.control_result else 0,
                1 if st.session_state.decision_result else 0,
                1 if st.session_state.output_result else 0  # Changed!
            ]) / 5
            
            st.progress(progress)
            st.caption(f"Progress: {int(progress * 100)}% complete")
            
            # 🔧 FIXED: Tabs section (with corrected variable names)
            if any([st.session_state.impact_result, st.session_state.risk_result, 
                    st.session_state.control_result, st.session_state.decision_result,
                    st.session_state.output_result]):
                
                tab1, tab2, tab3, tab4 = st.tabs([
                    "🔍 Agent 1: Impact",
                    "📊 Agent 2: Risk", 
                    "🛡️ Agent 3: Controls",
                    "🎯 Agent 4: Decision"
                ])
                
                # Agent 1 Results Tab
                with tab1:
                    if st.session_state.impact_result:
                        result = st.session_state.impact_result
                        
                        # ✅ NEW: Display Asset-Level CIA First (Maximum across all threats)
                        if 'asset_cia_ratings' in result:
                            st.markdown("### 🏛️ Asset-Level CIA Ratings (Maximum Across All Threats)")
                            st.caption("💡 These are the maximum CIA values across all threats, used for Asset Business Value calculation")
                            
                            asset_cia = result['asset_cia_ratings']
                            
                            col_c, col_i, col_a = st.columns(3)
                            
                            with col_c:
                                conf = asset_cia.get('confidentiality', {})
                                conf_rating = conf.get('rating', 'N/A')
                                conf_numeric = conf.get('numeric_value', 0)
                                st.metric("🔐 Confidentiality (Asset)", conf_rating, delta="🔴" if conf_numeric >= 4 else "🟡" if conf_numeric >= 3 else "🟢")
                                with st.expander("💭 Reasoning"):
                                    st.write(conf.get('reasoning', 'Maximum value across all threats'))
                            
                            with col_i:
                                integ = asset_cia.get('integrity', {})
                                integ_rating = integ.get('rating', 'N/A')
                                integ_numeric = integ.get('numeric_value', 0)
                                st.metric("✅ Integrity (Asset)", integ_rating, delta="🔴" if integ_numeric >= 4 else "🟡" if integ_numeric >= 3 else "🟢")
                                with st.expander("💭 Reasoning"):
                                    st.write(integ.get('reasoning', 'Maximum value across all threats'))
                            
                            with col_a:
                                avail = asset_cia.get('availability', {})
                                avail_rating = avail.get('rating', 'N/A')
                                avail_numeric = avail.get('numeric_value', 0)
                                st.metric("⚡ Availability (Asset)", avail_rating, delta="🔴" if avail_numeric >= 4 else "🟡" if avail_numeric >= 3 else "🟢")
                                with st.expander("💭 Reasoning"):
                                    st.write(avail.get('reasoning', 'Maximum value across all threats'))
                            
                            st.markdown("---")
                        
                        # 🔧 UPDATED: Per-Threat CIA (show all threats)
                        st.markdown("### ⚠️ Per-Threat CIA Ratings")
                        st.caption("💡 CIA ratings calculated for each individual threat")
                        
                        threat_analysis = result.get('threat_analysis', [])
                        if threat_analysis and len(threat_analysis) > 0:
                            for threat_idx, threat_data in enumerate(threat_analysis, 1):
                                threat_name = threat_data.get('threat_name', f'Threat {threat_idx}')
                                
                                with st.expander(f"⚠️ Threat {threat_idx}: {threat_name}", expanded=(threat_idx == 1)):
                                    impact = threat_data.get('impact_assessment', {})
                                    
                                    col_c, col_i, col_a = st.columns(3)
                                    
                                    with col_c:
                                        conf = impact.get('confidentiality', {})
                                        conf_rating = conf.get('rating', 'N/A')
                                        conf_numeric = conf.get('numeric_value', 0)
                                        st.metric("Confidentiality", conf_rating, delta="🔴" if conf_numeric >= 4 else "🟡" if conf_numeric >= 3 else "🟢")
                                        with st.expander("💭 Reasoning"):
                                            st.write(conf.get('reasoning', 'No reasoning provided'))
                                    
                                    with col_i:
                                        integ = impact.get('integrity', {})
                                        integ_rating = integ.get('rating', 'N/A')
                                        integ_numeric = integ.get('numeric_value', 0)
                                        st.metric("Integrity", integ_rating, delta="🔴" if integ_numeric >= 4 else "🟡" if integ_numeric >= 3 else "🟢")
                                        with st.expander("💭 Reasoning"):
                                            st.write(integ.get('reasoning', 'No reasoning provided'))
                                    
                                    with col_a:
                                        avail = impact.get('availability', {})
                                        avail_rating = avail.get('rating', 'N/A')
                                        avail_numeric = avail.get('numeric_value', 0)
                                        st.metric("Availability", avail_rating, delta="🔴" if avail_numeric >= 4 else "🟡" if avail_numeric >= 3 else "🟢")
                                        with st.expander("💭 Reasoning"):
                                            st.write(avail.get('reasoning', 'No reasoning provided'))
                                    
                                    # Overall impact for this threat
                                    overall_calc = threat_data.get('overall_impact_calculation', {})
                                    if overall_calc:
                                        st.markdown("**Overall Impact (This Threat):**")
                                        overall_impact = overall_calc.get('overall_impact', 'N/A')
                                        overall_impact_numeric = overall_calc.get('overall_impact_numeric', None)
                                        
                                        if overall_impact_numeric:
                                            display_value = f"{overall_impact_numeric} - {overall_impact}" if isinstance(overall_impact, str) and str(overall_impact_numeric) not in overall_impact else str(overall_impact)
                                        else:
                                            display_value = str(overall_impact)
                                        
                                        delta = "🔴" if overall_impact_numeric and overall_impact_numeric >= 4 else "🟡" if overall_impact_numeric and overall_impact_numeric >= 3 else "🟢"
                                        st.metric("Overall Impact", display_value, delta=delta)
                        else:
                            st.warning("⚠️ No threat analysis found")
                        
                        st.markdown("---")
                        st.markdown("### 💰 Asset Valuation & Classification")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("#### 💰 Asset Business Value")
                            if 'asset_business_value' in result:
                                business_value = result['asset_business_value']
                                if isinstance(business_value, dict):
                                    bv_rating = business_value.get('business_value_rating', 'N/A')
                                    bv_cia_combo = business_value.get('cia_combination', 'N/A')
                                    bv_reasoning = business_value.get('reasoning', 'No reasoning provided')
                                    bv_method = business_value.get('calculation_method', 'Unknown')
                                    bv_source = business_value.get('source_reference', 'Unknown')
                                else:
                                    bv_rating = str(business_value)
                                    bv_cia_combo = 'N/A'
                                    bv_reasoning = 'No reasoning provided'
                                    bv_method = 'Unknown'
                                    bv_source = 'Unknown'
                                
                                # Color based on rating level
                                bv_lower = bv_rating.lower()
                                if 'very high' in bv_lower or 'critical' in bv_lower or 'extreme' in bv_lower:
                                    color = "🔴"
                                elif 'high' in bv_lower:
                                    color = "🔴"
                                elif 'medium' in bv_lower or 'moderate' in bv_lower:
                                    color = "🔴"
                                else:
                                    color = "🔴"
                                
                                st.metric("Business Value", bv_rating, delta=color)
                                st.caption(f"📊 **Calculated from CIA:** {bv_cia_combo}")
                                
                                with st.expander("📊 Calculation Details"):
                                    st.markdown(f"**Method:** {bv_method}")
                                    st.markdown(f"**Source:** {bv_source}")
                                    st.markdown(f"**Reasoning:** {bv_reasoning}")
                            else:
                                st.info("ℹ️ Business Value not calculated")
                        
                        with col2:
                            st.markdown("#### 🎯 Asset Criticality Classification")
                            if 'asset_criticality' in result:
                                criticality = result['asset_criticality']
                                if isinstance(criticality, dict):
                                    crit_class = criticality.get('criticality_classification', 'N/A')
                                    crit_bv_input = criticality.get('business_value_input', 'N/A')
                                    crit_reasoning = criticality.get('reasoning', 'No reasoning provided')
                                    crit_method = criticality.get('calculation_method', 'Unknown')
                                    crit_source = criticality.get('source_reference', 'Unknown')
                                else:
                                    crit_class = str(criticality)
                                    crit_bv_input = 'N/A'
                                    crit_reasoning = 'No reasoning provided'
                                    crit_method = 'Unknown'
                                    crit_source = 'Unknown'
                                
                                # Color based on criticality level
                                crit_lower = crit_class.lower()
                                if 'very high' in crit_lower or 'critical' in crit_lower or 'extreme' in crit_lower:
                                    color = "🔴"
                                elif 'high' in crit_lower:
                                    color = "🔴"
                                elif 'medium' in crit_lower or 'moderate' in crit_lower:
                                    color = "🔴"
                                else:
                                    color = "🔴"
                                
                                st.metric("Criticality", crit_class, delta=color)
                                st.caption(f"📊 **Derived from Business Value:** {crit_bv_input}")
                                
                                with st.expander("📊 Classification Details"):
                                    st.markdown(f"**Method:** {crit_method}")
                                    st.markdown(f"**Source:** {crit_source}")
                                    st.markdown(f"**Reasoning:** {crit_reasoning}")
                            else:
                                st.info("ℹ️ Criticality not classified")
                        
                        st.markdown("---")
                        
                        if 'discovery_summary' in result:
                            with st.expander("📚 Discovered Methodologies (RAG Sources)"):
                                discovery = result['discovery_summary']
                                st.markdown("#### 🔍 What Agent 1 Discovered from Documents:")
                                st.markdown("**1. CIA Rating Scale:**")
                                st.write(f"   - {discovery.get('cia_rating_scale', 'N/A')}")
                                st.write(f"   - Source: {discovery.get('cia_definitions_source', 'Unknown')}")
                                
                                if 'business_value_calculation_method' in discovery:
                                    st.markdown("**2. Business Value Calculation:**")
                                    st.write(f"   - Method: {discovery.get('business_value_calculation_method', 'N/A')}")
                                    st.write(f"   - Levels: {', '.join(discovery.get('business_value_levels', []))}")
                                    st.write(f"   - Source: {discovery.get('business_value_source', 'Unknown')}")
                                
                                if 'criticality_classification_method' in discovery:
                                    st.markdown("**3. Criticality Classification:**")
                                    st.write(f"   - Method: {discovery.get('criticality_classification_method', 'N/A')}")
                                    st.write(f"   - Levels: {', '.join(discovery.get('criticality_levels', []))}")
                                    st.write(f"   - Source: {discovery.get('criticality_source', 'Unknown')}")
                                
                                if 'searches_performed' in discovery:
                                    st.markdown("**4. RAG Searches Performed:**")
                                    for search in discovery.get('searches_performed', []):
                                        st.write(f"   - {search}")
                                
                                st.success("✅ All methodologies discovered from organizational documents - NO HARDCODING!")
                        
                        st.download_button(
                            label="📥 Download Agent 1 Complete Results (JSON)",
                            data=json.dumps(result, indent=2),
                            file_name=f"agent1_complete_{selected_asset['asset_name'].replace(' ', '_')}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                    else:
                        st.info("ℹ️ Run Agent 1 to see complete CIA assessment with Business Value and Criticality")
                
                # Agent 2 Results Tab
                with tab2:
                    if st.session_state.risk_result:
                        result = st.session_state.risk_result
                        
                        # Check for error
                        if 'error' in result:
                            st.error(f"❌ Agent 2 Error: {result['error']}")
                            if 'details' in result:
                                with st.expander("❌ Error Details"):
                                    st.text(result['details'])
                            if 'raw_response' in result:
                                with st.expander("📄 Raw Output"):
                                    st.text(result['raw_response'][:2000])
                            
                            # Show retry suggestion
                            st.info("ℹ️ Try clicking the Agent 2 button again. The system will automatically rotate API keys if needed.")
                        else:
                            st.markdown("### 📊 Risk Summary")
                            
                            # Handle summary with defaults
                            summary = result.get('summary', {})
                            
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric("Total Threats", summary.get('total_threats_assessed', 0))
                            
                            with col2:
                                st.metric("Highest Risk Value", summary.get('highest_risk_value', 0))
                            
                            with col3:
                                st.metric("Non-Acceptable Risks", summary.get('non_acceptable_risks_count', 0), delta="🔴")
                            
                            with col4:
                                st.metric("Acceptable Risks", summary.get('acceptable_risks_count', 0), delta="🔴")
                        
                            st.markdown("### ⚠️ Threat Risk Analysis")
                            
                            # Get threat list with fallback
                            threats = result.get('threat_risk_quantification', result.get('risk_assessments', []))
                            
                            for idx, threat_risk in enumerate(threats, 1):
                                # Get threat name - Agent 2 should provide specific threat names
                                threat_name = threat_risk.get('threat', threat_risk.get('threat_name', 'Unknown Threat'))
                                
                                # If it's still the placeholder, make it more descriptive
                                if threat_name in ['To be assessed by agents', 'Unknown Threat', 'General security threats']:
                                    if 'risk_statement' in threat_risk:
                                        threat_name = f"Security Threat {idx}"
                                    else:
                                        threat_name = f"Threat {idx}"
                                
                                with st.expander(f"**{threat_name}**", expanded=(idx == 1)):
                                    col1, col2, col3, col4 = st.columns(4)
                                    
                                    with col1:
                                        risk_impact = threat_risk.get('risk_impact', {})
                                        if isinstance(risk_impact, dict):
                                            rating = risk_impact.get('rating', 'N/A')
                                            category = risk_impact.get('category', '')
                                            st.metric("Risk Impact", f"{rating}/5" if isinstance(rating, (int, float)) else rating, delta=category)
                                        else:
                                            st.metric("Risk Impact", risk_impact)
                                    
                                    with col2:
                                        risk_prob = threat_risk.get('risk_probability', {})
                                        if isinstance(risk_prob, dict):
                                            rating = risk_prob.get('rating', 'N/A')
                                            category = risk_prob.get('category', '')
                                            st.metric("Risk Probability", f"{rating}/5" if isinstance(rating, (int, float)) else rating, delta=category)
                                        else:
                                            st.metric("Risk Probability", risk_prob)
                                    
                                    with col3:
                                        risk_val = threat_risk.get('risk_value', {})
                                        if isinstance(risk_val, dict):
                                            st.metric("Risk Value", risk_val.get('value', 'N/A'))
                                        else:
                                            st.metric("Risk Value", risk_val)
                                    
                                    with col4:
                                        risk_eval = threat_risk.get('risk_evaluation_rating', {})
                                        if isinstance(risk_eval, dict):
                                            rating = risk_eval.get('rating', 0)
                                            color = "🔴" if rating >= 4 else "🟡" if rating == 3 else "🟢"
                                            st.metric("Risk Rating", f"{rating}/5", delta=f"{color}")
                                        else:
                                            st.metric("Risk Rating", risk_eval)
                        
                            # Download button
                            st.download_button(
                                label="📥 Download Agent 2 Results (JSON)",
                                data=json.dumps(result, indent=2),
                                file_name=f"agent2_risk_{selected_asset['asset_name'].replace(' ', '_')}.json",
                                mime="application/json",
                                use_container_width=True
                            )
                    else:
                        st.info("ℹ️ Run Agent 2 to see risk quantification results")
                
                # Agent 3 Results Tab
                with tab3:
                    if st.session_state.control_result:
                        result = st.session_state.control_result
                        
                        # Check for error
                        if 'error' in result:
                            st.error(f"❌ Agent 3 Error: {result['error']}")
                            if 'details' in result:
                                with st.expander("❌ Error Details"):
                                    st.text(result['details'])
                            if 'raw_response' in result:
                                with st.expander("📄 Raw Output"):
                                    st.text(result['raw_response'][:2000])
                            st.info("ℹ️ Try clicking the Agent 3 button again. The system will automatically rotate API keys if needed.")
                        else:
                            st.markdown("### 📊 Control Evaluation Summary")
                            
                            # Get threat control evaluation with fallback
                            threat_controls = result.get('threat_control_evaluation', [])
                            
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Threats Evaluated", len(threat_controls))
                            
                            with col2:
                                if threat_controls:
                                    try:
                                        ratings = []
                                        for t in threat_controls:
                                            ctrl_calc = t.get('control_rating_calculation', {})
                                            ctrl_rating = ctrl_calc.get('control_rating')
                                            if isinstance(ctrl_rating, (int, float)):
                                                ratings.append(ctrl_rating)
                                        
                                        if ratings:
                                            avg_rating = sum(ratings) / len(ratings)
                                            st.metric("Avg Control Rating", f"{avg_rating:.2f}")
                                        else:
                                            st.metric("Avg Control Rating", "N/A")
                                    except:
                                        st.metric("Avg Control Rating", "N/A")
                                else:
                                    st.metric("Avg Control Rating", "N/A")
                            
                            with col3:
                                if threat_controls:
                                    try:
                                        residual_values = [
                                            t.get('residual_risk', {}).get('residual_risk_value', 0)
                                            for t in threat_controls
                                        ]
                                        highest_residual = max(residual_values) if residual_values else 0
                                        color = "🔴" if highest_residual >= 3 else "🟡" if highest_residual >= 2 else "🟢"
                                        st.metric("Highest Residual Risk", f"{highest_residual:.2f}", delta=color)
                                    except:
                                        st.metric("Highest Residual Risk", "N/A")
                                else:
                                    st.metric("Highest Residual Risk", "N/A")
                            
                            if not threat_controls:
                                st.warning("⚠️ No threat control evaluations found in results")
                            else:
                                st.markdown("### 📊 Threat Control Analysis")
                                
                                for idx, threat_ctrl in enumerate(threat_controls, 1):
                                    threat_name = threat_ctrl.get('threat', f'Threat {idx}')
                                    with st.expander(f"Threat {idx}: {threat_name}", expanded=(idx == 1)):
                                        
                                        col1, col2, col3, col4 = st.columns(4)
                                        
                                        with col1:
                                            controls = threat_ctrl.get('controls_identified', [])
                                            st.metric("Controls Found", len(controls))
                                        
                                        with col2:
                                            ctrl_calc = threat_ctrl.get('control_rating_calculation', {})
                                            ctrl_rating_numeric = ctrl_calc.get('control_rating')
                                            ctrl_rating_text = ctrl_calc.get('control_rating_text', '')
                                            
                                            if isinstance(ctrl_rating_numeric, (int, float)):
                                                display_value = f"{ctrl_rating_numeric:.2f}"
                                                if ctrl_rating_text:
                                                    display_value += f" ({ctrl_rating_text})"
                                            else:
                                                display_value = ctrl_rating_numeric or ctrl_rating_text or 'N/A'
                                            
                                            st.metric("Control Rating", display_value)
                                        
                                        with col3:
                                            risk_rating = threat_ctrl.get('risk_evaluation_rating', 'N/A')
                                            st.metric("Risk Rating", risk_rating)
                                        
                                        with col4:
                                            residual_risk = threat_ctrl.get('residual_risk', {})
                                            residual = residual_risk.get('residual_risk_value', 0)
                                            classification = residual_risk.get('residual_risk_classification', '')
                                            color = "🔴" if residual >= 3 else "🟢"
                                            st.metric("Residual Risk", residual, delta=f"{color} {classification}")
                                
                                        if 'control_category_averages' in threat_ctrl:
                                            st.markdown("**Control Category Averages:**")
                                            col1, col2, col3 = st.columns(3)
                                            
                                            cat_avg = threat_ctrl['control_category_averages']
                                            
                                            with col1:
                                                st.metric("Preventive", f"{cat_avg.get('preventive_avg', 0):.2f}")
                                            
                                            with col2:
                                                st.metric("Detective", f"{cat_avg.get('detective_avg', 0):.2f}")
                                            
                                            with col3:
                                                st.metric("Corrective", f"{cat_avg.get('corrective_avg', 0):.2f}")
                                
                                        controls = threat_ctrl.get('controls_identified', [])
                                        if controls:
                                            st.markdown("**Controls Identified:**")
                                            
                                            controls_data = []
                                            for ctrl in controls:
                                                controls_data.append({
                                                    "Control ID": ctrl.get('control_id', 'N/A'),
                                                    "Name": ctrl.get('control_name', 'N/A'),
                                                    "Category": ctrl.get('category', 'N/A'),
                                                    "Rating": ctrl.get('current_rating', 'N/A'),
                                                    "Source": ctrl.get('source', 'N/A')
                                                })
                                            
                                            df = pd.DataFrame(controls_data)
                                            st.dataframe(df, use_container_width=True, hide_index=True)
                                
                                        if 'control_rating_calculation' in threat_ctrl:
                                            with st.expander("📊 Control Rating Calculation"):
                                                calc = threat_ctrl['control_rating_calculation']
                                                
                                                def extract_value(calc_str):
                                                    calc_str = str(calc_str)
                                                    if '=' in calc_str:
                                                        return float(calc_str.split('=')[-1].strip())
                                                    return float(calc_str)
                                                
                                                try:
                                                    weighted_p = extract_value(calc.get('weighted_preventive', 0))
                                                    weighted_d = extract_value(calc.get('weighted_detective', 0))
                                                    weighted_c = extract_value(calc.get('weighted_corrective', 0))
                                                    avg_weighted = extract_value(calc.get('average_weighted', 0))
                                                    ctrl_rating = calc.get('control_rating', 'N/A')
                                                    
                                                    st.markdown(f"""
                                                    **Formula:** Control Rating = FLOOR(AVERAGE(P_avg � 1.0, D_avg � 0.75, C_avg � 0.5))
                                                    
                                                    **Step 1: Weighted Values**
                                                    - Preventive: {weighted_p:.4f}
                                                    - Detective: {weighted_d:.4f}
                                                    - Corrective: {weighted_c:.4f}
                                                    
                                                    **Step 2: Average**
                                                    - Average: {avg_weighted:.4f}
                                                    
                                                    **Step 3: FLOOR Function**
                                                    - Control Rating: **{ctrl_rating}**
                                                    """)
                                                except Exception as e:
                                                    st.warning(f"Could not display calculation details: {str(e)}")
                        
                        st.download_button(
                            label="📥 Download Agent 3 Results (JSON)",
                            data=json.dumps(result, indent=2),
                            file_name=f"agent3_controls_{selected_asset['asset_name'].replace(' ', '_')}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                    else:
                        st.info("ℹ️ Run Agent 3 to see control evaluation results")
                
                # Agent 4 Results Tab
                with tab4:
                    if st.session_state.decision_result:
                        result = st.session_state.decision_result
                        
                        # Check for error
                        if 'error' in result:
                            st.error(f"❌ Agent 4 Error: {result['error']}")
                            if 'details' in result:
                                with st.expander("❌ Error Details"):
                                    st.text(result['details'])
                            st.info("ℹ️ Try clicking the Agent 4 button again.")
                        
                        #  CHECK FOR NEW FORMAT FIRST (management_decisions)
                        elif 'management_decisions' in result and isinstance(result.get('management_decisions'), dict):
                            st.success("✅ Management Decisions Generated!")
                            
                            decisions = result['management_decisions']
                            
                            # Display each threat's decision options
                            for threat_key in sorted(decisions.keys()):
                                threat_data = decisions[threat_key]
                                threat_name = threat_data.get('threat_name', 'Unknown Threat')
                                threat_index = threat_data.get('threat_index', 0)
                                
                                st.markdown(f"### ⚠️ Threat {threat_index}: {threat_name}")
                                
                                # Risk metrics
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Risk Rating", threat_data.get('risk_rating', 'N/A'))
                                with col2:
                                    st.metric("Residual Risk", threat_data.get('residual_risk', 'N/A'))
                                with col3:
                                    gaps = threat_data.get('control_gaps', [])
                                    st.metric("Control Gaps", len(gaps))
                                
                                # ⚠️ CONTROL GAPS DETAILS (NEW - EXPANDED)
                                if gaps:
                                    with st.expander("⚠️ Control Gaps Identified", expanded=True):
                                        for idx, gap in enumerate(gaps, 1):
                                            if isinstance(gap, dict):
                                                st.warning(f"**Gap {idx}: {gap.get('gap_description', 'Unknown gap')}**")
                                                col_a, col_b = st.columns(2)
                                                with col_a:
                                                    if gap.get('evidence'):
                                                        st.caption(f"📄 Evidence: {gap['evidence']}")
                                                    if gap.get('impact'):
                                                        st.caption(f"⚠️ Impact: {gap['impact']}")
                                                with col_b:
                                                    if gap.get('severity'):
                                                        severity = gap['severity']
                                                        color = "🔴" if severity == "HIGH" else "🟡" if severity == "MEDIUM" else "🟢"
                                                        st.caption(f"{color} Severity: {severity}")
                                            else:
                                                st.warning(f"**Gap {idx}:** {gap}")
                                
                                # Recommended controls
                                recommended = threat_data.get('recommended_controls', [])
                                if recommended:
                                    with st.expander(f"✅ Recommended Controls ({len(recommended)})", expanded=False):
                                        for idx, ctrl in enumerate(recommended, 1):
                                            if isinstance(ctrl, dict):
                                                st.success(f"**{idx}. {ctrl.get('control_name', ctrl.get('control_id', 'Control'))}**")
                                                col_a, col_b = st.columns(2)
                                                with col_a:
                                                    if ctrl.get('control_type'):
                                                        st.caption(f"🏷️ Type: {ctrl['control_type']}")
                                                    if ctrl.get('priority'):
                                                        st.caption(f"🔥 Priority: {ctrl['priority']}")
                                                with col_b:
                                                    if ctrl.get('rationale'):
                                                        st.caption(f"💭 {ctrl['rationale']}")
                                            else:
                                                st.success(f"{idx}. {ctrl}")
                                
                                # Decision options
                                st.markdown("#### 🎯 Decision Options")
                                
                                decision_options = threat_data.get('decision_options', [])
                                for opt in decision_options:
                                    value = opt.get('value', '')
                                    label = opt.get('label', '')
                                    
                                    # Emoji based on decision type
                                    if value == 'TREAT':
                                        emoji = "🔧"
                                    elif value == 'ACCEPT':
                                        emoji = "⚠️"
                                    elif value == 'TRANSFER':
                                        emoji = "✅"
                                    elif value == 'TERMINATE':
                                        emoji = "🚫"
                                    else:
                                        emoji = "✅"
                                    
                                    with st.expander(f"{emoji} {value} - {label}", expanded=(value == 'TREAT')):
                                        st.markdown(f"**Description:**")
                                        st.info(opt.get('description', 'N/A'))
                                        
                                        st.markdown(f"**Recommendation:**")
                                        rec = opt.get('recommendation', 'N/A')
                                        if 'recommended' in rec.lower():
                                            st.success(rec)
                                        else:
                                            st.warning(rec)
                                        
                                        st.markdown(f"**Consequences:**")
                                        st.write(opt.get('consequences', 'N/A'))
                                        
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            st.markdown(f"**💰 Cost:** {opt.get('estimated_cost', 'N/A')}")
                                            st.markdown(f"**⏱️ Timeline:** {opt.get('typical_timeline', 'N/A')}")
                                        with col2:
                                            st.markdown(f"**✅ Approval:** {opt.get('approval_required', 'N/A')}")
                                            st.markdown(f"**📊 Monitoring:** {opt.get('monitoring_required', 'N/A')}")
                                        
                                        # ? SELECTION BUTTON (NEW)
                                        st.markdown("---")
                                        if st.button(f"🎯 Select {value} for Threat {threat_index}", 
                                                   key=f"select_{threat_key}_{value}",
                                                   type="primary" if value == "TREAT" else "secondary",
                                                   use_container_width=True):
                                            # Store selection in session state
                                            if 'threat_decisions' not in st.session_state:
                                                st.session_state.threat_decisions = {}
                                            st.session_state.threat_decisions[threat_key] = {
                                                'decision': value,
                                                'threat_name': threat_name,
                                                'threat_index': threat_index
                                            }
                                            st.rerun()
                                
                                # Show selected decision for this threat
                                if 'threat_decisions' in st.session_state and threat_key in st.session_state.threat_decisions:
                                    selected = st.session_state.threat_decisions[threat_key]
                                    st.success(f"✅ **Selected Decision:** {selected['decision']}")
                                
                                st.markdown("---")
                            
                            # ? DECISION SUMMARY (NEW)
                            if 'threat_decisions' in st.session_state and st.session_state.threat_decisions:
                                st.markdown("---")
                                st.markdown("## 📊 Decision Summary")
                                
                                # Count decisions by type
                                decision_counts = {}
                                for threat_key, decision_data in st.session_state.threat_decisions.items():
                                    dec = decision_data['decision']
                                    decision_counts[dec] = decision_counts.get(dec, 0) + 1
                                
                                # Display summary
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("🔧 TREAT", decision_counts.get('TREAT', 0))
                                with col2:
                                    st.metric("✅ ACCEPT", decision_counts.get('ACCEPT', 0))
                                with col3:
                                    st.metric("🔄 TRANSFER", decision_counts.get('TRANSFER', 0))
                                with col4:
                                    st.metric("🚫 TERMINATE", decision_counts.get('TERMINATE', 0))
                                
                                # List all decisions
                                st.markdown("### Selected Decisions:")
                                for threat_key in sorted(st.session_state.threat_decisions.keys()):
                                    decision_data = st.session_state.threat_decisions[threat_key]
                                    st.markdown(f"- **Threat {decision_data['threat_index']}:** {decision_data['threat_name']} → **{decision_data['decision']}** ")
                                
                                # Proceed button
                                total_threats = len(decisions)
                                selected_threats = len(st.session_state.threat_decisions)
                                
                                if selected_threats > 0:
                                    if selected_threats == total_threats:
                                        st.success(f"✅ All {total_threats} threats have decisions selected!")
                                    else:
                                        st.info(f"ℹ️ {selected_threats} of {total_threats} threats have decisions selected. You can proceed with selected threats or select more.")
                                    
                                    if st.button("🚀 Proceed with Selected Decisions", type="primary", use_container_width=True):
                                        st.session_state.processing_workflows = True
                                        st.rerun()
                                else:
                                    st.warning(f"⚠️ Please select at least one decision to proceed ({selected_threats}/{total_threats} selected)")
                                
                                # Reset button
                                if st.button("🔄 Reset All Decisions", use_container_width=True):
                                    st.session_state.threat_decisions = {}
                                    # ✅ FIX: Also clear workflow processing state
                                    if 'processing_workflows' in st.session_state:
                                        del st.session_state.processing_workflows
                                    if 'current_decision_index' in st.session_state:
                                        del st.session_state.current_decision_index
                                    
                                    # ✅ FIX: Clear all cached questionnaires and forms
                                    keys_to_delete = []
                                    for key in st.session_state.keys():
                                        if any(x in key for x in ['_questionnaire_', '_form_', 'accept_q_', 'transfer_q_', 'terminate_q_', 'treat_key_']):
                                            keys_to_delete.append(key)
                                    
                                    for key in keys_to_delete:
                                        del st.session_state[key]
                                    
                                    st.rerun()

                                
                                # ============================================================
                                # WORKFLOW PROCESSING - TRANSFER
                                # ============================================================
                                
                                # Check if we should process workflows
                                if st.session_state.get('processing_workflows', False):
                                    st.markdown("---")
                                    st.markdown("## 🔄 Processing Selected Decisions")
                                    
                                    # 🆕 SEQUENTIAL WORKFLOW: Track current decision index
                                    if 'current_decision_index' not in st.session_state:
                                        st.session_state.current_decision_index = 0
                                    
                                    # Get sorted list of threat keys
                                    sorted_threat_keys = sorted(st.session_state.threat_decisions.keys())
                                    total_decisions = len(sorted_threat_keys)
                                    current_idx = st.session_state.current_decision_index
                                    
                                    # Show progress
                                    progress_value = min(1.0, (current_idx + 1) / total_decisions)
                                    st.progress(progress_value)
                                    st.caption(f"Processing Decision {min(current_idx + 1, total_decisions)} of {total_decisions}")
                                    st.markdown("---")
                                    
                                    # Process ONLY the current decision
                                    if current_idx < total_decisions:
                                        threat_key = sorted_threat_keys[current_idx]
                                    else:
                                        # All decisions completed
                                        st.success("✅ All decisions processed!")
                                        st.info("📊 View Risk Register to see all saved risks")
                                        if st.button("🔄 Start Over", type="primary"):
                                            st.session_state.current_decision_index = 0
                                            st.session_state.processing_workflows = False
                                            st.rerun()
                                        threat_key = None
                                    
                                    if threat_key:
                                        decision_data = st.session_state.threat_decisions[threat_key]
                                        decision = decision_data['decision']
                                        threat_name = decision_data['threat_name']
                                        threat_index = decision_data['threat_index']
                                        
                                        # Get threat data from decisions
                                        threat_data = decisions.get(threat_key, {})
                                        
                                        st.markdown(f"### 🎯 Threat {threat_index}: {threat_name}")
                                        st.info(f"**Decision:** {decision}")
                                        
                                        # TREAT WORKFLOW
                                        if decision == "TREAT":
                                            st.markdown(f"#### 🔧 Treatment Plan for: {threat_name}")
                                            
                                            control_gaps = threat_data.get('control_gaps', [])
                                            recommended_controls = threat_data.get('recommended_controls', [])
                                            
                                            col1, col2, col3 = st.columns(3)
                                            with col1:
                                                st.metric("Control Gaps", len(control_gaps))
                                            with col2:
                                                st.metric("Recommended Controls", len(recommended_controls))
                                            with col3:
                                                st.metric("Risk Rating", threat_data.get('risk_rating', 'N/A'))
                                            
                                            if recommended_controls:
                                                st.info(f"✅ Select controls to implement for **{threat_name}**:")
                                                
                                                threat_key = f"selected_controls_{threat_index}"
                                                if threat_key not in st.session_state:
                                                    st.session_state[threat_key] = list(range(len(recommended_controls)))
                                                
                                                for idx, control in enumerate(recommended_controls):
                                                    col_check, col_content = st.columns([0.1, 0.9])
                                                    with col_check:
                                                        selected = st.checkbox("Select", value=idx in st.session_state[threat_key], key=f"treat_ctrl_{threat_index}_{idx}", label_visibility="collapsed")
                                                        if selected and idx not in st.session_state[threat_key]:
                                                            st.session_state[threat_key].append(idx)
                                                        elif not selected and idx in st.session_state[threat_key]:
                                                            st.session_state[threat_key].remove(idx)
                                                    with col_content:
                                                        control_name = control.get('control_name', control.get('control_id', f'Control {idx+1}'))
                                                        with st.expander(f"🛡️ {control_name}", expanded=False):
                                                            col1, col2 = st.columns(2)
                                                            with col1:
                                                                if control.get('control_type'):
                                                                    st.caption(f"🏷️ Type: {control['control_type']}")
                                                                if control.get('priority'):
                                                                    st.caption(f"🔥 Priority: {control['priority']}")
                                                            with col2:
                                                                if control.get('rationale'):
                                                                    st.caption(f"💭 Rationale: {control['rationale']}")
                                                            if control.get('description'):
                                                                st.info(control['description'])
                                                            if control.get('implementation_guidance'):
                                                                st.success(f"**Implementation:** {control['implementation_guidance']}")
                                                            if control.get('addresses_gap'):
                                                                st.warning(f"**Addresses Gap:** {control['addresses_gap']}")
                                                            if not any([control.get('description'), control.get('implementation_guidance'), control.get('addresses_gap'), control.get('rationale')]):
                                                                st.caption("No additional details available")
                                                
                                                st.caption(f"✅ {len(st.session_state[threat_key])} of {len(recommended_controls)} controls selected")
                                                
                                                if st.button(f"🤖 Generate Treatment Plan", key=f"gen_treat_{threat_index}", type="primary"):
                                                    if not st.session_state[threat_key]:
                                                        st.error("❌ Select at least one control!")
                                                    else:
                                                        with st.spinner("🤖 Generating..."):
                                                            from phase2_risk_resolver.agents.agent_4_treatment_plan import generate_treatment_plan
                                                            selected_controls = [recommended_controls[i] for i in st.session_state[threat_key] if i < len(recommended_controls)]
                                                            risk_data = {'asset_name': selected_asset.get('asset_name'), 'asset_type': selected_asset.get('asset_type'), 'threat_name': threat_name, 'risk_rating': threat_data.get('risk_rating', 0), 'selected_controls': selected_controls, 'control_gaps': control_gaps}
                                                            plan = execute_agent_with_retry(generate_treatment_plan, "Treatment Plan", agent_3_results=st.session_state.control_result, risk_data=risk_data)
                                                            if 'error' not in plan:
                                                                st.session_state[f"treatment_plan_{threat_index}"] = plan
                                                                st.success("✅ Generated!")
                                                                st.rerun()
                                                            else:
                                                                st.error(f"❌ {plan.get('error')}")
                                            else:
                                                st.warning("⚠️ No recommended controls found")
                                            
                                            treat_key = f"treatment_plan_{threat_index}"
                                            if treat_key in st.session_state:
                                                st.markdown("---")
                                                st.markdown("### 📋 Generated Treatment Plan")
                                                
                                                plan = st.session_state[treat_key]
                                                
                                                # Display treatment plan in user-friendly format
                                                if isinstance(plan, dict):
                                                    # Treatment Actions
                                                    if plan.get('treatment_actions'):
                                                        st.markdown("#### 🔧 Treatment Actions")
                                                        actions = plan['treatment_actions']
                                                        if isinstance(actions, list):
                                                            for idx, action in enumerate(actions, 1):
                                                                if isinstance(action, dict):
                                                                    # Get control info
                                                                    control_id = action.get('control_id', f'ACTION-{idx}')
                                                                    threat = action.get('threat', 'Action')
                                                                    
                                                                    with st.expander(f"Action {idx}: {control_id} - {threat}", expanded=True):
                                                                        # Description of activities
                                                                        if action.get('description_of_activities'):
                                                                            st.info(f"**Activities:** {action['description_of_activities']}")
                                                                        
                                                                        # Key details in columns
                                                                        col1, col2 = st.columns(2)
                                                                        with col1:
                                                                            if action.get('implementation_priority'):
                                                                                st.caption(f"🔥 Priority: {action['implementation_priority']}")
                                                                            if action.get('implementation_responsibility'):
                                                                                st.caption(f"👤 Responsible: {action['implementation_responsibility']}")
                                                                            if action.get('estimated_cost'):
                                                                                st.caption(f"💰 Cost: {action['estimated_cost']}")
                                                                        with col2:
                                                                            if action.get('proposed_start_date'):
                                                                                st.caption(f"📅 Start: {action['proposed_start_date']}")
                                                                            if action.get('proposed_completion_date'):
                                                                                st.caption(f"⏱️ Complete: {action['proposed_completion_date']}")
                                                                            if action.get('estimated_duration_days'):
                                                                                st.caption(f"⏳ Duration: {action['estimated_duration_days']} days")
                                                                        
                                                                        # Resources
                                                                        if action.get('necessary_resources'):
                                                                            st.success(f"**Resources:** {action['necessary_resources']}")
                                                                        
                                                                        # Evaluation method
                                                                        if action.get('method_for_evaluation'):
                                                                            st.warning(f"**Success Criteria:** {action['method_for_evaluation']}")
                                                                        
                                                                        # Expected risk reduction
                                                                        if action.get('expected_risk_reduction'):
                                                                            st.caption(f"📉 Expected Risk Reduction: {action['expected_risk_reduction']}")
                                                                else:
                                                                    st.write(f"{idx}. {action}")
                                                    
                                                    # Summary
                                                    if plan.get('summary'):
                                                        st.markdown("#### 📊 Summary")
                                                        summary = plan['summary']
                                                        col1, col2, col3, col4 = st.columns(4)
                                                        with col1:
                                                            st.metric("Total Actions", summary.get('total_actions', 0))
                                                        with col2:
                                                            st.metric("Total Cost", summary.get('total_estimated_cost', 'N/A'))
                                                        with col3:
                                                            st.metric("Duration", f"{summary.get('total_duration_days', 0)} days")
                                                        with col4:
                                                            st.metric("Expected Risk After", summary.get('expected_residual_risk_after', 'N/A'))
                                                    
                                                    # Show full JSON in expander for reference
                                                    with st.expander("📄 View Full Plan (JSON)", expanded=False):
                                                        st.json(plan)
                                                else:
                                                    # Fallback: show as JSON if not dict
                                                    st.json(plan)
                                                
                                                if st.button(f"💾 Save to Risk Register", key=f"save_treat_{threat_index}", type="primary"):
                                                    with st.spinner("💾 Saving..."):
                                                        try:
                                                            from phase2_risk_resolver.database.save_to_register import save_assessment_to_risk_register
                                                            
                                                            # ✅ FIX: Filter agent_2_results to include ONLY current threat
                                                            all_threats = st.session_state.risk_result.get('threat_risk_quantification', [])
                                                            current_threat_data = None
                                                            for t in all_threats:
                                                                if t.get('threat') == threat_name:
                                                                    current_threat_data = t
                                                                    break
                                                            
                                                            if not current_threat_data:
                                                                st.error(f"❌ Could not find threat data for: {threat_name}")
                                                            else:
                                                                # Create filtered agent_2_results with only current threat
                                                                filtered_agent_2 = {
                                                                    **st.session_state.risk_result,
                                                                    'threat_risk_quantification': [current_threat_data]
                                                                }
                                                                
                                                                risk_ids = save_assessment_to_risk_register(
                                                                    asset_data=st.session_state.selected_asset, 
                                                                    agent_1_results=st.session_state.impact_result, 
                                                                    agent_2_results=filtered_agent_2,
                                                                    agent_3_results=st.session_state.control_result, 
                                                                    agent_4_results={'management_decision': 'TREAT', 'treatment_plan': st.session_state[treat_key]}
                                                                )
                                                                
                                                                if risk_ids and len(risk_ids) > 0:
                                                                    st.success(f"✅ Saved! Risk ID: {risk_ids[0]}")
                                                                    st.session_state.current_decision_index += 1
                                                                    st.rerun()
                                                                else:
                                                                    st.error("❌ Save returned no Risk IDs")
                                                        except Exception as e:
                                                            st.error(f"❌ Save failed: {str(e)}")
                                                            import traceback
                                                            with st.expander("Debug"):
                                                                st.code(traceback.format_exc())
                                        
                                        # ACCEPT WORKFLOW
                                        elif decision == "ACCEPT":
                                            st.markdown(f"#### ⚠️ Risk Acceptance for: {threat_name}")
                                            
                                            accept_key = f"accept_q_{threat_key}"
                                            if accept_key not in st.session_state:
                                                with st.spinner("🤖 Generating acceptance questionnaire..."):
                                                    # Get actual Risk ID from database if it exists, otherwise use temp ID
                                                    import sqlite3
                                                    try:
                                                        conn = sqlite3.connect('database/risk_register.db')
                                                        cursor = conn.cursor()
                                                        cursor.execute("SELECT MAX(CAST(SUBSTR(risk_id, 5) AS INTEGER)) FROM risks WHERE risk_id LIKE 'RSK-%'")
                                                        result = cursor.fetchone()
                                                        next_num = (result[0] or 0) + 1
                                                        actual_risk_id = f"RSK-{next_num:03d}"
                                                        conn.close()
                                                    except:
                                                        actual_risk_id = f"RSK-{threat_index:03d}"
                                                    
                                                    ctx = {'risk_id': actual_risk_id, 'asset_name': selected_asset.get('asset_name'), 'threat_name': threat_name, 'inherent_risk_rating': threat_data.get('risk_rating', 0), 'residual_risk_rating': threat_data.get('residual_risk', 0), 'control_gaps': threat_data.get('control_gaps', [])}
                                                    q = execute_agent_with_retry(generate_acceptance_questionnaire, "Acceptance Q", risk_context=ctx)
                                                    st.session_state[accept_key] = q
                                                    st.session_state[f"{accept_key}_risk_id"] = actual_risk_id
                                                    st.rerun()
                                            
                                            q = st.session_state[accept_key]
                                            actual_risk_id = st.session_state.get(f"{accept_key}_risk_id", f"RSK-{threat_index:03d}")
                                            if 'error' not in q:
                                                # Get actual risk data
                                                risk_category = threat_data.get('risk_category', 'Security Risk')
                                                if not risk_category or risk_category == 'N/A':
                                                    risk_category = selected_asset.get('asset_type', 'Security Risk')
                                                current_risk = threat_data.get('risk_rating', 'N/A')
                                                residual_risk = threat_data.get('residual_risk', 'N/A')
                                                risk_description = f"Asset: {selected_asset.get('asset_name')}, Threat: {threat_name}. Risk Rating: {current_risk}, Residual Risk: {residual_risk}"
                                                
                                                # Display risk context (AI pre-filled)
                                                st.info("📊 **Risk Context** (Auto-filled by AI from Agents 1-3)")
                                                col1, col2, col3 = st.columns(3)
                                                with col1:
                                                    st.caption(f"**Risk ID:** {actual_risk_id}")
                                                    st.caption(f"**Category:** {risk_category}")
                                                with col2:
                                                    st.caption(f"**Current Risk:** {current_risk}")
                                                    st.caption(f"**Residual Risk:** {residual_risk}")
                                                with col3:
                                                    st.caption(f"**Threat:** {threat_name[:80]}..." if len(threat_name) > 80 else f"**Threat:** {threat_name}")
                                                st.markdown("---")
                                                
                                                # 📧 EMAIL OPTION - Choose between manual fill or email send
                                                st.info("💡 **Choose how to complete the acceptance questionnaire:**")
                                                
                                                col_option1, col_option2 = st.columns(2)
                                                
                                                with col_option1:
                                                    st.markdown("### 📧 Option 1: Send via Email")
                                                    st.caption("Send questionnaire to risk owner/approver")
                                                    
                                                    recipient_email_accept = st.text_input(
                                                        "Recipient Email Address",
                                                        placeholder="risk.owner@company.com",
                                                        key=f"recipient_email_accept_{threat_key}",
                                                        help="Email address of the person who will complete the acceptance questionnaire"
                                                    )
                                                    
                                                    if st.button("📧 Send Acceptance Questionnaire Email", key=f"send_accept_email_{threat_key}", type="primary", disabled=not recipient_email_accept):
                                                        with st.spinner(f"📧 Sending email to {recipient_email_accept}..."):
                                                            try:
                                                                from email_sender import send_questionnaire_email
                                                                
                                                                # 🆕 Prepare agent results for storage
                                                                # Get ORIGINAL Agent 2 threat data
                                                                agent_2_threats = st.session_state.get('risk_result', {}).get('threat_risk_quantification', [])
                                                                original_threat = next((t for t in agent_2_threats if t.get('threat') == threat_name), threat_data)
                                                                
                                                                agent_results = {
                                                                    'agent_1': st.session_state.get('impact_result', {}),
                                                                    'agent_2': st.session_state.get('risk_result', {}),
                                                                    'agent_3': st.session_state.get('control_result', {}),
                                                                    'selected_asset': st.session_state.get('selected_asset', {}),
                                                                    'threat_data': original_threat
                                                                }
                                                                
                                                                result = send_questionnaire_email(
                                                                    recipient_email=recipient_email_accept,
                                                                    asset_name=selected_asset.get('asset_name'),
                                                                    questionnaire=q,
                                                                    questionnaire_type='ACCEPT',
                                                                    agent_results=agent_results
                                                                )
                                                                
                                                                if result and result.get('success'):
                                                                    st.success(f"✅ Email sent successfully to {recipient_email_accept}!")
                                                                    st.info(f"📋 **Tracking Token:** {result['token']}")
                                                                    st.caption("The recipient will receive a link to fill the questionnaire online. Once completed, it will appear in 'Pending Questionnaires' section.")
                                                                    # ✅ Sequential workflow: Move to next threat after email send
                                                                    st.session_state.current_decision_index += 1
                                                                    time.sleep(1)
                                                                    st.rerun()
                                                                else:
                                                                    error_msg = result.get('error', 'Unknown error') if result else 'No response'
                                                                    st.error(f"❌ Failed to send email: {error_msg}")
                                                            except Exception as e:
                                                                st.error(f"❌ Error: {str(e)}")
                                                                import traceback
                                                                with st.expander("🔍 Error Details"):
                                                                    st.code(traceback.format_exc())
                                                
                                                with col_option2:
                                                    st.markdown("### ✍️ Option 2: Fill Manually")
                                                    st.caption("Fill the questionnaire yourself right now")
                                                    st.info("👇 Scroll down to see the questionnaire form below")
                                                
                                                st.markdown("---")
                                                
                                                # Render questionnaire sections
                                                for section_idx, section in enumerate(q.get('sections', [])):
                                                    section_title = section.get('section_title', section.get('title', ''))
                                                    if section_title and section_title.strip().lower() != 'section':
                                                        st.markdown(f"### {section_title}")
                                                        # Show section help text
                                                        section_help = section.get('help_text', section.get('description', ''))
                                                        if section_help:
                                                            st.caption(f"ℹ️ {section_help}")
                                                    
                                                    # Handle both 'questions' and 'fields' keys
                                                    questions_list = section.get('questions', section.get('fields', []))
                                                    for q_idx, qu in enumerate(questions_list):
                                                        q_id = qu.get('question_id', qu.get('id', f'Q{section_idx}_{q_idx}'))
                                                        q_text = qu.get('question_text', qu.get('question', qu.get('text', 'Question')))
                                                        # AGGRESSIVE CLEANUP: Remove ALL markdown formatting
                                                        q_text = str(q_text).replace('**', '').replace('__', '').replace('_', '').strip()
                                                        # Remove extra spaces
                                                        q_text = ' '.join(q_text.split())
                                                        q_type = qu.get('question_type', qu.get('type', 'text'))
                                                        q_help = qu.get('help_text', '')
                                                        q_placeholder = qu.get('placeholder', '')
                                                        q_required = qu.get('required', False)
                                                        options = qu.get('options', [])
                                                        # Add section and question index to ensure uniqueness
                                                        widget_key = f"acc_{threat_key}_s{section_idx}_q{q_idx}_{q_id}"
                                                        
                                                        # Add required indicator
                                                        display_text = f"{q_text} {'*' if q_required else ''}"
                                                        
                                                        # Handle display-only fields (AI provided) - populate with actual data
                                                        if q_type == 'display':
                                                            # Get the value to display
                                                            display_value = qu.get('value', '')
                                                            
                                                            # Replace placeholders with actual data
                                                            if 'RISK_ID' in str(display_value).upper() or 'risk_id' in q_id.lower():
                                                                display_value = actual_risk_id
                                                            elif 'RISK_CATEGORY' in str(display_value).upper() or 'risk_category' in q_id.lower():
                                                                display_value = risk_category
                                                            elif 'RISK_DESCRIPTION' in str(display_value).upper() or 'risk_description' in q_id.lower():
                                                                display_value = risk_description
                                                            
                                                            st.info(f"ℹ️ {q_text} {display_value}")
                                                            continue
                                                        
                                                        if q_type in ['text_area', 'textarea']:
                                                            st.text_area(display_text, key=widget_key, help=q_help, placeholder=q_placeholder, height=100)
                                                        elif q_type == 'date':
                                                            from datetime import date
                                                            st.date_input(display_text, value=date.today(), key=widget_key, help=q_help)
                                                        elif q_type == 'text':
                                                            st.text_input(display_text, key=widget_key, help=q_help, placeholder=q_placeholder)
                                                        elif q_type in ['select', 'dropdown']:
                                                            if options:
                                                                opts = [opt.get('label', opt.get('value', str(opt))) if isinstance(opt, dict) else str(opt) for opt in options]
                                                                st.selectbox(display_text, options=opts, key=widget_key, help=q_help)
                                                            else:
                                                                st.text_input(display_text, key=widget_key, help=q_help, placeholder=q_placeholder)
                                                        elif q_type in ['checkbox', 'multiselect']:
                                                            # Display question text as plain text (already cleaned)
                                                            st.write(f"**{q_text}**")
                                                            if q_help:
                                                                st.caption(f"ℹ️ {q_help}")
                                                            for idx, opt in enumerate(options):
                                                                if isinstance(opt, dict):
                                                                    # Handle both control_gaps structure and treatment controls structure
                                                                    ctrl_name = opt.get('label', opt.get('control_name', opt.get('gap_description', f'Control {idx+1}')))
                                                                    # Clean markdown from control name
                                                                    ctrl_name = str(ctrl_name).replace('**', '')
                                                                    
                                                                    with st.expander(f"🛡️ {ctrl_name}", expanded=False):
                                                                        # Show description or gap details
                                                                        if opt.get('description'):
                                                                            desc = str(opt['description']).replace('**', '')
                                                                            st.info(desc)
                                                                        elif opt.get('gap_description'):
                                                                            gap_desc = str(opt['gap_description']).replace('**', '')
                                                                            st.info(f"**Gap:** {gap_desc}")
                                                                        
                                                                        # Show evidence, impact, severity for control gaps
                                                                        if opt.get('evidence'):
                                                                            st.caption(f"📋 Evidence: {opt['evidence']}")
                                                                        if opt.get('impact'):
                                                                            st.caption(f"⚠️ Impact: {opt['impact']}")
                                                                        if opt.get('severity'):
                                                                            severity_color = {"CRITICAL": "🔴", "HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(opt['severity'], "⚪")
                                                                            st.caption(f"{severity_color} Severity: {opt['severity']}")
                                                                        
                                                                        # Show control details (for treatment controls)
                                                                        col1, col2 = st.columns(2)
                                                                        with col1:
                                                                            if opt.get('priority'):
                                                                                st.caption(f"🔥 Priority: {opt['priority']}")
                                                                            if opt.get('cost'):
                                                                                st.caption(f"💰 Cost: {opt['cost']}")
                                                                            if opt.get('control_type'):
                                                                                st.caption(f"🏷️ Type: {opt['control_type']}")
                                                                        with col2:
                                                                            if opt.get('timeline'):
                                                                                st.caption(f"⏱️ Timeline: {opt['timeline']}")
                                                                            if opt.get('risk_reduction'):
                                                                                st.caption(f"📉 Risk Reduction: {opt['risk_reduction']}")
                                                                            if opt.get('complexity'):
                                                                                st.caption(f"⚙️ Complexity: {opt['complexity']}")
                                                                        if opt.get('addresses_gap'):
                                                                            st.warning(f"**Addresses Gap:** {opt['addresses_gap']}")
                                                                        
                                                                        st.checkbox(f"Select {ctrl_name}", key=f"{widget_key}_opt_{idx}")
                                                                else:
                                                                    st.checkbox(str(opt), key=f"{widget_key}_opt_{idx}")
                                                        else:
                                                            st.text_input(display_text, key=widget_key, help=q_help, placeholder=q_placeholder)
                                                
                                                if st.button("✅ Submit & Generate Acceptance Form", key=f"sub_acc_{threat_key}", type="primary"):
                                                    # Collect answers - MUST iterate with same indices as rendering
                                                    answers = {}
                                                    for section_idx, section in enumerate(q.get('sections', [])):
                                                        questions_list = section.get('questions', section.get('fields', []))
                                                        for q_idx, qu in enumerate(questions_list):
                                                            q_id = qu.get('question_id', qu.get('id', f'Q{section_idx}_{q_idx}'))
                                                            q_type = qu.get('question_type', qu.get('type', 'text'))
                                                            # Use SAME key format as rendering
                                                            widget_key = f"acc_{threat_key}_s{section_idx}_q{q_idx}_{q_id}"
                                                            
                                                            if q_type in ['checkbox', 'multiselect']:
                                                                selected = []
                                                                for idx, opt in enumerate(qu.get('options', [])):
                                                                    if st.session_state.get(f"{widget_key}_opt_{idx}", False):
                                                                        if isinstance(opt, dict):
                                                                            selected.append(opt.get('label', opt.get('control_name', str(opt))))
                                                                        else:
                                                                            selected.append(str(opt))
                                                                answers[q_id] = selected
                                                            else:
                                                                val = st.session_state.get(widget_key, '')
                                                                # Convert date objects to strings
                                                                if hasattr(val, 'strftime'):
                                                                    val = val.strftime('%Y-%m-%d')
                                                                answers[q_id] = val
                                                    
                                                    # Generate acceptance form
                                                    with st.spinner("🤖 Generating acceptance form..."):
                                                        from phase2_risk_resolver.agents.agent_4_acceptance_form import generate_acceptance_form
                                                        ctx = {'risk_id': actual_risk_id, 'asset_name': selected_asset.get('asset_name'), 'threat_name': threat_name, 'inherent_risk_rating': threat_data.get('risk_rating', 0), 'residual_risk_rating': threat_data.get('residual_risk', 0)}
                                                        form = generate_acceptance_form(risk_context=ctx, questionnaire_answers=answers, questionnaire_structure=q, api_key=api_key)
                                                        
                                                        # Store in session state
                                                        st.session_state[f"acceptance_form_{threat_key}"] = form
                                                        st.session_state[f"acceptance_answers_{threat_key}"] = answers
                                                        st.rerun()
                                                
                                                # Display form if it exists in session state
                                                if f"acceptance_form_{threat_key}" in st.session_state:
                                                    form = st.session_state[f"acceptance_form_{threat_key}"]
                                                    answers = st.session_state.get(f"acceptance_answers_{threat_key}", {})
                                                    
                                                    # 🔧 FIX: Convert malformed selected_controls FIRST (before HTML cleaning)
                                                    if 'compensating_controls' in form and isinstance(form['compensating_controls'], dict):
                                                        sc = form['compensating_controls'].get('selected_controls')
                                                        # Check if it's a dict with numeric keys {0: {...}, 1: {...}}
                                                        if isinstance(sc, dict) and all(str(k).isdigit() for k in sc.keys()):
                                                            form['compensating_controls']['selected_controls'] = [sc[k] for k in sorted(sc.keys(), key=int)]
                                                        # Check if it's a stringified list "[{...}]"
                                                        elif isinstance(sc, str) and sc.strip().startswith('['):
                                                            try:
                                                                import ast
                                                                form['compensating_controls']['selected_controls'] = ast.literal_eval(sc)
                                                            except:
                                                                pass
                                                    
                                                    # 🔧 FIX: Clean HTML entities from entire form recursively
                                                    import html
                                                    def clean_html_recursive(obj):
                                                        if isinstance(obj, str):
                                                            return html.unescape(obj)
                                                        elif isinstance(obj, dict):
                                                            return {k: clean_html_recursive(v) for k, v in obj.items()}
                                                        elif isinstance(obj, list):
                                                            return [clean_html_recursive(item) for item in obj]
                                                        return obj
                                                    
                                                    form = clean_html_recursive(form)
                                                    
                                                    if 'error' not in form:
                                                        st.success("✅ Acceptance Form Generated!")
                                                        
                                                        # 🆕 100% DYNAMIC FORM DISPLAY - No hardcoded sections
                                                        emoji_map = {'metadata': '📋', 'risk_context': '⚠️', 'engagement_project': '🏢', 
                                                                     'compensating_controls': '🛡️', 'justification': '📝', 
                                                                     'approvals': '✅', 'signoff': '✍️'}
                                                        
                                                        # 📋 RISK ACCEPTANCE FORM HEADING
                                                        st.markdown("### 📋 Risk Acceptance Form")
                                                        st.markdown("---")
                                                        
                                                        for key, value in form.items():
                                                            emoji = emoji_map.get(key, '📌')
                                                            section_title = key.replace('_', ' ').title()
                                                            
                                                            # Display metadata fields without section heading
                                                            if key == 'metadata':
                                                                if isinstance(value, dict):
                                                                    for k, v in value.items():
                                                                        st.write(f"**{k.replace('_', ' ').title()}:** {v}")
                                                                continue
                                                            
                                                            st.markdown(f"### {emoji} {section_title}")
                                                            
                                                            # 🆕 100% DYNAMIC: Parse any stringified data recursively
                                                            def parse_value(val):
                                                                """Recursively parse stringified JSON/dicts"""
                                                                if isinstance(val, str) and (val.strip().startswith('{') or val.strip().startswith('[')):
                                                                    try:
                                                                        import ast
                                                                        import html
                                                                        unescaped = html.unescape(val)
                                                                        try:
                                                                            return json.loads(unescaped)
                                                                        except:
                                                                            return ast.literal_eval(unescaped)
                                                                    except:
                                                                        return val
                                                                elif isinstance(val, list):
                                                                    return [parse_value(item) for item in val]
                                                                elif isinstance(val, dict):
                                                                    return {k: parse_value(v) for k, v in val.items()}
                                                                return val
                                                            
                                                            def display_value(k, v):
                                                                """Display any value type dynamically"""
                                                                field_name = k.replace('_', ' ').title()
                                                                
                                                                if isinstance(v, dict):
                                                                    # Nested dict - show as grouped section
                                                                    st.markdown(f"**{field_name}:**")
                                                                    for dk, dv in v.items():
                                                                        st.write(f"  • **{dk.replace('_', ' ').title()}:** {dv}")
                                                                elif isinstance(v, list) and v and isinstance(v[0], dict):
                                                                    # List of dicts - show in expanders
                                                                    st.markdown(f"**{field_name}:**")
                                                                    for idx, item in enumerate(v, 1):
                                                                        label = item.get('name') or item.get('label') or item.get('description') or item.get('gap_description') or f"Item {idx}"
                                                                        if len(str(label)) > 50:
                                                                            label = str(label)[:50] + "..."
                                                                        with st.expander(f"📋 {label}", expanded=False):
                                                                            for ik, iv in item.items():
                                                                                st.write(f"**{ik.replace('_', ' ').title()}:** {iv}")
                                                                elif isinstance(v, list):
                                                                    st.write(f"**{field_name}:** {', '.join(str(x) for x in v)}")
                                                                else:
                                                                    st.write(f"**{field_name}:** {v}")
                                                            
                                                            if isinstance(value, dict):
                                                                parsed_value = parse_value(value)
                                                                for k, v in parsed_value.items():
                                                                    display_value(k, v)
                                                            elif isinstance(value, list):
                                                                parsed_value = parse_value(value)
                                                                for item in parsed_value:
                                                                    if isinstance(item, dict):
                                                                        for ik, iv in item.items():
                                                                            display_value(ik, iv)
                                                                        st.write("---")
                                                                    else:
                                                                        st.write(f"- {item}")
                                                            else:
                                                                st.write(value)
                                                        
                                                        with st.expander("📄 Raw JSON"):
                                                            st.json(form)
                                                        
                                                        if st.button(f"💾 Save to Risk Register", key=f"save_acc_{threat_key}", type="primary"):
                                                            with st.spinner("💾 Saving..."):
                                                                try:
                                                                    from phase2_risk_resolver.database.save_to_register import save_assessment_to_risk_register
                                                                    
                                                                    # Filter agent_2_results to include ONLY current threat
                                                                    all_threats = st.session_state.risk_result.get('threat_risk_quantification', [])
                                                                    current_threat_data = None
                                                                    for t in all_threats:
                                                                        if t.get('threat') == threat_name:
                                                                            current_threat_data = t
                                                                            break
                                                                    
                                                                    if not current_threat_data:
                                                                        st.error(f"❌ Could not find threat data for: {threat_name}")
                                                                    else:
                                                                        # Create filtered agent_2_results with only current threat
                                                                        filtered_agent_2 = {
                                                                            **st.session_state.risk_result,
                                                                            'threat_risk_quantification': [current_threat_data]
                                                                        }
                                                                        
                                                                        risk_ids = save_assessment_to_risk_register(
                                                                            asset_data=st.session_state.selected_asset, 
                                                                            agent_1_results=st.session_state.impact_result, 
                                                                            agent_2_results=filtered_agent_2,
                                                                            agent_3_results=st.session_state.control_result, 
                                                                            agent_4_results={'management_decision': 'ACCEPT', 'acceptance_form': form}
                                                                        )
                                                                        
                                                                        if risk_ids and len(risk_ids) > 0:
                                                                            st.success(f"✅ Saved! Risk ID: {risk_ids[0]}")
                                                                            st.session_state.current_decision_index += 1
                                                                            st.rerun()
                                                                        else:
                                                                            st.error("❌ Save returned no Risk IDs")
                                                                except Exception as e:
                                                                    st.error(f"❌ Save failed: {str(e)}")
                                                                    import traceback
                                                                    with st.expander("Debug"):
                                                                        st.code(traceback.format_exc())
                                                    else:
                                                        st.error(f"❌ Error: {form.get('error')}")
                                            else:
                                                st.error(f"❌ {q.get('error')}")
                                        
                                        # TRANSFER WORKFLOW
                                        elif decision == "TRANSFER":
                                            # Check if questionnaire already generated
                                            transfer_q_key = f"transfer_questionnaire_{threat_key}"
                                            
                                            if transfer_q_key not in st.session_state:
                                                st.markdown("#### 📋 Step 1: Generate Transfer Questionnaire")
                                                
                                                with st.spinner("🤖 Generating transfer questionnaire..."):
                                                    # 🔧 FIX: Get actual Risk ID from database
                                                    import sqlite3
                                                    try:
                                                        conn = sqlite3.connect('database/risk_register.db')
                                                        cursor = conn.cursor()
                                                        cursor.execute("SELECT MAX(CAST(SUBSTR(risk_id, 5) AS INTEGER)) FROM risks WHERE risk_id LIKE 'RSK-%'")
                                                        result = cursor.fetchone()
                                                        next_num = (result[0] or 0) + 1
                                                        actual_risk_id = f"RSK-{next_num:03d}"
                                                        conn.close()
                                                    except:
                                                        actual_risk_id = f"RSK-{threat_index:03d}"
                                                    
                                                    # Prepare risk context
                                                    risk_context = {
                                                        'risk_id': actual_risk_id,
                                                        'asset_name': selected_asset.get('asset_name', 'Unknown'),
                                                        'threat_name': threat_name,
                                                        'inherent_risk_rating': threat_data.get('risk_rating', 0),
                                                        'residual_risk_rating': threat_data.get('residual_risk', 0),
                                                        'control_gaps': threat_data.get('control_gaps', [])
                                                    }
                                                    
                                                    transfer_questionnaire = execute_agent_with_retry(
                                                        generate_transfer_questionnaire,
                                                        "Transfer Questionnaire Generator",
                                                        risk_context=risk_context
                                                    )
                                                    
                                                    st.session_state[transfer_q_key] = transfer_questionnaire
                                                    st.session_state[f"{transfer_q_key}_risk_id"] = actual_risk_id
                                                    st.rerun()
                                            
                                            # Display questionnaire
                                            transfer_questionnaire = st.session_state[transfer_q_key]
                                            actual_risk_id = st.session_state.get(f"{transfer_q_key}_risk_id", f"RSK-{threat_index:03d}")
                                            
                                            if 'error' in transfer_questionnaire:
                                                st.error(f"❌ Error: {transfer_questionnaire.get('error')}")
                                            else:
                                                # 🔧 FIX: Handle both 'sections' and 'questionnaire' keys
                                                sections = transfer_questionnaire.get('sections', transfer_questionnaire.get('questionnaire', []))
                                                if not sections:
                                                    st.error("❌ No sections found in questionnaire")
                                                else:
                                                    st.markdown("#### 📋 Risk Transfer Questionnaire")
                                                
                                                # Display AI-known risk context (read-only)
                                                st.markdown("##### 📊 Risk Context (Auto-filled by AI)")
                                                risk_ctx = transfer_questionnaire.get('risk_context', {})
                                                
                                                import html
                                                
                                                col1, col2 = st.columns(2)
                                                with col1:
                                                    st.markdown(f"**Risk ID:** {actual_risk_id}")
                                                    asset_name = html.unescape(risk_ctx.get('Asset', risk_ctx.get('asset', selected_asset.get('asset_name', 'N/A'))))
                                                    st.markdown(f"**Asset:** {asset_name}")
                                                    # Get risk rating from multiple possible keys
                                                    current_risk = risk_ctx.get('Risk Rating', risk_ctx.get('current_risk_rating', threat_data.get('risk_rating', 'N/A')))
                                                    st.markdown(f"**Current Risk Rating:** {format_risk_rating(current_risk)}")
                                                with col2:
                                                    threat_desc = html.unescape(risk_ctx.get('Threat', risk_ctx.get('risk_description', threat_name)))
                                                    st.markdown(f"**Risk Description:** {threat_desc}")
                                                    residual = risk_ctx.get('Residual Risk', risk_ctx.get('residual_risk', threat_data.get('residual_risk', 'N/A')))
                                                    st.markdown(f"**Residual Risk:** {format_risk_rating(residual)}")
                                                
                                                st.markdown("---")
                                                
                                                # EMAIL OPTION
                                                st.info("💡 **Choose how to complete the transfer questionnaire:**")
                                                col_opt1, col_opt2 = st.columns(2)
                                                with col_opt1:
                                                    st.markdown("### 📧 Send via Email")
                                                    st.caption("Send to third party")
                                                    email_transfer = st.text_input("Email", placeholder="vendor@company.com", key=f"email_tr_{threat_key}")
                                                    if st.button("📧 Send", key=f"send_tr_{threat_key}", type="primary", disabled=not email_transfer):
                                                        with st.spinner("📧 Sending..."):
                                                            try:
                                                                from email_sender import send_questionnaire_email
                                                                # 🆕 Prepare agent results for storage
                                                                # Get ORIGINAL Agent 2 threat data
                                                                agent_2_threats = st.session_state.get('risk_result', {}).get('threat_risk_quantification', [])
                                                                original_threat = next((t for t in agent_2_threats if t.get('threat') == threat_name), threat_data)
                                                                
                                                                agent_results = {
                                                                    'agent_1': st.session_state.get('impact_result', {}),
                                                                    'agent_2': st.session_state.get('risk_result', {}),
                                                                    'agent_3': st.session_state.get('control_result', {}),
                                                                    'selected_asset': st.session_state.get('selected_asset', {}),
                                                                    'threat_data': original_threat
                                                                }
                                                                result = send_questionnaire_email(
                                                                    recipient_email=email_transfer,
                                                                    asset_name=selected_asset.get('asset_name'),
                                                                    questionnaire=transfer_questionnaire,
                                                                    questionnaire_type='TRANSFER',
                                                                    agent_results=agent_results
                                                                )
                                                                if result and result.get('success'):
                                                                    st.success(f"✅ Email sent to {email_transfer}!")
                                                                    st.info(f"📋 Token: {result['token']}")
                                                                    st.caption("Moving to next threat...")
                                                                    st.session_state.current_decision_index += 1
                                                                    time.sleep(1)
                                                                    st.rerun()
                                                                else:
                                                                    st.error(f"❌ Failed to send email")
                                                            except Exception as e:
                                                                st.error(f"❌ Error: {str(e)}")
                                                with col_opt2:
                                                    st.markdown("### ✍️ Fill Manually")
                                                    st.info("👇 Scroll down")
                                                st.markdown("---")
                                                
                                                st.markdown("##### 📝 Transfer Details (Please Fill)")
                                                st.caption("Provide the following transfer-specific information:")
                                                
                                                # Render questionnaire (NO FORM - same pattern as ACCEPT)
                                                transfer_answers = {}
                                                
                                                # 🔧 FIX: Use sections variable from above
                                                for section_idx, section in enumerate(sections):
                                                    section_title = section.get('title') or section.get('section_title', 'Section')
                                                    st.markdown(f"##### {section_title}")
                                                    
                                                    # Get section description if available
                                                    section_desc = section.get('description', '')
                                                    if section_desc:
                                                        st.caption(section_desc)
                                                    
                                                    # Get questions - handle both 'questions' and 'fields' keys
                                                    questions = section.get('questions', section.get('fields', []))
                                                    
                                                    for q_idx, question in enumerate(questions):
                                                        # Handle multiple field name formats
                                                        q_id = question.get('id', question.get('question_id', question.get('field_id', question.get('field_name', 'Q'))))
                                                        # CRITICAL: field_name IS the question text for TRANSFER questionnaire
                                                        q_text = question.get('field_name') or question.get('text') or question.get('question_text') or question.get('question') or question.get('label') or question.get('description', 'Question')
                                                        q_type = question.get('type', question.get('question_type', question.get('field_type', 'text')))
                                                        q_help = question.get('help_text', question.get('help', ''))
                                                        q_required = question.get('required', False)
                                                        options = question.get('options', [])
                                                        
                                                        # Unique key with section/question indices
                                                        widget_key = f"transfer_{threat_key}_s{section_idx}_q{q_idx}_{q_id}"
                                                        default_value = st.session_state.get(widget_key, '')
                                                        
                                                        # ✅ FIX: Replace placeholder with actual Risk ID in default value
                                                        if not default_value or default_value == '':
                                                            default_value = question.get('value', '')
                                                        if 'AI_GENERATED_RISK_ID' in str(default_value) or ('risk' in q_text.lower() and 'id' in q_text.lower() and default_value == ''):
                                                            default_value = actual_risk_id
                                                        
                                                        # Add required indicator
                                                        if q_required:
                                                            q_text = f"{q_text} *"
                                                        
                                                        # Handle display-only fields (AI pre-filled)
                                                        if q_type == 'display':
                                                            display_value = question.get('value', '')
                                                            # ✅ FIX: Replace placeholder in display fields too
                                                            if 'AI_GENERATED_RISK_ID' in str(display_value):
                                                                display_value = actual_risk_id
                                                            st.info(f"**{q_text}**\n\n{display_value}")
                                                            transfer_answers[q_id] = display_value
                                                            continue
                                                        
                                                        # Render input based on type
                                                        if q_type in ['text_area', 'textarea']:
                                                            val = st.text_area(q_text, value=default_value or '', key=widget_key, help=q_help, height=100)
                                                            transfer_answers[q_id] = val
                                                        elif q_type == 'text':
                                                            val = st.text_input(q_text, value=default_value or '', key=widget_key, help=q_help)
                                                            transfer_answers[q_id] = val
                                                        elif q_type == 'number':
                                                            min_val = question.get('min', question.get('min_value', 0))
                                                            val = st.number_input(q_text, value=float(default_value) if default_value else 0.0, key=widget_key, help=q_help, min_value=float(min_val))
                                                            transfer_answers[q_id] = val
                                                        elif q_type == 'date':
                                                            from datetime import date
                                                            val = st.date_input(q_text, value=date.today(), key=widget_key, help=q_help)
                                                            transfer_answers[q_id] = val
                                                        elif q_type in ['select', 'dropdown']:
                                                            if options:
                                                                display_options = [opt.get('label', opt.get('value', str(opt))) if isinstance(opt, dict) else str(opt) for opt in options]
                                                                val = st.selectbox(q_text, options=display_options, key=widget_key, help=q_help)
                                                                transfer_answers[q_id] = val
                                                            else:
                                                                val = st.text_input(q_text, key=widget_key, help=q_help)
                                                                transfer_answers[q_id] = val
                                                        else:
                                                            # Default to text input
                                                            val = st.text_input(q_text, key=widget_key, help=q_help)
                                                            transfer_answers[q_id] = val
                                                
                                                # Submit button
                                                if st.button(f"✅ Submit & Generate Transfer Form", key=f"submit_transfer_{threat_key}", type="primary", use_container_width=True):
                                                    # Read values from session_state
                                                    transfer_answers_final = {}
                                                    # 🔧 FIX: Use sections variable and handle display fields
                                                    for section_idx, section in enumerate(sections):
                                                        for q_idx, question in enumerate(section.get('questions', section.get('fields', []))):
                                                            q_id = question.get('id', question.get('question_id', question.get('field_id', question.get('field_name', 'Q'))))
                                                            q_type = question.get('type', question.get('question_type', 'text'))
                                                            
                                                            # ✅ FIX: Handle display fields - get value from question, not session_state
                                                            if q_type == 'display':
                                                                transfer_answers_final[q_id] = question.get('value', '')
                                                            else:
                                                                widget_key = f"transfer_{threat_key}_s{section_idx}_q{q_idx}_{q_id}"
                                                                transfer_answers_final[q_id] = st.session_state.get(widget_key, '')
                                                    
                                                    # Convert dates to strings
                                                    for key, value in transfer_answers_final.items():
                                                        if hasattr(value, 'strftime'):
                                                            transfer_answers_final[key] = value.strftime('%Y-%m-%d')
                                                    
                                                    # Generate transfer form with retry
                                                    with st.spinner("🤖 Generating transfer form..."):
                                                        # ✅ FIX: Use actual_risk_id from session state
                                                        risk_context = {
                                                            'risk_id': actual_risk_id,
                                                            'asset_name': selected_asset.get('asset_name', 'Unknown'),
                                                            'threat_name': threat_name,
                                                            'inherent_risk_rating': threat_data.get('risk_rating', 0),
                                                            'residual_risk_rating': threat_data.get('residual_risk', 0)
                                                        }
                                                        
                                                        transfer_form = execute_agent_with_retry(
                                                            generate_transfer_form,
                                                            "Transfer Form Generator",
                                                            api_key=api_key,
                                                            risk_context=risk_context,
                                                            questionnaire_responses=transfer_answers_final,
                                                            questionnaire_structure=transfer_questionnaire
                                                        )
                                                        
                                                        if 'error' not in transfer_form:
                                                            # ✅ STORE FORM IN SESSION STATE
                                                            st.session_state[f"transfer_form_{threat_key}"] = transfer_form
                                                            st.success("✅ Transfer Form Generated!")
                                                            st.rerun()
                                                        else:
                                                            st.error(f"❌ Error: {transfer_form.get('error')}")
                                                
                                                # ✅ FIX: Display form OUTSIDE submit button block (like ACCEPT workflow)
                                                if f"transfer_form_{threat_key}" in st.session_state:
                                                    transfer_form = st.session_state[f"transfer_form_{threat_key}"]
                                                    
                                                    # Extract form from wrapper
                                                    form = transfer_form.get('risk_transfer_form', transfer_form)
                                                    
                                                    # Clean HTML entities
                                                    import html
                                                    def clean_html_recursive(obj):
                                                        if isinstance(obj, str):
                                                            return html.unescape(obj)
                                                        elif isinstance(obj, dict):
                                                            return {k: clean_html_recursive(v) for k, v in obj.items()}
                                                        elif isinstance(obj, list):
                                                            return [clean_html_recursive(item) for item in obj]
                                                        return obj
                                                    
                                                    form = clean_html_recursive(form)
                                                    
                                                    st.markdown("---")
                                                    st.success("✅ Transfer Form Generated!")
                                                    
                                                    # Display form heading
                                                    st.markdown("### 📋 Risk Transfer Form")
                                                    
                                                    # Display risk context summary (asset & threat)
                                                    if 'risk_context' in form and isinstance(form['risk_context'], dict):
                                                        risk_ctx = form['risk_context']
                                                        col1, col2 = st.columns(2)
                                                        with col1:
                                                            if 'asset' in risk_ctx:
                                                                st.info(f"**Asset:** {risk_ctx['asset']}")
                                                        with col2:
                                                            if 'threat' in risk_ctx:
                                                                st.info(f"**Threat:** {risk_ctx['threat']}")
                                                    
                                                    st.markdown("")  # Spacing
                                                    
                                                    # Display all sections
                                                    section_emoji_map = {
                                                        'risk identification': '⚠️',
                                                        'risk rating': '📊',
                                                        'risk transfer': '🔄',
                                                        'transfer management': '👥',
                                                        'ownership': '👥',
                                                        'review': '👥'
                                                    }
                                                    
                                                    if 'sections' in form and isinstance(form['sections'], list):
                                                        for section in form['sections']:
                                                            if isinstance(section, dict):
                                                                section_title = section.get('title', 'Section')
                                                                
                                                                # Get emoji based on keywords in title
                                                                emoji = '📌'
                                                                section_lower = section_title.lower()
                                                                for key, em in section_emoji_map.items():
                                                                    if key in section_lower:
                                                                        emoji = em
                                                                        break
                                                                
                                                                st.markdown(f"### {emoji} {section_title}")
                                                                
                                                                fields = section.get('fields', [])
                                                                for field in fields:
                                                                    if isinstance(field, dict):
                                                                        field_name = field.get('field_name', 'Field')
                                                                        field_value = field.get('value', 'N/A')
                                                                        st.markdown(f"**{field_name}:** {field_value}")
                                                                
                                                                st.markdown("")  # Spacing
                                                    
                                                    # Generation Date at bottom
                                                    st.markdown("---")
                                                    if transfer_form.get('generation_date'):
                                                        st.caption(f"📅 Generated: {transfer_form['generation_date']}")
                                                    
                                                    with st.expander("📄 View Raw JSON", expanded=False):
                                                        st.json(transfer_form)
                                                    
                                                    # Save to risk register
                                                    if st.button(f"💾 Save Transfer Form to Risk Register", key=f"save_transfer_{threat_key}", type="primary", use_container_width=True):
                                                        with st.spinner("💾 Saving..."):
                                                            try:
                                                                from phase2_risk_resolver.database.save_to_register import save_assessment_to_risk_register
                                                                
                                                                # Filter agent_2_results to include ONLY current threat
                                                                all_threats = st.session_state.risk_result.get('threat_risk_quantification', [])
                                                                current_threat_data = None
                                                                for t in all_threats:
                                                                    if t.get('threat') == threat_name:
                                                                        current_threat_data = t
                                                                        break
                                                                
                                                                if not current_threat_data:
                                                                    st.error(f"❌ Could not find threat data for: {threat_name}")
                                                                else:
                                                                    # Create filtered agent_2_results with only current threat
                                                                    filtered_agent_2 = {
                                                                        **st.session_state.risk_result,
                                                                        'threat_risk_quantification': [current_threat_data]
                                                                    }
                                                                    
                                                                    # ✅ DEBUG: Show what we're saving
                                                                    with st.expander("🔍 Debug: Data being saved", expanded=False):
                                                                        st.write("Threat name:", threat_name)
                                                                        st.write("Transfer form keys:", list(transfer_form.keys()) if isinstance(transfer_form, dict) else "Not a dict")
                                                                        st.json({'management_decision': 'TRANSFER', 'transfer_form': transfer_form})
                                                                    
                                                                    risk_ids = save_assessment_to_risk_register(
                                                                        asset_data=st.session_state.selected_asset, 
                                                                        agent_1_results=st.session_state.impact_result, 
                                                                        agent_2_results=filtered_agent_2,
                                                                        agent_3_results=st.session_state.control_result, 
                                                                        agent_4_results={'management_decision': 'TRANSFER', 'transfer_form': transfer_form}
                                                                    )
                                                                    
                                                                    if risk_ids and len(risk_ids) > 0:
                                                                        st.success(f"✅ Saved! Risk ID: {risk_ids[0]}")
                                                                        st.session_state.current_decision_index += 1
                                                                        st.rerun()
                                                                    else:
                                                                        st.error("❌ Save returned no Risk IDs")
                                                                        st.warning("⚠️ Check the console/terminal for detailed error messages")
                                                            except Exception as e:
                                                                st.error(f"❌ Save failed: {str(e)}")
                                                                import traceback
                                                                with st.expander("Debug"):
                                                                    st.code(traceback.format_exc())
                                        
                                        # ============================================================
                                        # TERMINATE WORKFLOW
                                        # ============================================================
                                        elif decision == "TERMINATE":
                                            # Check if questionnaire already generated
                                            terminate_q_key = f"terminate_questionnaire_{threat_key}"
                                            
                                            if terminate_q_key not in st.session_state:
                                                st.markdown("#### 📋 Step 1: Generate Termination Questionnaire")
                                                
                                                with st.spinner("🤖 Generating termination questionnaire..."):
                                                    # Get actual Risk ID from database
                                                    import sqlite3
                                                    try:
                                                        conn = sqlite3.connect('database/risk_register.db')
                                                        cursor = conn.cursor()
                                                        cursor.execute("SELECT MAX(CAST(SUBSTR(risk_id, 5) AS INTEGER)) FROM risks WHERE risk_id LIKE 'RSK-%'")
                                                        result = cursor.fetchone()
                                                        next_num = (result[0] or 0) + 1
                                                        actual_risk_id = f"RSK-{next_num:03d}"
                                                        conn.close()
                                                    except:
                                                        actual_risk_id = f"RSK-{threat_index:03d}"
                                                    
                                                    # Prepare risk context
                                                    risk_context = {
                                                        'risk_id': actual_risk_id,
                                                        'asset_name': selected_asset.get('asset_name', 'Unknown'),
                                                        'threat_name': threat_name,
                                                        'inherent_risk_rating': threat_data.get('risk_rating', 0),
                                                        'residual_risk_rating': threat_data.get('residual_risk', 0),
                                                        'control_gaps': threat_data.get('control_gaps', [])
                                                    }
                                                    
                                                    terminate_questionnaire = execute_agent_with_retry(
                                                        generate_terminate_questionnaire,
                                                        "Termination Questionnaire Generator",
                                                        risk_context=risk_context
                                                    )
                                                    
                                                    st.session_state[terminate_q_key] = terminate_questionnaire
                                                    st.session_state[f"{terminate_q_key}_risk_id"] = actual_risk_id
                                                    st.rerun()
                                            
                                            # Display questionnaire
                                            terminate_questionnaire = st.session_state[terminate_q_key]
                                            actual_risk_id = st.session_state.get(f"{terminate_q_key}_risk_id", f"RSK-{threat_index:03d}")
                                            
                                            if 'error' in terminate_questionnaire:
                                                st.error(f"❌ Error: {terminate_questionnaire.get('error')}")
                                            else:
                                                st.markdown("### 📋 Risk Termination Questionnaire")
                                                
                                                # Display AI-known risk context (read-only)
                                                st.markdown("##### 📊 Risk Context (Auto-filled by AI)")
                                                risk_ctx = terminate_questionnaire.get('risk_context', {})
                                                
                                                col1, col2 = st.columns(2)
                                                with col1:
                                                    st.markdown(f"**Risk ID:** {actual_risk_id}")
                                                    st.markdown(f"**Asset:** {risk_ctx.get('asset', selected_asset.get('asset_name', 'N/A'))}")
                                                    # Get current risk from threat_data (actual value)
                                                    current_risk = threat_data.get('risk_rating', 'N/A')
                                                    st.markdown(f"**Current Risk Rating:** {format_risk_rating(current_risk)}")
                                                with col2:
                                                    st.markdown(f"**Risk Description:** {risk_ctx.get('risk_description', threat_name)}")
                                                    # Get residual risk from threat_data (actual value)
                                                    residual = threat_data.get('residual_risk', 'N/A')
                                                    st.markdown(f"**Residual Risk:** {format_risk_rating(residual)}")
                                                
                                                st.markdown("---")
                                                # EMAIL OPTION
                                                st.info("💡 **Choose how to complete the termination questionnaire:**")
                                                col_opt1, col_opt2 = st.columns(2)
                                                with col_opt1:
                                                    st.markdown("### 📧 Send via Email")
                                                    st.caption("Send to stakeholder")
                                                    email_terminate = st.text_input("Email", placeholder="owner@company.com", key=f"email_tm_{threat_key}")
                                                    if st.button("📧 Send", key=f"send_tm_{threat_key}", type="primary", disabled=not email_terminate):
                                                        with st.spinner("📧 Sending..."):
                                                            try:
                                                                from email_sender import send_questionnaire_email
                                                                # Get ORIGINAL Agent 2 threat data
                                                                agent_2_threats = st.session_state.get('risk_result', {}).get('threat_risk_quantification', [])
                                                                original_threat = next((t for t in agent_2_threats if t.get('threat') == threat_name), threat_data)
                                                                
                                                                agent_results = {
                                                                    'agent_1': st.session_state.get('impact_result', {}),
                                                                    'agent_2': st.session_state.get('risk_result', {}),
                                                                    'agent_3': st.session_state.get('control_result', {}),
                                                                    'selected_asset': st.session_state.get('selected_asset', {}),
                                                                    'threat_data': original_threat
                                                                }
                                                                result = send_questionnaire_email(
                                                                    recipient_email=email_terminate,
                                                                    asset_name=selected_asset.get('asset_name'),
                                                                    questionnaire=terminate_questionnaire,
                                                                    questionnaire_type='TERMINATE',
                                                                    agent_results=agent_results
                                                                )
                                                                if result and result.get('success'):
                                                                    st.success(f"✅ Email sent to {email_terminate}!")
                                                                    st.info(f"📋 Token: {result['token']}")
                                                                    st.caption("Moving to next threat...")
                                                                    st.session_state.current_decision_index += 1
                                                                    time.sleep(1)
                                                                    st.rerun()
                                                                else:
                                                                    st.error(f"❌ Failed to send email")
                                                            except Exception as e:
                                                                st.error(f"❌ Error: {str(e)}")
                                                with col_opt2:
                                                    st.markdown("### ✍️ Fill Manually")
                                                    st.info("👇 Scroll down")
                                                st.markdown("---")
                                                
                                                st.markdown("##### 📝 Termination Details (Please Fill)")
                                                st.caption("Provide the following termination-specific information:")
                                                
                                                # Render questionnaire
                                                terminate_answers = {}
                                                
                                                for section_idx, section in enumerate(terminate_questionnaire.get('sections', [])):
                                                    section_title = section.get('title') or section.get('section_title', 'Section')
                                                    st.markdown(f"##### {section_title}")
                                                    
                                                    section_desc = section.get('description', '')
                                                    if section_desc:
                                                        st.caption(section_desc)
                                                    
                                                    questions = section.get('questions', section.get('fields', []))
                                                    
                                                    for q_idx, question in enumerate(questions):
                                                        q_id = question.get('id', question.get('question_id', question.get('field_id', question.get('field_name', f'Q{section_idx}_{q_idx}'))))
                                                        # CRITICAL: field_name IS the question text for TERMINATE questionnaire (same as TRANSFER)
                                                        q_text = question.get('field_name') or question.get('text') or question.get('question_text') or question.get('question') or question.get('label') or question.get('description', 'Question')
                                                        q_type = question.get('type', question.get('question_type', question.get('field_type', 'text')))
                                                        q_help = question.get('help_text', question.get('help', ''))
                                                        q_required = question.get('required', False)
                                                        options = question.get('options', [])
                                                        
                                                        widget_key = f"terminate_{threat_key}_s{section_idx}_q{q_idx}_{q_id}"
                                                        default_value = st.session_state.get(widget_key, '')
                                                        
                                                        if q_required:
                                                            q_text = f"{q_text} *"
                                                        
                                                        # 🆕 Display-only fields (AI pre-filled)
                                                        if q_type == 'display':
                                                            pre_filled_value = question.get('value', question.get('default_value', 'N/A'))
                                                            st.info(f"**{q_text}:** {pre_filled_value}")
                                                            terminate_answers[q_id] = pre_filled_value
                                                        
                                                        elif q_type in ['text_area', 'textarea']:
                                                            val = st.text_area(q_text, value=default_value or '', key=widget_key, help=q_help, height=100)
                                                            terminate_answers[q_id] = val
                                                        elif q_type == 'text':
                                                            val = st.text_input(q_text, value=default_value or '', key=widget_key, help=q_help)
                                                            terminate_answers[q_id] = val
                                                        elif q_type == 'number':
                                                            min_val = question.get('min', question.get('min_value', 0))
                                                            val = st.number_input(q_text, value=float(default_value) if default_value else 0.0, key=widget_key, help=q_help, min_value=float(min_val))
                                                            terminate_answers[q_id] = val
                                                        elif q_type == 'date':
                                                            from datetime import date
                                                            val = st.date_input(q_text, value=date.today(), key=widget_key, help=q_help)
                                                            terminate_answers[q_id] = val
                                                        elif q_type in ['select', 'dropdown']:
                                                            if options:
                                                                display_options = [opt.get('label', opt.get('value', str(opt))) if isinstance(opt, dict) else str(opt) for opt in options]
                                                                val = st.selectbox(q_text, options=display_options, key=widget_key, help=q_help)
                                                                terminate_answers[q_id] = val
                                                            else:
                                                                val = st.text_input(q_text, key=widget_key, help=q_help)
                                                                terminate_answers[q_id] = val
                                                        else:
                                                            val = st.text_input(q_text, key=widget_key, help=q_help)
                                                            terminate_answers[q_id] = val
                                                
                                                # Submit button
                                                if st.button(f"✅ Submit & Generate Termination Form", key=f"submit_terminate_{threat_key}", type="primary", use_container_width=True):
                                                    terminate_answers_final = {}
                                                    for section_idx, section in enumerate(terminate_questionnaire.get('sections', [])):
                                                        for q_idx, question in enumerate(section.get('questions', section.get('fields', []))):
                                                            q_id = question.get('id', question.get('question_id', question.get('field_id', question.get('field_name', f'Q{section_idx}_{q_idx}'))))
                                                            widget_key = f"terminate_{threat_key}_s{section_idx}_q{q_idx}_{q_id}"
                                                            terminate_answers_final[q_id] = st.session_state.get(widget_key, '')
                                                    
                                                    # Convert dates to strings
                                                    for key, value in terminate_answers_final.items():
                                                        if hasattr(value, 'strftime'):
                                                            terminate_answers_final[key] = value.strftime('%Y-%m-%d')
                                                    
                                                    # Generate termination form with retry
                                                    with st.spinner("🤖 Generating termination form..."):
                                                        risk_context = {
                                                            'risk_id': actual_risk_id,
                                                            'asset_name': selected_asset.get('asset_name', 'Unknown'),
                                                            'threat_name': threat_name,
                                                            'inherent_risk_rating': threat_data.get('risk_rating', 0),
                                                            'residual_risk_rating': threat_data.get('residual_risk', 0)
                                                        }
                                                        
                                                        from phase2_risk_resolver.agents.agent_4_terminate_form import generate_terminate_form
                                                        terminate_form = execute_agent_with_retry(
                                                            generate_terminate_form,
                                                            "Termination Form Generator",
                                                            api_key=api_key,
                                                            risk_context=risk_context,
                                                            questionnaire_responses=terminate_answers_final,
                                                            questionnaire_structure=terminate_questionnaire
                                                        )
                                                        
                                                        if 'error' not in terminate_form:
                                                            # ✅ STORE FORM IN SESSION STATE
                                                            st.session_state[f"terminate_form_{threat_key}"] = terminate_form
                                                            st.success("✅ Termination Form Generated!")
                                                            st.rerun()
                                                            
                                                        else:
                                                            st.error(f"❌ Error: {terminate_form.get('error')}")
                                                
                                                # ✅ FIX: Display form OUTSIDE submit button block (like ACCEPT and TRANSFER workflows)
                                                if f"terminate_form_{threat_key}" in st.session_state:
                                                    terminate_form = st.session_state[f"terminate_form_{threat_key}"]
                                                    
                                                    # Extract form from wrapper
                                                    form = terminate_form.get('risk_termination_form', terminate_form)
                                                    
                                                    # Clean HTML entities
                                                    import html
                                                    def clean_html_recursive(obj):
                                                        if isinstance(obj, str):
                                                            return html.unescape(obj)
                                                        elif isinstance(obj, dict):
                                                            return {k: clean_html_recursive(v) for k, v in obj.items()}
                                                        elif isinstance(obj, list):
                                                            return [clean_html_recursive(item) for item in obj]
                                                        return obj
                                                    
                                                    form = clean_html_recursive(form)
                                                    
                                                    st.markdown("---")
                                                    st.success("✅ Termination Form Generated!")
                                                    
                                                    # Display form heading
                                                    st.markdown("### 📋 Risk Termination Form")
                                                    st.markdown("")  # Spacing
                                                    
                                                    # 🆕 100% DYNAMIC - Display sections with smart emoji selection
                                                    if 'sections' in form and isinstance(form['sections'], list):
                                                        for section in form['sections']:
                                                            if isinstance(section, dict):
                                                                section_title = section.get('title', 'Section')
                                                                # Smart emoji based on keywords
                                                                emoji = '📌'
                                                                title_lower = section_title.lower()
                                                                if 'information' in title_lower or 'identification' in title_lower:
                                                                    emoji = '📊'
                                                                elif 'termination' in title_lower or 'details' in title_lower:
                                                                    emoji = '🚫'
                                                                elif 'approval' in title_lower or 'action' in title_lower:
                                                                    emoji = '✅'
                                                                elif 'status' in title_lower or 'closure' in title_lower:
                                                                    emoji = '🔒'
                                                                
                                                                st.markdown(f"### {emoji} {section_title}")
                                                                
                                                                fields = section.get('fields', [])
                                                                for field in fields:
                                                                    if isinstance(field, dict):
                                                                        field_name = field.get('field_name', 'Field')
                                                                        field_value = field.get('value', 'N/A')
                                                                        st.markdown(f"**{field_name}:** {field_value}")
                                                                
                                                                st.markdown("")  # Spacing
                                                    
                                                    # Generation Date at bottom
                                                    st.markdown("---")
                                                    if terminate_form.get('generation_date'):
                                                        st.caption(f"📅 Generated: {terminate_form['generation_date']}")
                                                    
                                                    with st.expander("📄 View Raw JSON", expanded=False):
                                                        st.json(terminate_form)
                                                    
                                                    # Save to risk register
                                                    if st.button(f"💾 Save Termination Form to Risk Register", key=f"save_terminate_{threat_key}", type="primary", use_container_width=True):
                                                        with st.spinner("💾 Saving..."):
                                                            try:
                                                                from phase2_risk_resolver.database.save_to_register import save_assessment_to_risk_register
                                                                
                                                                # Filter agent_2_results to include ONLY current threat
                                                                all_threats = st.session_state.risk_result.get('threat_risk_quantification', [])
                                                                current_threat_data = None
                                                                for t in all_threats:
                                                                    if t.get('threat') == threat_name:
                                                                        current_threat_data = t
                                                                        break
                                                                
                                                                if not current_threat_data:
                                                                    st.error(f"❌ Could not find threat data for: {threat_name}")
                                                                else:
                                                                    # Create filtered agent_2_results with only current threat
                                                                    filtered_agent_2 = {
                                                                        **st.session_state.risk_result,
                                                                        'threat_risk_quantification': [current_threat_data]
                                                                    }
                                                                    
                                                                    risk_ids = save_assessment_to_risk_register(
                                                                        asset_data=st.session_state.selected_asset, 
                                                                        agent_1_results=st.session_state.impact_result, 
                                                                        agent_2_results=filtered_agent_2,
                                                                        agent_3_results=st.session_state.control_result, 
                                                                        agent_4_results={'management_decision': 'TERMINATE', 'terminate_form': terminate_form}
                                                                    )
                                                                    
                                                                    if risk_ids and len(risk_ids) > 0:
                                                                        st.success(f"✅ Saved! Risk ID: {risk_ids[0]}")
                                                                        st.session_state.current_decision_index += 1
                                                                        st.rerun()
                                                                    else:
                                                                        st.error("❌ Save returned no Risk IDs")
                                                            except Exception as e:
                                                                st.error(f"❌ Save failed: {str(e)}")
                                                                import traceback
                                                                with st.expander("Debug"):
                                                                    st.code(traceback.format_exc())
                                        
                                        st.markdown("---")
                            
                            # Download button
                            st.download_button(
                                label="📥 Download Management Decisions (JSON)",
                                data=json.dumps(result, indent=2),
                                file_name=f"agent4_decisions_{selected_asset['asset_name'].replace(' ', '_')}.json",
                                mime="application/json",
                                use_container_width=True
                            )
                        
                        # Check if this is RTP questionnaire format (OLD FORMAT)
                        elif 'questions' in result or 'metadata' in result:
                            
                            # ============================================================
                            # NEW: CHECK IF DECISION ALREADY MADE
                            # ============================================================
                            
                            # If no treatment_decision in session state, show summary first
                            if 'treatment_decision' not in st.session_state:
                                # User hasn't made a decision yet - show summary first!
                                
                                st.success("✅ RTP Questionnaire Generated!")
                                
                                # Display metadata
                                if 'metadata' in result:
                                    metadata = result['metadata']
                                    st.markdown("### 🎯 Risk Treatment Decision Required")
                                    
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("Asset", metadata.get('asset_name', 'N/A'))
                                    with col2:
                                        # Count sections instead of threats
                                        total_sections = len(result.get('sections', []))
                                        st.metric("Questionnaire Sections", total_sections)
                                    with col3:
                                        st.metric("Generated", metadata.get('generation_date', 'N/A'))
                                
                                # Extract threat info from first section (handle both 'questions' and 'sections' structure)
                                questions_sections = result.get('questions', result.get('sections', []))
                                
                                # NEW: Extract threat info from risk_context if sections structure
                                if 'sections' in result and 'risk_context' in result:
                                    # New structure: threat info is in risk_context
                                    risk_ctx = result['risk_context']
                                    
                                    # Extract risk_rating - try multiple field names
                                    risk_rating_str = risk_ctx.get('risk_rating', risk_ctx.get('current_risk_rating', '0/5'))
                                    if isinstance(risk_rating_str, str) and '/' in risk_rating_str:
                                        risk_rating = float(risk_rating_str.split('/')[0].strip())
                                        risk_level_display = risk_rating_str
                                    else:
                                        risk_rating = float(risk_rating_str) if risk_rating_str else 0
                                        risk_level_display = f"{risk_rating}/5"
                                    
                                    # Extract residual_risk - try multiple field names
                                    residual_risk_str = risk_ctx.get('residual_risk_after_existing_controls', 
                                                                    risk_ctx.get('residual_risk_rating', 
                                                                    risk_ctx.get('residual_risk', '0/5')))
                                    if isinstance(residual_risk_str, str) and '/' in residual_risk_str:
                                        residual_risk = float(residual_risk_str.split('/')[0].strip())
                                    else:
                                        residual_risk = float(residual_risk_str) if residual_risk_str else 0
                                    
                                    # Control gaps - check in risk_context first, then Agent 3
                                    control_gaps = risk_ctx.get('control_gaps_identified', [])
                                    if not control_gaps and st.session_state.control_result:
                                        threat_controls = st.session_state.control_result.get('threat_control_evaluation', [])
                                        if threat_controls:
                                            first_threat = threat_controls[0]
                                            control_gaps = first_threat.get('control_gaps', [])
                                    
                                    threat_info = {
                                        'threat_name': risk_ctx.get('risk_description', 'Unknown'),
                                        'risk_rating': risk_rating,
                                        'risk_level': risk_level_display,
                                        'residual_risk': residual_risk,
                                        'control_gaps': control_gaps
                                    }
                                    
                                    # Find decision question in sections
                                    decision_question = None
                                    control_selection_question = None
                                    
                                    for section in questions_sections:
                                        if section.get('section_id') == 's1_treatment_decision':
                                            questions = section.get('questions', [])
                                            for q in questions:
                                                if 'treatment_option' in q.get('question_id', '').lower() or 'select_treatment' in q.get('question_id', '').lower():
                                                    decision_question = q
                                        elif section.get('section_id') == 's2_treatment_details_treat':
                                            questions = section.get('questions', [])
                                            for q in questions:
                                                if 'proposed_controls' in q.get('question_id', '').lower() or 'controls' in q.get('question_text', '').lower():
                                                    control_selection_question = q
                                
                                elif questions_sections:
                                    # Old structure: threat info in first section
                                    first_section = questions_sections[0]
                                    threat_info = first_section.get('threat_info', {})
                                    questions = first_section.get('questions', [])
                                    
                                    # Find Q1.1 (treatment decision question) and Q1.2 (controls)
                                    decision_question = None
                                    control_selection_question = None
                                    
                                    for q in questions:
                                        if q.get('question_id') == 'Q1.1':
                                            decision_question = q
                                        elif q.get('question_id') == 'Q1.2':
                                            control_selection_question = q
                                else:
                                    threat_info = {}
                                    decision_question = None
                                    control_selection_question = None
                                
                                # ============================================================
                                # SHOW DECISION SUMMARY
                                # ============================================================
                                
                                st.markdown("---")
                                st.markdown("## 🎯 Management Decision Required")
                                st.info("ℹ️ **Review the risk information below and select your treatment decision**")
                                
                                # Current risk status
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    risk_rating = threat_info.get('risk_rating', 0)
                                    risk_level_display = threat_info.get('risk_level', 'N/A')
                                    
                                    # Extract numeric value if it's a string like "4/5 (High)"
                                    if isinstance(risk_level_display, str) and '/' in risk_level_display:
                                        try:
                                            risk_rating = float(risk_level_display.split('/')[0])
                                        except:
                                            pass
                                    
                                    st.metric("Current Risk Rating", f"{risk_rating}/5", 
                                             delta="VERY HIGH" if risk_rating >= 4.5 else "HIGH" if risk_rating >= 3.5 else "MEDIUM")
                                with col2:
                                    st.metric("Risk Level", threat_info.get('risk_level', 'N/A'))
                                with col3:
                                    residual_risk = threat_info.get('residual_risk', 0)
                                    
                                    # Handle string format like "1.58/5"
                                    if isinstance(residual_risk, str) and '/' in str(residual_risk):
                                        try:
                                            residual_risk = float(str(residual_risk).split('/')[0])
                                        except:
                                            residual_risk = 0
                                    elif not isinstance(residual_risk, (int, float)):
                                        residual_risk = 0
                                    
                                    st.metric("Residual Risk", f"{residual_risk:.1f}/5")
                                with col4:
                                    control_gaps = threat_info.get('control_gaps', [])
                                    st.metric("Control Gaps", len(control_gaps))
                                
                                # Control gaps identified
                                st.markdown("### ⚠️ Control Gaps Identified")
                                if control_gaps:
                                    for idx, gap in enumerate(control_gaps, 1):
                                        if isinstance(gap, dict):
                                            st.warning(f"⚠️ **Gap {idx}:** {gap.get('gap_description', 'Unknown')}")
                                        else:
                                            st.warning(f"⚠️ **Gap {idx}:** {gap}")
                                else:
                                    st.info("No control gaps found")
                                
                                # Decision options info
                                st.markdown("### 🎯 Your Decision Options")
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.info("""
**🔧 TREAT the Risk:**
- Implement controls to reduce risk
- AI will generate treatment plan
- Select from recommended controls
- Requires budget and timeline
""")
                                
                                with col2:
                                    st.warning(f"""
**✅ ACCEPT the Risk:**
- Risk remains at **{risk_rating}/5**
- Requires management approval
- Must provide justification
- Mandatory periodic reviews
""")
                                
                                st.markdown("---")
























































                                if 'discovery_summary' in result:
                                    with st.expander("🔍 AI Discovery Summary", expanded=False):
                                        discovery = result['discovery_summary']
                                        
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            st.markdown("**Treatment Options:**")
                                            for opt in discovery.get('treatment_options_discovered', []):
                                                st.markdown(f"- {opt}")
                                            
                                            st.markdown("**Priority Levels:**")
                                            for pri in discovery.get('priority_levels_discovered', []):
                                                st.markdown(f"- {pri}")
                                        
                                        with col2:
                                            st.markdown("**Risk Owners:**")
                                            owners = discovery.get('risk_owners_discovered', [])
                                            for owner in owners[:10]:
                                                st.markdown(f"- {owner}")
                                            if len(owners) > 10:
                                                st.caption(f"... and {len(owners) - 10} more")
                                
                                # ============================================================
                                # DECISION BUTTONS
                                # ============================================================
                                
                                st.markdown("---")
                                st.markdown("## 🎯 What is your treatment decision?")
                                st.info("Based on the information above, select your treatment decision:")
                                
                                # Get options from decision question
                                decision_options = []
                                if decision_question and decision_question.get('options'):
                                    decision_options = decision_question['options']

                                    
                                    # ============================================================
                                    # DECISION CARDS - FULL TEXT WITH EXPANDERS
                                    # ============================================================
                                    
                                    st.markdown("### Select Your Treatment Decision:")
                                    
                                    # Show all 4 options as expandable cards
                                    for opt in decision_options:
                                        if isinstance(opt, dict):
                                            value = opt.get('value', '')
                                            label = opt.get('label', '')
                                            description = opt.get('description', '')
                                            recommendation = opt.get('recommendation', '')
                                            consequences = opt.get('consequences', '')
                                            cost = opt.get('estimated_cost', '')
                                            timeline = opt.get('typical_timeline', '')
                                            
                                            # Determine emoji
                                            if value == 'TREAT':
                                                emoji = "🔧"
                                                expanded = True  # TREAT expanded by default
                                            elif value == 'ACCEPT':
                                                emoji = "✅"
                                                expanded = False
                                            elif value == 'TRANSFER':
                                                emoji = "🚫"
                                                expanded = False
                                            elif value == 'TERMINATE':
                                                emoji = "⛔"
                                                expanded = False
                                            else:
                                                emoji = "❓"
                                                expanded = False
                                            
                                            # Create expander with full details
                                            with st.expander(f"{emoji} **{value}** - {label}", expanded=expanded):
                                                
                                                # Description (FULL TEXT)
                                                st.markdown(f"**Description:**")
                                                st.info(description)
                                                
                                                # Recommendation (FULL TEXT)
                                                if recommendation:
                                                    st.markdown(f"**Recommendation:**")
                                                    if "RECOMMENDED" in recommendation or "STRONGLY" in recommendation:
                                                        st.success(recommendation)
                                                    else:
                                                        st.warning(recommendation)
                                                
                                                # Consequences (FULL TEXT)
                                                if consequences:
                                                    st.markdown(f"**Consequences:**")
                                                    st.write(consequences)
                                                
                                                # Cost & Timeline
                                                col1, col2 = st.columns(2)
                                                with col1:
                                                    if cost:
                                                        st.markdown(f"**💰 Estimated Cost:**")
                                                        st.code(cost)
                                                with col2:
                                                    if timeline:
                                                        st.markdown(f"**⏱️ Timeline:**")
                                                        st.code(timeline)
                                                
                                                # Approval/Monitoring requirements
                                                approval = opt.get('approval_required', '')
                                                monitoring = opt.get('monitoring_required', '')
                                                
                                                if approval:
                                                    st.caption(f"✅ {approval}")
                                                if monitoring:
                                                    st.caption(f"📊 {monitoring}")
                                                
                                                # Selection button
                                                st.markdown("---")
                                                if st.button(f"✅ Select {value}", 
                                                           key=f"decision_{value}",
                                                           type="primary" if value == "TREAT" else "secondary",
                                                           use_container_width=True):
                                                    st.session_state.treatment_decision = value
                                                    st.rerun()
                            
                            # ============================================================
                            # STEP 1 & 2: DISPLAY QUESTIONNAIRE & COLLECT ANSWERS
                            # (Only after decision is made)
                            # ============================================================
                            
                            elif 'treatment_plan' not in st.session_state:
                                # Decision made, now show appropriate questionnaire
                                # BUT: Skip if we're already past the questionnaire stage
                                
                                decision = st.session_state.treatment_decision
                                
                                st.success(f"✅ You selected: **{decision}**")
                                
                                # Back button
                                if st.button("🔄 Change Decision", key="change_decision"):
                                    del st.session_state.treatment_decision
                                    st.rerun()
                                
                                st.markdown("---")
                                
                                # ============================================================
                                # IF ACCEPT: Show ACCEPT Questionnaire
                                # ============================================================
                                
                                if decision == "ACCEPT":
                                    # Mark that we're showing the questionnaire (prevents re-rendering on widget interactions)
                                    if 'showing_acceptance_questionnaire' not in st.session_state:
                                        st.session_state.showing_acceptance_questionnaire = True
                                    
                                    st.markdown("### 📝 Risk Acceptance Questionnaire")
                                    st.info("📝 **Step 1:** Fill out the questionnaire to document your risk acceptance")
                                    
                                    # Get threat info for context
                                    questions_sections = result.get('questions', result.get('sections', []))
                                    
                                    # Extract control gaps from Agent 3 results (NOT from RTP questionnaire)
                                    control_gaps = []
                                    if st.session_state.control_result:
                                        threat_controls = st.session_state.control_result.get('threat_control_evaluation', [])
                                        if threat_controls:
                                            first_threat = threat_controls[0]
                                            control_gaps = first_threat.get('control_gaps', [])
                                    
                                    # Get risk ratings from Agent 2
                                    risk_rating = 0
                                    if st.session_state.risk_result:
                                        threats = st.session_state.risk_result.get('threat_risk_quantification', [])
                                        if threats:
                                            first_threat = threats[0]
                                            risk_eval = first_threat.get('risk_evaluation_rating', {})
                                            if isinstance(risk_eval, dict):
                                                risk_rating = risk_eval.get('rating', 0)
                                            else:
                                                risk_rating = risk_eval
                                    
                                    # Get residual risk from Agent 3
                                    residual_risk = 0
                                    if st.session_state.control_result:
                                        threat_controls = st.session_state.control_result.get('threat_control_evaluation', [])
                                        if threat_controls:
                                            first_threat = threat_controls[0]
                                            residual_risk_data = first_threat.get('residual_risk', {})
                                            residual_risk = residual_risk_data.get('residual_risk_value', 0)
                                    
                                    # Generate acceptance questionnaire ONLY ONCE
                                    if 'acceptance_questionnaire' not in st.session_state:
                                        risk_context = {
                                            'risk_id': f"RISK-{result.get('metadata', {}).get('asset_name', 'UNKNOWN').replace(' ', '-')}-001",
                                            'asset_name': result.get('metadata', {}).get('asset_name', 'Unknown'),
                                            'threat_name': 'Security threats to Database Server',
                                            'inherent_risk_rating': risk_rating,
                                            'residual_risk_rating': residual_risk,
                                            'control_gaps': control_gaps,
                                        }
                                        
                                        acceptance_questionnaire = execute_agent_with_retry(generate_acceptance_questionnaire, "Acceptance Questionnaire Generator", risk_context=risk_context)
                                        st.session_state.acceptance_questionnaire = acceptance_questionnaire
                                    else:
                                        acceptance_questionnaire = st.session_state.acceptance_questionnaire

                                    # DEBUG: Show questionnaire structure
                                    with st.expander("🐛 DEBUG: View Questionnaire Structure", expanded=False):
                                        st.json(acceptance_questionnaire)
                                    
                                    # Check if questionnaire generation succeeded
                                    if 'error' in acceptance_questionnaire:
                                        st.error("❌ Failed to generate acceptance questionnaire")
                                        st.error(f"**Error:** {acceptance_questionnaire.get('error', 'Unknown error')}")
                                        
                                        if '429' in str(acceptance_questionnaire.get('error', '')):
                                            st.warning("⚠️ **API Quota Exhausted!**")
                                            st.info("""
                                            💡 **Solutions:**
                                            1. Wait 24 hours for quota reset
                                            2. Add more API keys to .env file (GEMINI_API_KEY_7, etc.)
                                            3. Upgrade to paid tier for higher limits
                                            
                                            Current limit: 20 requests/day per key (free tier)
                                            """)
                                        
                                        st.stop()
                                    
                                    if 'sections' not in acceptance_questionnaire:
                                        st.error("❌ Invalid questionnaire format - missing 'sections' key")
                                        st.json(acceptance_questionnaire)
                                        st.stop()

                                    # Render acceptance questionnaire - NO FORM (Streamlit form bug workaround)
                                    
                                    # Initialize form values storage
                                    if 'acceptance_form_values' not in st.session_state:
                                        st.session_state.acceptance_form_values = {}
                                    
                                    acceptance_answers = {}
                                    
                                    for section in acceptance_questionnaire['sections']:
                                        section_title = section.get('title') or section.get('section_title', 'Section')
                                        st.markdown(f"### {section_title}")
                                        if section.get('description'):
                                            st.info(section['description'])
                                        
                                        for question in section['questions']:
                                            q_id = question.get('id', question.get('question_id', 'Q'))
                                            q_text = question.get('text', question.get('question_text', 'Question'))
                                            q_type = question.get('type', question.get('question_type', 'text'))
                                            q_help = question.get('help_text', '')
                                            options = question.get('options', [])
                                            
                                            # Get default value from session state (persists across reruns)
                                            default_value = st.session_state.get(f"accept_{q_id}", '')
                                            
                                            # Render input WITHOUT form - values auto-save to session_state
                                            if q_type in ['text_area', 'textarea']:
                                                val = st.text_area(q_text, value=default_value or '', key=f"accept_{q_id}", help=q_help, height=100)
                                                acceptance_answers[q_id] = val
                                            elif q_type == 'text':
                                                val = st.text_input(q_text, value=default_value or '', key=f"accept_{q_id}", help=q_help)
                                                acceptance_answers[q_id] = val
                                            elif q_type == 'email':
                                                val = st.text_input(q_text, value=default_value or '', key=f"accept_{q_id}", help=q_help, placeholder="email@example.com")
                                                acceptance_answers[q_id] = val
                                            elif q_type == 'number':
                                                val = st.number_input(q_text, key=f"accept_{q_id}", help=q_help, min_value=0)
                                                acceptance_answers[q_id] = val
                                            elif q_type == 'date':
                                                from datetime import date
                                                val = st.date_input(q_text, value=date.today(), key=f"accept_{q_id}", help=q_help)
                                                acceptance_answers[q_id] = val
                                            elif q_type in ['select', 'dropdown']:
                                                if options:
                                                    display_options = []
                                                    for opt in options:
                                                        if isinstance(opt, dict):
                                                            display_options.append(opt.get('label', opt.get('value', str(opt))))
                                                        else:
                                                            display_options.append(str(opt))
                                                    val = st.selectbox(q_text, options=display_options, key=f"accept_{q_id}", help=q_help)
                                                    acceptance_answers[q_id] = val
                                                else:
                                                    val = st.text_input(q_text, key=f"accept_{q_id}", help=q_help)
                                                    acceptance_answers[q_id] = val
                                            elif q_type == 'radio':
                                                if options:
                                                    val = st.radio(q_text, options=options, key=f"accept_{q_id}", help=q_help)
                                                    acceptance_answers[q_id] = val
                                                else:
                                                    val = st.text_input(q_text, key=f"accept_{q_id}", help=q_help)
                                                    acceptance_answers[q_id] = val
                                            elif q_type in ['checkbox', 'multiselect']:
                                                if options:
                                                    st.markdown(f"**{q_text}**")
                                                    if q_help:
                                                        st.caption(q_help)
                                                    
                                                    selected = []
                                                    for idx, opt in enumerate(options):
                                                        if isinstance(opt, dict):
                                                            control_name = opt.get('label', opt.get('control_name', f'Control {idx+1}'))
                                                            control_desc = opt.get('description', '')
                                                            priority = opt.get('priority', 'N/A')
                                                            control_type = opt.get('control_type', 'N/A')
                                                            cost = opt.get('cost', 'N/A')
                                                            timeline = opt.get('timeline', 'N/A')
                                                            complexity = opt.get('complexity', 'N/A')
                                                            risk_reduction = opt.get('risk_reduction', 'N/A')
                                                            
                                                            with st.expander(f"✅ {control_name}", expanded=False):
                                                                col1, col2 = st.columns(2)
                                                                
                                                                with col1:
                                                                    st.markdown(f"**Description:** {control_desc}")
                                                                    st.markdown(f"**Priority:** {priority}")
                                                                    st.markdown(f"**Type:** {control_type}")
                                                                
                                                                with col2:
                                                                    st.markdown(f"**💰 Cost:** {cost}")
                                                                    st.markdown(f"**⏱️ Timeline:** {timeline}")
                                                                    st.markdown(f"**📉 Risk Reduction:** {risk_reduction}")
                                                                
                                                                st.markdown(f"**Complexity:** {complexity}")
                                                                
                                                                if st.checkbox(f"Select {control_name}", key=f"accept_{q_id}_opt_{idx}"):
                                                                    selected.append(opt)
                                                        else:
                                                            if st.checkbox(str(opt), key=f"accept_{q_id}_opt_{idx}"):
                                                                selected.append(str(opt))
                                                    
                                                    acceptance_answers[q_id] = selected
                                                else:
                                                    st.warning(f"⚠️ No options available for {q_text}")
                                                    acceptance_answers[q_id] = []
                                            else:
                                                val = st.text_input(q_text, key=f"accept_{q_id}", help=q_help)
                                                acceptance_answers[q_id] = val
                                    
                                    # Submit button OUTSIDE form
                                    submitted = st.button("✅ Submit & Generate Acceptance Form", type="primary", use_container_width=True, key="submit_acceptance_form")
                                    
                                    if submitted:
                                        # 🔧 FIX: Read values from session state AFTER form submission
                                        # Streamlit forms clear widget values, so we must read from st.session_state
                                        
                                        # DEBUG: Show ALL session state keys that start with 'accept_'
                                        with st.expander("🐛 DEBUG: Session State Keys", expanded=True):
                                            accept_keys = {k: v for k, v in st.session_state.items() if k.startswith('accept_')}
                                            st.markdown(f"**Found {len(accept_keys)} keys starting with 'accept_':**")
                                            for k, v in accept_keys.items():
                                                st.markdown(f"- `{k}`: `{v}` (type: {type(v).__name__})")
                                        
                                        acceptance_answers_final = {}
                                        for section in acceptance_questionnaire['sections']:
                                            for question in section['questions']:
                                                q_id = question.get('id', question.get('question_id', 'Q'))
                                                q_type = question.get('type', question.get('question_type', 'text'))
                                                q_text = question.get('text', question.get('question_text', 'Question'))
                                                
                                                # Read from session state using widget key
                                                widget_key = f"accept_{q_id}"
                                                
                                                if q_type in ['checkbox', 'multiselect']:
                                                    # For checkboxes, collect all selected options
                                                    selected = []
                                                    options = question.get('options', [])
                                                    for idx, opt in enumerate(options):
                                                        checkbox_key = f"accept_{q_id}_opt_{idx}"
                                                        if st.session_state.get(checkbox_key, False):
                                                            if isinstance(opt, dict):
                                                                selected.append({
                                                                    'control_name': opt.get('label', opt.get('control_name', f'Control {idx+1}')),
                                                                    'label': opt.get('label', opt.get('control_name', f'Control {idx+1}')),
                                                                    'description': opt.get('description', ''),
                                                                    'priority': opt.get('priority', 'N/A'),
                                                                    'control_type': opt.get('control_type', 'N/A'),
                                                                    'cost': opt.get('cost', 'N/A'),
                                                                    'timeline': opt.get('timeline', 'N/A'),
                                                                    'risk_reduction': opt.get('risk_reduction', 'N/A'),
                                                                    'complexity': opt.get('complexity', 'N/A')
                                                                })
                                                            else:
                                                                selected.append(str(opt))
                                                    acceptance_answers_final[q_id] = selected
                                                else:
                                                    # For other types, read directly from session state
                                                    value_from_state = st.session_state.get(widget_key, '')
                                                    
                                                    # ? CRITICAL FIX: For empty string values, check if there's a default in acceptance_form_values
                                                    if value_from_state == '' and 'acceptance_form_values' in st.session_state:
                                                        value_from_state = st.session_state.acceptance_form_values.get(q_id, '')
                                                    
                                                    acceptance_answers_final[q_id] = value_from_state
                                                    
                                                    # DEBUG: Show what we captured for this field
                                                    if 'SIGNATURE' in q_id.upper() or 'SIGNOFF' in q_text.upper():
                                                        st.warning(f"🐛 DEBUG: Signature field '{q_id}' ('{q_text}')")
                                                        st.code(f"Widget key: {widget_key}")
                                                        st.code(f"Value from session_state: '{value_from_state}'")
                                                        st.code(f"Is in session_state: {widget_key in st.session_state}")
                                        
                                        # Convert date objects to strings for JSON serialization
                                        for key, value in acceptance_answers_final.items():
                                            if hasattr(value, 'strftime'):
                                                acceptance_answers_final[key] = value.strftime('%Y-%m-%d')
                                        
                                        # Store in session state for persistence
                                        st.session_state.acceptance_form_values = acceptance_answers_final.copy()
                                        acceptance_answers = acceptance_answers_final

                                        # DEBUG: Show what we captured
                                        with st.expander("🐛 DEBUG: Captured Values Before Validation", expanded=True):
                                            st.markdown("### Values in acceptance_answers:")
                                            for k, v in acceptance_answers.items():
                                                st.markdown(f"**{k}:** `{v}` (type: {type(v).__name__}, empty: {not v or v == '' or v == []})") 

                                        # Validate ONLY truly required fields (skip optional ones)
                                        missing_critical = []
                                        
                                        # Define optional field patterns (case-insensitive)
                                        # CRITICAL FIX: Make most fields optional - only validate CRITICAL fields
                                        optional_patterns = ['CLIENT', 'CISO', 'EVIDENCE', 'APPROVAL_DATE', 'L1', 'L1_HEAD', 'FACILITY', 'BU_HEAD', 'BU_DU_HEAD', 'SIGNATURE', 'LOCATION', 'ENGAGEMENT', 'PROJECT', 'LOB', 'JUSTIFICATION']
                                        
                                        # Check each field from questionnaire structure
                                        for section in acceptance_questionnaire['sections']:
                                            for question in section['questions']:
                                                q_id = question.get('id', question.get('question_id', 'Q'))
                                                q_text = question.get('text', question.get('question_text', 'Question'))
                                                q_type = question.get('type', question.get('question_type', 'text'))
                                                q_required = question.get('required', True)  # Default to required
                                                
                                                # Skip if explicitly marked as not required
                                                if not q_required:
                                                    continue
                                                
                                                # Skip if matches optional patterns
                                                if any(pattern in q_id.upper() or pattern in q_text.upper() for pattern in optional_patterns):
                                                    continue
                                                
                                                # Check if field has value in acceptance_answers
                                                value = acceptance_answers.get(q_id)
                                                
                                                # Validate based on type
                                                is_empty = False
                                                if value is None:
                                                    is_empty = True
                                                elif isinstance(value, str) and value.strip() == '':
                                                    is_empty = True
                                                elif isinstance(value, list) and len(value) == 0:
                                                    is_empty = True
                                                elif isinstance(value, dict) and not any(value.values()):
                                                    is_empty = True
                                                
                                                if is_empty:
                                                    missing_critical.append(q_text)
                                        
                                        if missing_critical:
                                            st.error(f"❌ Please fill out the following required fields:")
                                            for field in missing_critical:
                                                st.warning(f"• {field}")
                                            st.info("ℹ️ Scroll up to fill out the missing fields, then click Submit again.")
                                            st.stop()
                                        
                                        # Store answers
                                        st.session_state.rtp_answers = {**acceptance_answers, 'Q1.1': 'ACCEPT'}

                                        # DEBUG: Show submitted answers
                                        with st.expander("🐛 DEBUG: View Submitted Answers", expanded=True):
                                            st.markdown("### 📋 Captured Answers:")
                                            st.json(acceptance_answers)
                                            st.markdown(f"**Total fields captured:** {len(acceptance_answers)}")
                                            
                                            # Show which fields are empty
                                            empty_fields = [k for k, v in acceptance_answers.items() if not v or v == '' or v == []]
                                            if empty_fields:
                                                st.warning(f"⚠️ **Empty fields:** {len(empty_fields)}")
                                                st.code(', '.join(empty_fields))
                                            else:
                                                st.success("✅ All fields have values!")

                                        st.info(" **Step 2:** Generating Risk Acceptance Form...")
                                        
                                        with st.spinner("⏳ Generating acceptance form..."):
                                            try:
                                                from phase2_risk_resolver.agents.agent_4_acceptance_form import generate_acceptance_form
                                                
                                                # DEBUG: Verify API key before calling
                                                if not api_key or api_key.strip() == '':
                                                    st.error("🔑 API key is empty! Attempting to retrieve from manager...")
                                                    try:
                                                        from api_key_manager import get_active_api_key
                                                        api_key = get_active_api_key()
                                                        if api_key:
                                                            st.success(f"🔑 Retrieved API key from manager (length: {len(api_key)})")
                                                        else:
                                                            st.error("🔑 Failed to retrieve API key from manager")
                                                            st.stop()
                                                    except Exception as e:
                                                        st.error(f"❌ Error getting API key: {str(e)}")
                                                        st.stop()
                                                else:
                                                    st.info(f"🔑 API key available (length: {len(api_key)})")
                                                
                                                # Recreate risk context for form generation
                                                risk_context = {
                                                    'risk_id': f"RISK-{result.get('metadata', {}).get('asset_name', 'UNKNOWN').replace(' ', '-')}-001",
                                                    'asset_name': result.get('metadata', {}).get('asset_name', 'Unknown'),
                                                    'threat_name': 'Security threats to Database Server',
                                                    'inherent_risk_rating': risk_rating,
                                                    'residual_risk_rating': residual_risk,
                                                    'control_gaps': control_gaps,
                                                    'threat_description': 'Security threats to Database Server',
                                                    'existing_controls': [],
                                                    'identified_date': datetime.now().strftime('%Y-%m-%d')
                                                }
                                                
                                                # Generate acceptance form (OPTIMIZED - no RAG lookup)
                                                acceptance_form = generate_acceptance_form(
                                                    risk_context=risk_context,
                                                    questionnaire_answers=acceptance_answers,
                                                    questionnaire_structure=acceptance_questionnaire,
                                                    api_key=api_key
                                                )
                                                
                                                # DEBUG: Show what was returned
                                                with st.expander("🐛 DEBUG: Raw Form Output", expanded=True):
                                                    st.json(acceptance_form)
                                                    st.markdown(f"**Type:** {type(acceptance_form)}")
                                                    if isinstance(acceptance_form, dict):
                                                        st.markdown(f"**Keys:** {list(acceptance_form.keys())}")
                                                        st.markdown(f"**Has 'error':** {'error' in acceptance_form}")
                                                
                                                # Check if form has error
                                                if isinstance(acceptance_form, dict) and 'error' in acceptance_form:
                                                    st.error(f"❌ Form generation failed: {acceptance_form.get('error')}")
                                                    st.stop()
                                                
                                                # Check if form is empty
                                                if not acceptance_form or (isinstance(acceptance_form, dict) and len(acceptance_form) == 0):
                                                    st.error("📋 Form is EMPTY! Agent returned nothing.")
                                                    st.stop()
                                                
                                                st.success(f"📋 Form has {len(acceptance_form)} sections")
                                                
                                                # Store in session state
                                                st.session_state.treatment_plan = {
                                                    'treatment_plan': {
                                                        'treatment_decision': 'ACCEPT',
                                                        'risk_owner': acceptance_answers.get('Q5.1', 'Unassigned'),
                                                        'priority': 'HIGH' if risk_context['inherent_risk_rating'] >= 4 else 'MEDIUM',
                                                        'target_completion_date': acceptance_form.get('validity', {}).get('valid_until_date'),
                                                    },
                                                    'acceptance_form': acceptance_form,
                                                    'rtp_answers': acceptance_answers,
                                                    'generation_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                                }
                                                
                                                st.success("✅ Risk Acceptance Form Generated!")
                                                st.rerun()
                                                
                                            except Exception as e:
                                                st.error(f"❌ Error: {str(e)}")
                                                import traceback
                                                with st.expander("Debug"):
                                                    st.code(traceback.format_exc())
                                
                                # ============================================================
                                # IF TREAT: Auto-Generate Treatment Plan (FULLY AGENTIC)
                                # ============================================================
                                
                                else:
                                    st.markdown("### 🔧 Auto-Generate Treatment Plan")
                                    st.info("🤖 **AI will auto-generate treatment plan from control gaps - No questionnaire needed!**")
                                    
                                    # 🔧 FIX: Check for both old and new structure
                                    questions_sections = result.get('questions', result.get('sections', []))
                                    
                                    # 🔧 FIX: Extract threat_info from risk_context if new structure
                                    if 'sections' in result and 'risk_context' in result:
                                        # New structure - get from risk_context
                                        risk_ctx = result['risk_context']
                                        
                                        # Extract risk_rating
                                        risk_rating_str = risk_ctx.get('risk_rating', risk_ctx.get('current_risk_rating', '0/5'))
                                        if isinstance(risk_rating_str, str) and '/' in risk_rating_str:
                                            risk_rating = float(risk_rating_str.split('/')[0].strip())
                                            risk_level_display = risk_rating_str
                                        else:
                                            risk_rating = float(risk_rating_str) if risk_rating_str else 0
                                            risk_level_display = f"{risk_rating}/5"
                                        
                                        # Extract residual_risk
                                        residual_risk_str = risk_ctx.get('residual_risk_after_existing_controls', 
                                                                        risk_ctx.get('residual_risk_rating', 
                                                                        risk_ctx.get('residual_risk', '0/5')))
                                        if isinstance(residual_risk_str, str) and '/' in residual_risk_str:
                                            residual_risk = float(residual_risk_str.split('/')[0].strip())
                                        else:
                                            residual_risk = float(residual_risk_str) if residual_risk_str else 0
                                        
                                        # 🔧 FIX: Get control gaps AND recommended controls from Agent 3
                                        control_gaps = risk_ctx.get('control_gaps_identified', [])
                                        recommended_controls = []
                                        
                                        if st.session_state.control_result:
                                            threat_controls = st.session_state.control_result.get('threat_control_evaluation', [])
                                            if threat_controls:
                                                first_threat = threat_controls[0]
                                                # Get gaps if not in risk_ctx
                                                if not control_gaps:
                                                    control_gaps = first_threat.get('control_gaps', [])
                                                # ? CRITICAL: Get recommended controls from Agent 3
                                                recommended_controls = first_threat.get('recommended_controls', [])
                                        
                                        threat_info = {
                                            'threat_name': risk_ctx.get('risk_description', 'Unknown'),
                                            'risk_rating': risk_rating,
                                            'risk_level': risk_level_display,
                                            'residual_risk': residual_risk,
                                            'control_gaps': control_gaps,
                                            'recommended_controls': recommended_controls,  # ? ADD THIS
                                            'risk_owner': 'IT Security Team'
                                        }
                                    elif questions_sections and len(questions_sections) > 0:
                                        # Old structure - get from first section
                                        first_section = questions_sections[0]
                                        threat_info = first_section.get('threat_info', {})
                                    else:
                                        threat_info = None
                                    
                                    if threat_info:
                                        
                                        # Display summary of what will be treated
                                        st.markdown("#### 📊 Risk Summary")
                                        col1, col2, col3, col4 = st.columns(4)
                                        
                                        with col1:
                                            control_gaps = threat_info.get('control_gaps', [])
                                            st.metric("Control Gaps", len(control_gaps), delta="🔴")
                                        
                                        with col2:
                                            risk_rating = threat_info.get('risk_rating', 0)
                                            st.metric("Risk Rating", f"{risk_rating}/5", delta="VERY HIGH" if risk_rating >= 4.5 else "HIGH")
                                        
                                        with col3:
                                            residual_risk = threat_info.get('residual_risk', 0)
                                            st.metric("Residual Risk", f"{residual_risk:.1f}/5")
                                        
                                        with col4:
                                            risk_level = threat_info.get('risk_level', 'Unknown')
                                            st.metric("Risk Level", risk_level)
                                        
                                        # 🆕 NEW: Show RECOMMENDED CONTROLS (not just gaps)
                                        st.markdown("#### ✅ Recommended Controls to Implement")
                                        
                                        # Get recommended controls from threat_info
                                        recommended_controls = threat_info.get('recommended_controls', [])
                                        
                                        if recommended_controls:
                                            st.success(f"🤖 Agent 3 discovered {len(recommended_controls)} controls to address the gaps")
                                            st.info("📋 **Select which controls you want to implement:**")
                                            
                                            # Initialize session state for selected controls
                                            if 'selected_controls_for_treatment' not in st.session_state:
                                                st.session_state.selected_controls_for_treatment = list(range(len(recommended_controls)))
                                            
                                            for idx, control in enumerate(recommended_controls):
                                                if isinstance(control, dict):
                                                    col_check, col_content = st.columns([0.1, 0.9])
                                                    
                                                    with col_check:
                                                        selected = st.checkbox(
                                                            "Select",
                                                            value=idx in st.session_state.selected_controls_for_treatment,
                                                            key=f"control_select_{idx}",
                                                            label_visibility="collapsed"
                                                        )
                                                        if selected and idx not in st.session_state.selected_controls_for_treatment:
                                                            st.session_state.selected_controls_for_treatment.append(idx)
                                                        elif not selected and idx in st.session_state.selected_controls_for_treatment:
                                                            st.session_state.selected_controls_for_treatment.remove(idx)
                                                    
                                                    with col_content:
                                                        control_name = control.get('control_name', control.get('control_id', f'Control {idx+1}'))
                                                        with st.expander(f"✅ {control_name}", expanded=False):
                                                            col1, col2 = st.columns(2)
                                                            
                                                            with col1:
                                                                st.markdown(f"**Control ID:** {control.get('control_id', 'N/A')}")
                                                                if control.get('category') and control.get('category') != 'N/A':
                                                                    st.markdown(f"**Category:** {control['category']}")
                                                                if control.get('source') and control.get('source') != 'N/A':
                                                                    st.markdown(f"**Source:** {control['source']}")
                                                                if control.get('description'):
                                                                    st.info(f"**Description:** {control['description']}")
                                                            
                                                            with col2:
                                                                if control.get('target_rating') and control.get('target_rating') != 'N/A':
                                                                    st.markdown(f"**Target Rating:** {control['target_rating']}")
                                                                st.markdown(f"**Priority:** {control.get('priority', 'MEDIUM')}")
                                                                if control.get('implementation_guidance'):
                                                                    st.success(f"**Guidance:** {control['implementation_guidance']}")
                                                            
                                                            # Show which gap this addresses
                                                            if control.get('addresses_gap'):
                                                                st.warning(f"⚠️ **Addresses Gap:** {control['addresses_gap']}")
                                                            
                                                            # Show ALL other fields dynamically
                                                            other_fields = {k: v for k, v in control.items() 
                                                                          if k not in ['control_name', 'control_id', 'category', 'source', 
                                                                                     'description', 'target_rating', 'priority', 
                                                                                     'implementation_guidance', 'addresses_gap'] 
                                                                          and v and v != 'N/A'}
                                                            if other_fields:
                                                                st.markdown("**Additional Details:**")
                                                                for key, value in other_fields.items():
                                                                    field_name = key.replace('_', ' ').title()
                                                                    st.caption(f"� {field_name}: {value}")
                                                else:
                                                    st.info(f"✅ Control {idx+1}: {control}")
                                            
                                            st.caption(f"📊 **{len(st.session_state.selected_controls_for_treatment)} of {len(recommended_controls)} controls selected**")
                                        
                                        else:
                                            # Fallback: Show control gaps if no recommended controls
                                            st.warning("⚠️ No recommended controls found in Agent 3 results")
                                            st.info("ℹ️ Showing control gaps instead:")
                                            
                                            control_gaps = threat_info.get('control_gaps', [])
                                            
                                            if control_gaps:
                                                # Initialize session state for selected gaps
                                                if 'selected_gaps_for_treatment' not in st.session_state:
                                                    st.session_state.selected_gaps_for_treatment = list(range(len(control_gaps)))
                                                
                                                for idx, gap in enumerate(control_gaps):
                                                    if isinstance(gap, dict):
                                                        col_check, col_content = st.columns([0.1, 0.9])
                                                        
                                                        with col_check:
                                                            selected = st.checkbox(
                                                                "Select",
                                                                value=idx in st.session_state.selected_gaps_for_treatment,
                                                                key=f"gap_select_{idx}",
                                                                label_visibility="collapsed"
                                                            )
                                                            if selected and idx not in st.session_state.selected_gaps_for_treatment:
                                                                st.session_state.selected_gaps_for_treatment.append(idx)
                                                            elif not selected and idx in st.session_state.selected_gaps_for_treatment:
                                                                st.session_state.selected_gaps_for_treatment.remove(idx)
                                                        
                                                        with col_content:
                                                            st.warning(f"**Gap {idx+1}:** {gap.get('gap_description', 'Unknown gap')}")
                                                            st.caption(f"⚠️ Severity: {gap.get('severity', 'N/A')}")
                                                            if gap.get('evidence'):
                                                                st.caption(f"*Evidence: {gap.get('evidence')}*")
                                                    else:
                                                        st.warning(f"**Gap {idx+1}:** {gap}")
                                                
                                                st.caption(f"📊 **{len(st.session_state.selected_gaps_for_treatment)} of {len(control_gaps)} gaps selected**")
                                            else:
                                                st.error("✅ No control gaps or recommended controls found!")
                                        
                                        st.markdown("---")
                                        st.markdown("#### 🤖 AI Treatment Plan Generation")
                                        st.info("""
**What AI will do:**
1. 🔍 Discover Treatment Plan template from your documents
2. 🔧 Generate implementation details for selected controls
3. 💰 Estimate resources, costs, and timelines
4. 📊 Define success metrics
5. ✅ Create complete treatment plan

**No questionnaire needed!**
                                        """)
                                        
                                        # Auto-generate button
                                        if st.button("🤖 Auto-Generate Treatment Plan", type="primary", use_container_width=True, key="auto_generate_treatment"):
                                            # 🔧 FIX: Check for selected CONTROLS (not gaps)
                                            recommended_controls = threat_info.get('recommended_controls', [])
                                            
                                            if recommended_controls:
                                                # User is selecting from recommended controls
                                                if not st.session_state.get('selected_controls_for_treatment', []):
                                                    st.error("❌ Please select at least one control to implement!")
                                                else:
                                                    with st.spinner("🤖 AI is generating treatment plan for selected controls..."):
                                                        try:
                                                            from phase2_risk_resolver.agents.agent_4_treatment_plan import generate_treatment_plan
                                                            
                                                            # 🔧 FIX: Get SELECTED CONTROLS (not gaps)
                                                            selected_indices = st.session_state.selected_controls_for_treatment
                                                            selected_controls = [recommended_controls[i] for i in selected_indices if i < len(recommended_controls)]
                                                            
                                                            # Get asset info from session state
                                                            selected_asset_data = st.session_state.get('selected_asset') or {}
                                                            asset_name = selected_asset_data.get('asset_name', 'Unknown Asset')
                                                            asset_type = selected_asset_data.get('asset_type', 'Unknown')
                                                            
                                                            # DEBUG: Show what we're passing
                                                            st.info(f"🐛 DEBUG: Asset Name = '{asset_name}', Asset Type = '{asset_type}'")
                                                            st.info(f"🐛 DEBUG: Selected {len(selected_controls)} controls: {[c.get('control_name', c.get('control_id', 'N/A')) for c in selected_controls]}")
                                                            
                                                            # 🔧 FIX: Pass SELECTED CONTROLS (not gaps) to treatment plan generator
                                                            risk_data = {
                                                                'asset_name': asset_name,
                                                                'asset_type': asset_type,
                                                                'risk_rating': threat_info.get('risk_rating', 0),
                                                                'risk_level': threat_info.get('risk_level', 'Unknown'),
                                                                'residual_risk': threat_info.get('residual_risk', 0),
                                                                'selected_controls': selected_controls,  # ? PASS CONTROLS
                                                                'control_gaps': threat_info.get('control_gaps', []),  # Keep gaps for context
                                                                'risk_owner': threat_info.get('risk_owner', 'IT Security Team')
                                                            }
                                                            
                                                            # 🆕 NEW: Call fully agentic function with API key rotation
                                                            treatment_plan_result = execute_agent_with_retry(
                                                                agent_function=generate_treatment_plan,
                                                                agent_name="Agent 4: Treatment Plan",
                                                                agent_3_results=st.session_state.control_result,
                                                                risk_data=risk_data
                                                            )
                                                            
                                                            if 'error' in treatment_plan_result:
                                                                st.error(f"❌ Error: {treatment_plan_result['error']}")
                                                                if 'raw_output' in treatment_plan_result:
                                                                    with st.expander("View Raw Output"):
                                                                        st.text(treatment_plan_result['raw_output'][:1000])
                                                            else:
                                                                # Store in session state WITH selected controls info
                                                                st.session_state.treatment_plan = {
                                                                    'treatment_plan': treatment_plan_result,
                                                                    'rtp_answers': {'Q1.1': 'TREAT'},  # Minimal for compatibility
                                                                    'generation_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                                    'risk_rating': risk_data['risk_rating'],
                                                                    'residual_risk': risk_data['residual_risk'],
                                                                    'selected_controls': selected_controls,  # Store which controls were selected
                                                                    'selected_control_count': len(selected_controls)  # Store count for display
                                                                }
                                                                st.success("✅ Treatment Plan Auto-Generated!")
                                                                st.info("ℹ️ **Scroll down to review your treatment plan**")
                                                                st.rerun()
                                                        except Exception as e:
                                                            st.error(f"❌ Error: {str(e)}")
                                                            import traceback
                                                            with st.expander("Debug"):
                                                                st.code(traceback.format_exc())
                                            else:
                                                # Fallback: User is selecting from gaps (old behavior)
                                                if not st.session_state.get('selected_gaps_for_treatment', []):
                                                    st.error("❌ Please select at least one control gap to treat!")
                                                else:
                                                    with st.spinner("🤖 AI is discovering template structure and generating treatment plan..."):
                                                        try:
                                                            from phase2_risk_resolver.agents.agent_4_treatment_plan import generate_treatment_plan
                                                            
                                                            # Filter selected gaps only
                                                            selected_indices = st.session_state.selected_gaps_for_treatment
                                                            selected_gaps = [control_gaps[i] for i in selected_indices if i < len(control_gaps)]
                                                            
                                                            # Get asset info from session state
                                                            selected_asset_data = st.session_state.get('selected_asset') or {}
                                                            asset_name = selected_asset_data.get('asset_name', 'Unknown Asset')
                                                            asset_type = selected_asset_data.get('asset_type', 'Unknown')
                                                            
                                                            # DEBUG: Show what we're passing
                                                            st.info(f"🐛 DEBUG: Asset Name = '{asset_name}', Asset Type = '{asset_type}'")
                                                            st.info(f"🐛 DEBUG: Selected {len(selected_gaps)} gaps with control_ids: {[g.get('control_id', 'N/A') for g in selected_gaps]}")
                                                            
                                                            # Prepare risk data
                                                            risk_data = {
                                                                'asset_name': asset_name,
                                                                'asset_type': asset_type,
                                                                'risk_rating': threat_info.get('risk_rating', 0),
                                                                'risk_level': threat_info.get('risk_level', 'Unknown'),
                                                                'residual_risk': threat_info.get('residual_risk', 0),
                                                                'control_gaps': selected_gaps,
                                                                'risk_owner': threat_info.get('risk_owner', 'IT Security Team')
                                                            }
                                                        
                                                            # 🆕 NEW: Call fully agentic function with API key rotation
                                                            treatment_plan_result = execute_agent_with_retry(
                                                                agent_function=generate_treatment_plan,
                                                                agent_name="Agent 4: Treatment Plan",
                                                                agent_3_results=st.session_state.control_result,
                                                                risk_data=risk_data
                                                            )
                                                            
                                                            if 'error' in treatment_plan_result:
                                                                st.error(f"❌ Error: {treatment_plan_result['error']}")
                                                                if 'raw_output' in treatment_plan_result:
                                                                    with st.expander("View Raw Output"):
                                                                        st.text(treatment_plan_result['raw_output'][:1000])
                                                            else:
                                                                # Store in session state WITH selected gaps info
                                                                st.session_state.treatment_plan = {
                                                                    'treatment_plan': treatment_plan_result,
                                                                    'rtp_answers': {'Q1.1': 'TREAT'},  # Minimal for compatibility
                                                                    'generation_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                                    'risk_rating': risk_data['risk_rating'],
                                                                    'residual_risk': risk_data['residual_risk'],
                                                                    'selected_gaps': selected_gaps,  # Store which gaps were selected
                                                                    'selected_gap_count': len(selected_gaps)  # Store count for display
                                                                }
                                                                st.success("✅ Treatment Plan Auto-Generated!")
                                                                st.info("ℹ️ **Scroll down to review your treatment plan**")
                                                                st.rerun()
                                                        except Exception as e:
                                                            st.error(f"❌ Error: {str(e)}")
                                                            import traceback
                                                            with st.expander("Debug"):
                                                                st.code(traceback.format_exc())
                                    else:
                                        st.warning("⚠️ No questionnaire data available")
                            
                            # ============================================================
                            # STEP 3: DISPLAY TREATMENT PLAN (keep existing code)
                            # ============================================================
                            
                            # ============================================================
                            # STEP 3: DISPLAY TREATMENT PLAN
                            # ============================================================
                            
                            else:
                                # Check if this is acceptance form or treatment plan
                                treatment_plan_data = st.session_state.treatment_plan
                                
                                if 'acceptance_form' in treatment_plan_data:
                                    # ACCEPTANCE FORM DISPLAY
                                    st.success("✅ Risk Acceptance Form Generated!")
                                    
                                    st.markdown("## 📋 Risk Acceptance Form")
                                    st.info("✅ **Step 2 Complete:** Review your acceptance form below")
                                    
                                    acceptance_form = treatment_plan_data['acceptance_form']
                                    
                                    # FULLY DYNAMIC DISPLAY - Works with ANY structure agent generates
                                    if isinstance(acceptance_form, dict):
                                        # Iterate through ALL top-level keys dynamically
                                        for section_key, section_value in acceptance_form.items():
                                            # Skip internal/metadata fields
                                            if section_key.startswith('_'):
                                                continue
                                            
                                            # Create section title from key
                                            section_title = section_key.replace('_', ' ').title()
                                            
                                            # Add emoji based on section name
                                            if 'risk' in section_key.lower():
                                                emoji = "✅"
                                            elif 'project' in section_key.lower() or 'engagement' in section_key.lower():
                                                emoji = "�"
                                            elif 'accept' in section_key.lower():
                                                emoji = "?"
                                            elif 'monitor' in section_key.lower():
                                                emoji = "✅"
                                            elif 'valid' in section_key.lower() or 'date' in section_key.lower():
                                                emoji = "✅"
                                            elif 'approval' in section_key.lower():
                                                emoji = "?"
                                            elif 'metadata' in section_key.lower():
                                                emoji = "✅"
                                            else:
                                                emoji = "✅"
                                            
                                            st.markdown(f"### {emoji} {section_title}")
                                            
                                            # Display section content dynamically
                                            if isinstance(section_value, dict):
                                                # If it's a dict, show as key-value pairs
                                                
                                                # Check if it's a table-like structure (approvals, etc.)
                                                if all(isinstance(v, dict) for v in section_value.values()):
                                                    # Table format (like approvals)
                                                    table_data = []
                                                    for role, details in section_value.items():
                                                        if isinstance(details, dict):
                                                            row = {"Role": role.replace('_', ' ').title()}
                                                            row.update({k.replace('_', ' ').title(): v for k, v in details.items()})
                                                            table_data.append(row)
                                                    
                                                    if table_data:
                                                        df = pd.DataFrame(table_data)
                                                        st.dataframe(df, use_container_width=True, hide_index=True)
                                                else:
                                                    # Regular key-value display
                                                    # Split into columns for better layout
                                                    items = list(section_value.items())
                                                    
                                                    # Display in 2 columns if more than 3 items
                                                    if len(items) > 3:
                                                        col1, col2 = st.columns(2)
                                                        mid = len(items) // 2
                                                        
                                                        with col1:
                                                            for key, value in items[:mid]:
                                                                field_name = key.replace('_', ' ').title()
                                                                if isinstance(value, list):
                                                                    # Check if list contains dicts (like compensating controls)
                                                                    if value and isinstance(value[0], dict):
                                                                        st.markdown(f"**{field_name}:**")
                                                                        for idx, item in enumerate(value, 1):
                                                                            with st.expander(f"✅ {item.get('control_name', item.get('label', f'Item {idx}'))}", expanded=False):
                                                                                for k, v in item.items():
                                                                                    if k not in ['control_name', 'label']:
                                                                                        st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")
                                                                    else:
                                                                        # Simple list - bullet points
                                                                        st.markdown(f"**{field_name}:**")
                                                                        for item in value:
                                                                            st.markdown(f"- {item}")
                                                                elif isinstance(value, dict):
                                                                    # Format dict as key-value pairs
                                                                    st.markdown(f"**{field_name}:**")
                                                                    for k, v in value.items():
                                                                        st.markdown(f"- **{k.replace('_', ' ').title()}:** {v}")
                                                                else:
                                                                    st.markdown(f"**{field_name}:** {value}")
                                                        
                                                        with col2:
                                                            for key, value in items[mid:]:
                                                                field_name = key.replace('_', ' ').title()
                                                                if isinstance(value, list):
                                                                    # Check if list contains dicts (like compensating controls)
                                                                    if value and isinstance(value[0], dict):
                                                                        st.markdown(f"**{field_name}:**")
                                                                        for idx, item in enumerate(value, 1):
                                                                            with st.expander(f"✅ {item.get('control_name', item.get('label', f'Item {idx}'))}", expanded=False):
                                                                                for k, v in item.items():
                                                                                    if k not in ['control_name', 'label']:
                                                                                        st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")
                                                                    else:
                                                                        # Simple list - bullet points
                                                                        st.markdown(f"**{field_name}:**")
                                                                        for item in value:
                                                                            st.markdown(f"- {item}")
                                                                elif isinstance(value, dict):
                                                                    # Format dict as key-value pairs
                                                                    st.markdown(f"**{field_name}:**")
                                                                    for k, v in value.items():
                                                                        st.markdown(f"- **{k.replace('_', ' ').title()}:** {v}")
                                                                else:
                                                                    st.markdown(f"**{field_name}:** {value}")
                                                    else:
                                                        # Single column for few items
                                                        for key, value in items:
                                                            field_name = key.replace('_', ' ').title()
                                                            if isinstance(value, list):
                                                                # Check if list contains dicts (like compensating controls)
                                                                if value and isinstance(value[0], dict):
                                                                    st.markdown(f"**{field_name}:**")
                                                                    for idx, item in enumerate(value, 1):
                                                                        with st.expander(f"✅ {item.get('control_name', item.get('label', f'Item {idx}'))}", expanded=False):
                                                                            for k, v in item.items():
                                                                                if k not in ['control_name', 'label']:
                                                                                    st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")
                                                                else:
                                                                    # Simple list - bullet points
                                                                    st.markdown(f"**{field_name}:**")
                                                                    for item in value:
                                                                        st.markdown(f"- {item}")
                                                            elif isinstance(value, dict):
                                                                # Format dict as key-value pairs
                                                                st.markdown(f"**{field_name}:**")
                                                                for k, v in value.items():
                                                                    st.markdown(f"- **{k.replace('_', ' ').title()}:** {v}")
                                                            elif len(str(value)) > 100:
                                                                # Long text in info box
                                                                st.markdown(f"**{field_name}:**")
                                                                st.info(value)
                                                            else:
                                                                st.markdown(f"**{field_name}:** {value}")
                                            
                                            elif isinstance(section_value, list):
                                                # If it's a list, show as bullet points or table
                                                if section_value and isinstance(section_value[0], dict):
                                                    # ? SPECIAL HANDLING: Check if this is compensating controls
                                                    if 'compensating' in section_key.lower() or 'control' in section_key.lower():
                                                        # Format controls with rich display
                                                        for idx, control in enumerate(section_value, 1):
                                                            with st.expander(f"✅ Control {idx}: {control.get('control_name', control.get('label', 'Control'))}", expanded=False):
                                                                col1, col2 = st.columns(2)
                                                                
                                                                with col1:
                                                                    if control.get('description'):
                                                                        st.markdown(f"**Description:** {control['description']}")
                                                                    if control.get('priority'):
                                                                        st.markdown(f"**Priority:** {control['priority']}")
                                                                    if control.get('control_type'):
                                                                        st.markdown(f"**Type:** {control['control_type']}")
                                                                
                                                                with col2:
                                                                    if control.get('cost'):
                                                                        st.markdown(f"**💰 Cost:** {control['cost']}")
                                                                    if control.get('timeline'):
                                                                        st.markdown(f"**⏱️ Timeline:** {control['timeline']}")
                                                                    if control.get('risk_reduction'):
                                                                        st.markdown(f"**📉 Risk Reduction:** {control['risk_reduction']}")
                                                                
                                                                if control.get('complexity'):
                                                                    st.markdown(f"**Complexity:** {control['complexity']}")
                                                    else:
                                                        # List of dicts -> table
                                                        # Convert to safe format for dataframe (handle ALL nested types)
                                                        safe_data = []
                                                        for item in section_value:
                                                            safe_item = {}
                                                            for k, v in item.items():
                                                                # Convert ANY complex type to string for Arrow compatibility
                                                                if isinstance(v, (list, dict, tuple, set)):
                                                                    safe_item[k] = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                                                                elif v is None:
                                                                    safe_item[k] = ""  # Convert None to empty string
                                                                else:
                                                                    safe_item[k] = v
                                                            safe_data.append(safe_item)
                                                        
                                                        df = pd.DataFrame(safe_data)
                                                        st.dataframe(df, use_container_width=True, hide_index=True)
                                                else:
                                                    # Simple list -> bullet points
                                                    for item in section_value:
                                                        st.markdown(f"- {item}")
                                            
                                            else:
                                                # Simple value
                                                st.write(section_value)
                                            
                                            st.markdown("---")
                                        
                                        # Raw JSON in expander (for technical users) - Use code block to prevent HTML encoding
                                        with st.expander("📄 View Raw JSON", expanded=False):
                                            st.code(json.dumps(acceptance_form, indent=2), language="json")
                                    
                                    elif isinstance(acceptance_form, str):
                                        # Markdown display
                                        st.markdown(acceptance_form)
                                    
                                    # Download button
                                    st.markdown("---")
                                    if isinstance(acceptance_form, str):
                                        st.download_button(
                                            label="📥 Download Acceptance Form (Markdown)",
                                            data=acceptance_form,
                                            file_name=f"Risk_Acceptance_Form_{datetime.now().strftime('%Y%m%d')}.md",
                                            mime="text/markdown",
                                            use_container_width=True
                                        )
                                    else:
                                        st.download_button(
                                            label="📥 Download Acceptance Form (JSON)",
                                            data=json.dumps(acceptance_form, indent=2),
                                            file_name=f"Risk_Acceptance_Form_{datetime.now().strftime('%Y%m%d')}.json",
                                            mime="application/json",
                                            use_container_width=True
                                        )
                                    
                                    # Save to database button
                                    if st.button("💾 Save Acceptance Form to Risk Register", type="primary", use_container_width=True):
                                        with st.spinner("💾 Saving to database..."):
                                            try:
                                                from phase2_risk_resolver.database.save_to_register import save_assessment_to_risk_register
                                                
                                                # Enhance decision result with acceptance form
                                                enhanced_decision = {
                                                    **result,
                                                    'rtp_answers': st.session_state.rtp_answers,
                                                    'acceptance_form': acceptance_form,
                                                    'treatment_plan': treatment_plan_data.get('treatment_plan', {}),
                                                    'completed': True
                                                }
                                                
                                                risk_ids = save_assessment_to_risk_register(
                                                    asset_data=selected_asset,
                                                    agent_1_results=st.session_state.impact_result,
                                                    agent_2_results=st.session_state.risk_result,
                                                    agent_3_results=st.session_state.control_result,
                                                    agent_4_results=enhanced_decision
                                                )
                                                
                                                st.session_state.risk_ids = risk_ids
                                                st.session_state.output_result = {'status': 'saved', 'risk_ids': risk_ids}
                                                
                                                st.success(f"✅ Saved! Risk IDs: {', '.join(risk_ids)}")
                                                st.info("ℹ️ **View in Risk Register page!**")
                                                
                                            except Exception as e:
                                                st.error(f"❌ Error: {str(e)}")
                                
                                else:
                                    # TREATMENT PLAN DISPLAY (original code)
                                    st.success("📋 Treatment Plan Generated!")
                                    
                                    st.markdown("### 📋 Risk Treatment Plan")
                                    st.info("✅ **Step 2 Complete:** Review your treatment plan below")
                                    
                                    treatment_plan = treatment_plan_data.get('treatment_plan', {})
                                    
                                    # Summary metrics
                                    col1, col2, col3, col4 = st.columns(4)
                                    
                                    with col1:
                                        decision = treatment_plan.get('treatment_option', 'TREAT')
                                        color = "🔴" if decision == "TREAT" else "🟢"
                                        st.metric("Decision", decision, delta=color)
                                    
                                    with col2:
                                        st.metric("Priority", (treatment_plan.get('treatment_actions', [])[0].get('implementation_priority', 'N/A') if treatment_plan.get('treatment_actions', []) else 'N/A'))
                                    
                                    with col3:
                                        total_actions = len(treatment_plan.get('treatment_actions', []))
                                        st.metric("Total Actions", total_actions)
                                    
                                    with col4:
                                        summary = treatment_plan.get('summary', {})
                                        st.metric("Duration", f"{summary.get('total_duration_days', 0)} days")
                                    
                                    st.markdown("---")
                                    
                                    # Treatment Actions
                                    st.markdown("###  Treatment Actions")
                                    
                                    actions = treatment_plan.get('treatment_actions', [])
                                    
                                    for action in actions:
                                        # Dynamic display - show ALL fields from action
                                        title = f"{action.get('action_id', 'ACTION')}: {action.get('control_gap', action.get('title', 'Action'))}"
                                        with st.expander(f"**{title}**", expanded=False):
                                            # Display all fields dynamically
                                            for key, value in action.items():
                                                if value and key not in ['action_id', 'control_gap', 'title']:
                                                    # Format field name
                                                    field_name = key.replace('_', ' ').title()
                                                    
                                                    # Special formatting for specific fields
                                                    if key == 'implementation_priority':
                                                        priority_color = "🔴" if value == "CRITICAL" else "🟡" if value == "HIGH" else "🟢"
                                                        st.metric(field_name, f"{priority_color} {value}")
                                                    elif key in ['estimated_cost', 'cost', 'total_cost']:
                                                        st.metric(f"📊 {field_name}", value)
                                                    elif key in ['estimated_duration_days', 'duration', 'duration_days']:
                                                        st.metric(f"📊 {field_name}", f"{value} days")
                                                    elif key in ['proposed_start_date', 'proposed_completion_date', 'actual_start_date', 'actual_completion_date']:
                                                        st.caption(f"**📊 {field_name}:**")
                                                        st.info(value if value else 'TBD')
                                                    elif key in ['status', 'implementation_responsibility', 'risk_owner']:
                                                        st.caption(f"**{field_name}:**")
                                                        st.info(value)
                                                    elif isinstance(value, (list, dict)):
                                                        st.caption(f"**{field_name}:**")
                                                        st.json(value)
                                                    else:
                                                        st.markdown(f"**{field_name}:** {value}")
                                                    
                                                    st.markdown("")
                                    
                                    # Expected Outcomes
                                    st.markdown("---")
                                    st.markdown("### 🎯 Expected Outcomes")
                                    
                                    expected = treatment_plan.get('expected_outcomes', {})
                                    _ = expected  # Satisfy linter
                                    
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        current = treatment_plan_data.get('risk_rating', 0)
                                        after = treatment_plan.get('summary', {}).get('expected_risk_rating_after', '0')
                                        _ = current  # Satisfy linter
                                        st.metric("Risk Rating", f"{current} → {after}")
                                    
                                    with col2:
                                        reduction = expected.get('risk_reduction_percentage', '0%')
                                        if current > 0 and after:
                                            try:
                                                after_num = float(str(after).split('/')[0]) if '/' in str(after) else float(after)  # pyright: ignore
                                                reduction = f"{((current - after_num) / current) * 100:.0f}%" if after_num else '0%'
                                            except:
                                                pass
                                        st.metric("Risk Reduction", reduction, delta="🟢")
                                    
                                    with col3:
                                        current_res = treatment_plan_data.get('residual_risk', 0)
                                        after_res = treatment_plan.get('summary', {}).get('expected_residual_risk_after', '0')
                                        st.metric("Residual Risk", f"{current_res} → {after_res}")
                                    
                                    # Resource Summary
                                    st.markdown("---")
                                    st.markdown("### 📊 Resource Summary")
                                    
                                    summary = treatment_plan.get('summary', {})
                                    
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        st.metric("Total Cost", summary.get('total_estimated_cost', '$0'))
                                    
                                    with col2:
                                        st.metric("Duration", f"{summary.get('total_duration_days', 0)} days")
                                    
                                    with col3:
                                        st.metric("Total Actions", summary.get('total_actions', len(actions)))
                                    
                                    # Show resources from each action
                                    st.markdown("#### 📊 Resources by Action")
                                    for action in actions:
                                        resources = action.get('necessary_resources', 'N/A')
                                        if resources and resources != 'N/A':
                                            st.markdown(f"**{action.get('action_id')}:** {resources}")
                                    
                                    # Save to database button
                                    st.markdown("---")
                                    
                                    if st.button("💾 Save Treatment Plan to Risk Register", type="primary", use_container_width=True):
                                        with st.spinner("💾 Saving to database..."):
                                            try:
                                                from phase2_risk_resolver.database.save_to_register import save_assessment_to_risk_register
                                                
                                                # Enhance decision result with treatment plan
                                                enhanced_decision = {
                                                    **result,
                                                    'rtp_answers': st.session_state.get('rtp_answers', {'Q1.1': 'TREAT'}),  # 🔧 FIX: Use get() with default
                                                    'treatment_plan': treatment_plan,
                                                    'completed': True
                                                }
                                                
                                                risk_ids = save_assessment_to_risk_register(
                                                    asset_data=selected_asset,
                                                    agent_1_results=st.session_state.impact_result,
                                                    agent_2_results=st.session_state.risk_result,
                                                    agent_3_results=st.session_state.control_result,
                                                    agent_4_results=enhanced_decision
                                                )
                                                
                                                st.session_state.risk_ids = risk_ids
                                                st.session_state.output_result = {'status': 'saved', 'risk_ids': risk_ids}
                                                
                                                st.success(f"✅ Saved! Risk IDs: {', '.join(risk_ids)}")
                                                st.info("ℹ️ **View in Risk Register page!**")
                                                
                                            except Exception as e:
                                                st.error(f"❌ Error: {str(e)}")
                                    
                                    # Download treatment plan
                                    st.download_button(
                                        label="📥 Download Treatment Plan (JSON)",
                                        data=json.dumps(treatment_plan, indent=2),
                                        file_name=f"treatment_plan_{selected_asset['asset_name'].replace(' ', '_')}.json",
                                        mime="application/json",
                                        use_container_width=True
                                    )
                        
                        else:
                            st.warning("⚠️ Unexpected format")
                    
                    else:
                        st.info("ℹ️ Run Agent 4 to generate RTP questionnaire")
                

# ===================================================================
# SIDEBAR
# ===================================================================

def render_sidebar():
    """Render sidebar with navigation and controls"""
    with st.sidebar:
        st.markdown("# 🎯 Risk Resolver")
        st.markdown("*Agentic AI Risk Assessment*")
        
        st.markdown("---")
        
        # API Key Status with Auto-Rotation
        try:
            manager = get_api_key_manager()
            status = manager.get_status()
            
            st.markdown("### 🔑 API Keys (Auto-Rotate)")
            st.success(f"🔑 Key #{status['current_index']}/{status['total_keys']}")
            st.caption(f"Available: {status['available_count']} | Used: {status['failed_count']}")
            
            if st.button("🔄 Reset Keys", help="Reset after quota period", use_container_width=True):
                manager.reset_failed_keys()
                st.rerun()
            
            api_key = manager.get_current_key()
        except Exception as e:
            st.error(f"❌ API Error: {str(e)}")
            st.info("ℹ️ Add .env file with GEMINI_API_KEY_1, etc.")
            api_key = None
        
        st.markdown("---")
        
        st.markdown("### 🧭 Navigation")
        
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.current_page = "Home"
            st.rerun()
        
        if st.button("📚 Knowledge Base", use_container_width=True):
            st.session_state.current_page = "Knowledge Base"
            st.rerun()
        
        if st.button("🎯 Risk Assessment", use_container_width=True):
            st.session_state.current_page = "Risk Assessment"
            st.rerun()

        # NEW: Risk Register button
        if st.button("📋 Risk Register", use_container_width=True):
            st.session_state.current_page = "Risk Register"
            st.rerun()
        
        if st.button("📅 Follow-up", use_container_width=True):
            st.session_state.current_page = "Follow-up"
            st.rerun()
        
        st.markdown("---")
        
        st.markdown("### 📊 System Status")
        
        if st.session_state.processed:
            st.success("✅ Knowledge Base: Ready")
            st.caption(f"Documents: {len(st.session_state.documents)}")
        else:
            st.warning("⚠️ Knowledge Base: Not Loaded")
        
        if st.session_state.rag_initialized:
            st.success("✅ Agent System: Ready")
            st.caption("Agents: 6 active")
        else:
            st.info("⚠️ Agent System: Not Initialized")
        
        st.markdown("### 🤖 Agent Status")
        
        # 🔧 FIXED: Updated variable names
        if st.session_state.impact_result:  # Changed from cia_result!
            st.success("✅ Agent 1: Impact Complete")
        else:
            st.info("⚪ Agent 1: Not run")
        
        if st.session_state.risk_result:
            st.success("✅ Agent 2: Risk Complete")
        else:
            st.info("⚪ Agent 2: Not run")
        
        if st.session_state.control_result:
            st.success("✅ Agent 3: Controls Complete")
        else:
            st.info("⚪ Agent 3: Not run")
        
        if st.session_state.decision_result:
            st.success("✅ Agent 4: Decision Complete")
        else:
            st.info("⚪ Agent 4: Not run")
        
        return api_key

# ===================================================================
# MAIN APP
# ===================================================================

def main():
    if not st.session_state.kb_loaded:
        if knowledge_base_exists():
            with st.spinner("Loading knowledge base..."):
                documents, vectorizer, document_vectors, metadata = load_knowledge_base()
                
                if documents is not None:
                    st.session_state.documents = documents
                    st.session_state.vectorizer = vectorizer
                    st.session_state.document_vectors = document_vectors
                    st.session_state.processed = True
                    st.session_state.kb_loaded = True
    
    api_key = render_sidebar()
    
    if st.session_state.current_page == "Home":
        render_home_page()
    elif st.session_state.current_page == "Knowledge Base":
        render_knowledge_base_page(api_key)
    elif st.session_state.current_page == "Risk Assessment":
        render_risk_assessment_page(api_key)
    elif st.session_state.current_page == "Risk Register":
        render_risk_register_page()
    elif st.session_state.current_page == "Follow-up":
        render_followup_page(api_key)

if __name__ == "__main__":
    main()


