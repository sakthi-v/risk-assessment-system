"""
Risk Register Page - FIXED VERSION
Displays all risks from database with filters, sorting, and details view
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from typing import Dict, List, Any
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ✅ FIXED: Import from risk_register_queries instead of risk_register_db
from phase2_risk_resolver.database.risk_register_queries import (
    get_dashboard_stats,
    get_all_risks,
    get_risk_by_id,
    get_unique_risk_owners,
    get_unique_treatment_decisions
)


def render_risk_register_page():
    """Main function to render Risk Register page"""
    
    def get_mitigation_summary(risk):
        """Get full mitigation plan text for table display - NO truncation"""
        mitigation_plan = risk.get('mitigation_plan', '')
        
        if not mitigation_plan or mitigation_plan == 'Mitigation plan pending - awaiting management decision':
            return 'Pending'
        
        # Return FULL text - no truncation
        return mitigation_plan
    
    st.title("🎯 Risk Register")
    st.markdown("### Centralized Risk Management Dashboard")
    
    # Add refresh button
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # ✅ FIXED: Get data directly from database queries
    try:
        stats = get_dashboard_stats()
        all_risks = get_all_risks()
    except Exception as e:
        st.error(f"❌ Error loading risks: {str(e)}")
        import traceback
        with st.expander("🔍 Debug Info"):
            st.code(traceback.format_exc())
        
        # Set empty defaults
        stats = {
            'total_risks': 0,
            'high_priority': 0,
            'open_risks': 0,
            'closed_risks': 0,
            'in_progress': 0,
            'highest_risk': '0/5',
            'by_status': {},
            'by_priority': {},
            'by_risk_level': {}
        }
        all_risks = []
    
    # ═══════════════════════════════════════════════════════════════
    # DASHBOARD METRICS
    # ═══════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown("## 📊 Dashboard Overview")
    
    col1, sep1, col2, col3, col4, sep2, col5 = st.columns([1, 0.05, 1, 1, 1, 0.05, 1])
    
    with col1:
        st.metric(
            label="📋 Total Risk Findings",
            value=stats.get('total_risks', 0)
        )
    
    with sep1:
        st.markdown(
            '<div style="height: 80px; border-left: 1px solid rgba(128, 128, 128, 0.3); margin: 0 auto;"></div>',
            unsafe_allow_html=True
        )
    
    with col2:
        st.metric(
            label="📂 Open Risks",
            value=stats.get('open_risks', 0)
        )
    
    with col3:
        st.metric(
            label="✅ Closed Risks",
            value=stats.get('closed_risks', 0)
        )
    
    with col4:
        st.metric(
            label="⏳ In Progress",
            value=stats.get('in_progress', 0)
        )
    
    with sep2:
        st.markdown(
            '<div style="height: 80px; border-left: 1px solid rgba(128, 128, 128, 0.3); margin: 0 auto;"></div>',
            unsafe_allow_html=True
        )
    
    with col5:
        st.metric(
            label="🔴 High Priority",
            value=stats.get('high_priority', 0),
            delta="Critical" if stats.get('high_priority', 0) > 0 else "None"
        )
    
    # ═══════════════════════════════════════════════════════════════
    # RISK DISTRIBUTION CHARTS
    # ═══════════════════════════════════════════════════════════════
    
    if all_risks:
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Risk Findings by Severity")
            
            # Build rating counts
            rating_data = {}
            for risk in all_risks:
                try:
                    rating = float(risk.get('inherent_risk_rating', 0))
                    rating = int(round(rating))
                except (ValueError, TypeError):
                    rating = 0
                rating_data[rating] = rating_data.get(rating, 0) + 1
            
            if rating_data:
                # Create data with risk level names for legend
                rating_labels = {
                    5: 'Extreme',
                    4: 'High',
                    3: 'Medium',
                    2: 'Low',
                    1: 'Very Low'
                }
                
                color_map = {
                    'Extreme': '#dc3545',
                    'High': '#fd7e14',
                    'Medium': '#ffc107',
                    'Low': '#28a745',
                    'Very Low': '#28a745'
                }
                
                # Build data for chart
                x_values = []
                y_values = []
                colors = []
                
                for rating in sorted(rating_data.keys(), reverse=True):
                    x_values.append(str(rating))
                    y_values.append(rating_data[rating])
                    colors.append(rating_labels.get(rating, str(rating)))
                
                fig_rating = px.bar(
                    x=x_values,
                    y=y_values,
                    labels={'x': 'Risk Rating (Severity)', 'y': 'No. of Risk Findings'},
                    color=colors,
                    color_discrete_map=color_map
                )
                fig_rating.update_layout(showlegend=True, height=300, legend_title_text='Risk Level')
                st.plotly_chart(fig_rating, use_container_width=True)
        
        with col2:
            st.markdown("#### 📈 Risk Findings by Status")
            status_counts = stats.get('by_status', {})
            
            if status_counts:
                # Ensure correct color order: Open=Red, In Progress=Yellow, Closed=Green
                status_order = ['Open', 'In Progress', 'Closed']
                colors = ['#dc3545', '#ffc107', '#28a745']  # Red, Yellow, Green
                
                # Reorder data to match status_order
                ordered_names = []
                ordered_values = []
                ordered_colors = []
                
                for idx, status in enumerate(status_order):
                    if status in status_counts:
                        ordered_names.append(status)
                        ordered_values.append(status_counts[status])
                        ordered_colors.append(colors[idx])
                
                fig_status = px.pie(
                    values=ordered_values,
                    names=ordered_names,
                    color_discrete_sequence=ordered_colors
                )
                fig_status.update_layout(height=300)
                st.plotly_chart(fig_status, use_container_width=True)
    
    # ═══════════════════════════════════════════════════════════════
    # FILTERS
    # ═══════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown("## 🔍 Filters")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Status filter
        status_options = ['All'] + list(set([r.get('status', 'Unknown') for r in all_risks if r.get('status')]))
        selected_status = st.selectbox("Status", status_options, key="filter_status")
    
    with col2:
        # Rating filter
        rating_options = ['All', '5 - Extreme', '4 - High', '3 - Medium', '2 - Low', '1 - Very Low']
        selected_rating = st.selectbox("Risk Rating", rating_options, key="filter_rating")
    
    with col3:
        # Owner filter
        try:
            owner_options = ['All'] + get_unique_risk_owners()
        except:
            owner_options = ['All'] + list(set([r.get('risk_owner', 'Unknown') for r in all_risks if r.get('risk_owner')]))
        selected_owner = st.selectbox("Risk Owner", owner_options, key="filter_owner")
    
    with col4:
        # Decision filter
        try:
            decision_options = ['All'] + get_unique_treatment_decisions()
        except:
            decision_options = ['All', 'TREAT', 'ACCEPT', 'TRANSFER', 'TERMINATE']
        selected_decision = st.selectbox("Treatment Decision", decision_options, key="filter_decision")
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input("Date From", value=None, key="filter_date_from")
    with col2:
        date_to = st.date_input("Date To", value=None, key="filter_date_to")
    
    # Search box
    search_query = st.text_input("🔍 Search risks (title, description, asset)", key="search_query")
    
    # Apply filters button
    col1, col2 = st.columns([1, 4])
    with col1:
        apply_filters = st.button("🔍 Apply Filters", type="primary", use_container_width=True)
    with col2:
        if st.button("🔄 Reset Filters", use_container_width=True):
            st.rerun()
    
    # ═══════════════════════════════════════════════════════════════
    # FILTER RISKS
    # ═══════════════════════════════════════════════════════════════
    
    filtered_risks = all_risks.copy()
    
    # Apply status filter
    if selected_status != 'All':
        filtered_risks = [r for r in filtered_risks if r.get('status') == selected_status]
    
    # Apply rating filter
    if selected_rating != 'All':
        try:
            rating_value = int(selected_rating.split(' ')[0])
            filtered_risks = [r for r in filtered_risks if int(round(float(r.get('inherent_risk_rating', 0)))) == rating_value]
        except (ValueError, TypeError, IndexError):
            pass
    
    # Apply owner filter
    if selected_owner != 'All':
        filtered_risks = [r for r in filtered_risks if r.get('risk_owner') == selected_owner]
    
    # Apply decision filter
    if selected_decision != 'All':
        filtered_risks = [r for r in filtered_risks if r.get('treatment_decision') == selected_decision]
    
    # Apply date filters
    if date_from:
        date_from_str = date_from.strftime('%Y-%m-%d')
        filtered_risks = [r for r in filtered_risks if r.get('identified_date', '9999-12-31') >= date_from_str]
    
    if date_to:
        date_to_str = date_to.strftime('%Y-%m-%d')
        filtered_risks = [r for r in filtered_risks if r.get('identified_date', '0000-01-01') <= date_to_str]
    
    # Apply search query
    if search_query:
        query_lower = search_query.lower()
        filtered_risks = [
            r for r in filtered_risks
            if query_lower in str(r.get('threat_name', '')).lower()
            or query_lower in str(r.get('threat_description', '')).lower()
            or query_lower in str(r.get('asset_name', '')).lower()
        ]
    
    # ═══════════════════════════════════════════════════════════════
    # RISK TABLE
    # ═══════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown(f"## 📋 Risk Table ({len(filtered_risks)} risks)")
    
    if not filtered_risks:
        st.info("ℹ️ No risks found matching the filters")
    else:
        # Export buttons
        col1, col2, col3 = st.columns([1, 1, 3])
        
        with col1:
            if st.button("📥 Export Excel", use_container_width=True):
                try:
                    df = pd.DataFrame(filtered_risks)
                    st.download_button(
                        label="⬇️ Download Excel",
                        data=df.to_csv(index=False).encode('utf-8'),
                        file_name=f"risk_register_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")
        
        with col2:
            if st.button("📥 Export JSON", use_container_width=True):
                json_data = json.dumps(filtered_risks, indent=2, default=str)
                st.download_button(
                    label="⬇️ Download JSON",
                    data=json_data,
                    file_name=f"risk_register_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    use_container_width=True
                )
        
        st.markdown("---")
        
        # Create dataframe for display
        display_data = []
        
        for risk in filtered_risks:
            # Color coding for risk rating
            try:
                rating = float(risk.get('inherent_risk_rating', 0))
            except (ValueError, TypeError):
                rating = 0
            if rating >= 5:
                rating_display = f"🔴 {rating}/5"
            elif rating >= 4:
                rating_display = f"🟠 {rating}/5"
            elif rating >= 3:
                rating_display = f"🟡 {rating}/5"
            else:
                rating_display = f"🟢 {rating}/5"
            
            # Use current residual risk if follow-up done, else original
            current_residual = risk.get('current_residual_risk')
            residual_risk = current_residual if current_residual else risk.get('residual_risk_rating', 0)
            
            # Convert to float safely
            try:
                residual_risk = float(residual_risk) if residual_risk else 0.0
            except (ValueError, TypeError):
                residual_risk = 0.0
            
            # Extract delay_reason from latest follow-up answers
            delay_reason = 'N/A'
            followup_answers = risk.get('followup_answers')
            if followup_answers:
                try:
                    if isinstance(followup_answers, str):
                        followup_history = json.loads(followup_answers)
                    else:
                        followup_history = followup_answers
                    
                    if isinstance(followup_history, list) and len(followup_history) > 0:
                        # Get latest follow-up
                        latest_followup = followup_history[-1]
                        answers = latest_followup.get('answers', {})
                        delay_reason = answers.get('delay_reason', 'N/A')
                except:
                    delay_reason = 'N/A'
            
            display_data.append({
                'ID': risk.get('risk_id', 'N/A'),
                'Risk Title': risk.get('threat_name', 'Untitled'),
                'Asset': risk.get('asset_name', 'N/A'),
                'Rating': rating_display,
                'Residual Risk': f"{residual_risk:.2f}",
                'Status': risk.get('status', 'Unknown'),
                'Decision': risk.get('treatment_decision', 'Pending'),
                'Mitigation': get_mitigation_summary(risk),
                'Owner': risk.get('risk_owner', 'Unassigned'),
                'Action Owner': risk.get('action_owner', 'Not assigned'),
                'Progress (Follow-up)': f"{risk.get('completion_percentage') or 0}%",
                'Delay': delay_reason,
                'Target Date': risk.get('target_completion_date', 'Not set'),
                'Last Updated': risk.get('last_updated', 'N/A')
            })
        
        df_display = pd.DataFrame(display_data)
        
        # Display table
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.TextColumn("Risk ID", width="small"),
                "Risk Title": st.column_config.TextColumn("Risk Title", width="large"),
                "Asset": st.column_config.TextColumn("Asset", width="small"),
                "Rating": st.column_config.TextColumn("Rating", width="small"),
                "Residual Risk": st.column_config.TextColumn("Residual Risk", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Decision": st.column_config.TextColumn("Decision", width="small"),
                "Mitigation": st.column_config.TextColumn("Mitigation Plan", width="medium", help="Preventive steps to reduce risk likelihood"),
                "Owner": st.column_config.TextColumn("Application Owner", width="small"),
                "Action Owner": st.column_config.TextColumn("Action Owner", width="small"),
                "Progress (Follow-up)": st.column_config.TextColumn("Progress (Follow-up)", width="small", help="Completion percentage from follow-up questionnaire"),
                "Delay": st.column_config.TextColumn("Delay Reason", width="medium", help="Delay reason from latest follow-up questionnaire"),
                "Target Date": st.column_config.TextColumn("Target Date", width="small"),
                "Last Updated": st.column_config.TextColumn("Updated Date", width="small")
            }
        )
        
        # Color legend for Rating column
        st.caption("**Rating Color Legend:** 🔴 Extreme (5) | 🟠 High (4) | 🟡 Medium (3) | 🟢 Low (1-2)")
        
        st.markdown("---")
        
        # ═══════════════════════════════════════════════════════════════
        # RISK DETAILS (Expandable)
        # ═══════════════════════════════════════════════════════════════
        st.markdown("## 📝 Risk Details")
        st.caption("Click on a risk to view full details")
        
        # Select risk to view
        risk_ids = [r.get('risk_id', 'N/A') for r in filtered_risks]
        selected_risk_id = st.selectbox(
            "Select Risk ID to view details:",
            options=risk_ids,
            key="selected_risk_detail"
        )
        
        if selected_risk_id:
            # Get full risk details
            selected_risk = next((r for r in filtered_risks if r.get('risk_id') == selected_risk_id), None)
            
            if selected_risk:
                # Display risk details
                with st.expander(f"📋 **{selected_risk_id}: {selected_risk.get('threat_name', 'Untitled')}**", expanded=True):
                    
                    # Basic Info
                    st.markdown("### 📊 Basic Information")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown(f"**Asset:** {selected_risk.get('asset_name', 'N/A')}")
                        st.markdown(f"**Asset Type:** {selected_risk.get('asset_type', 'N/A')}")
                    
                    with col2:
                        st.markdown(f"**Status:** {selected_risk.get('status', 'Unknown')}")
                        st.markdown(f"**Date Identified:** {selected_risk.get('identified_date', 'N/A')}")
                    
                    with col3:
                        st.markdown(f"**Risk Owner:** {selected_risk.get('risk_owner', 'Unassigned')}")
                        st.markdown(f"**Target Date:** {selected_risk.get('target_completion_date', 'Not set')}")
                    
                    st.markdown("---")
                    
                    # Risk Description
                    st.markdown("### 📝 Risk Description")
                    st.write(selected_risk.get('threat_description', 'No description available'))
                    
                    st.markdown("---")
                    
                    # Risk Assessment - Display Agent 2 outputs
                    st.markdown("### 📈 Risk Assessment")
                    col1, col2, col3 = st.columns(3)
                    
                    # Extract Agent 2 data for proper display
                    agent_2_raw = selected_risk.get('agent_2_raw', '{}')
                    if isinstance(agent_2_raw, str):
                        try:
                            agent_2_data = json.loads(agent_2_raw)
                        except:
                            agent_2_data = {}
                    else:
                        agent_2_data = agent_2_raw
                    
                    # Get first threat's risk quantification
                    risk_impact_rating = 0
                    risk_probability_rating = 0
                    risk_value = 0
                    
                    if 'threat_risk_quantification' in agent_2_data:
                        threats = agent_2_data['threat_risk_quantification']
                        if threats and len(threats) > 0:
                            first_threat = threats[0]
                            
                            # Risk Impact
                            risk_impact = first_threat.get('risk_impact', {})
                            if isinstance(risk_impact, dict):
                                risk_impact_rating = risk_impact.get('rating', 0)
                            
                            # Risk Probability
                            risk_prob = first_threat.get('risk_probability', {})
                            if isinstance(risk_prob, dict):
                                risk_probability_rating = risk_prob.get('rating', 0)
                            
                            # Risk Value
                            risk_val = first_threat.get('risk_value', {})
                            if isinstance(risk_val, dict):
                                risk_value = risk_val.get('value', 0)
                    
                    with col1:
                        rating = selected_risk.get('inherent_risk_rating', 0)
                        color = "🔴" if rating >= 4 else "🟠" if rating == 3 else "🟢"
                        st.metric("Risk Rating", f"{rating}/5", delta=f"{color} {selected_risk.get('inherent_risk_level', '')}")
                    
                    with col2:
                        st.metric("Risk Impact", f"{risk_impact_rating}/5")
                    
                    with col3:
                        st.metric("Risk Probability", f"{risk_probability_rating}/5")
                    
                    st.markdown("---")
                    
                    # CIA Impact - Extract text ratings from Agent 1
                    st.markdown("### 🔐 CIA Impact")
                    
                    # Try to get text ratings from agent_1_raw
                    agent_1_raw = selected_risk.get('agent_1_raw', '{}')
                    if isinstance(agent_1_raw, str):
                        try:
                            agent_1_data = json.loads(agent_1_raw)
                        except:
                            agent_1_data = {}
                    else:
                        agent_1_data = agent_1_raw
                    
                    # Extract CIA text ratings
                    c_text = "N/A"
                    i_text = "N/A"
                    a_text = "N/A"
                    
                    if 'threat_analysis' in agent_1_data:
                        threat_analysis = agent_1_data['threat_analysis']
                        if threat_analysis and len(threat_analysis) > 0:
                            impact_assessment = threat_analysis[0].get('impact_assessment', {})
                            
                            conf_data = impact_assessment.get('confidentiality', {})
                            if isinstance(conf_data, dict):
                                c_text = conf_data.get('rating', 'N/A')
                            
                            int_data = impact_assessment.get('integrity', {})
                            if isinstance(int_data, dict):
                                i_text = int_data.get('rating', 'N/A')
                            
                            avail_data = impact_assessment.get('availability', {})
                            if isinstance(avail_data, dict):
                                a_text = avail_data.get('rating', 'N/A')
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Confidentiality", c_text)
                    
                    with col2:
                        st.metric("Integrity", i_text)
                    
                    with col3:
                        st.metric("Availability", a_text)
                    
                    st.markdown("---")
                    
                    # Controls & Residual Risk
                    st.markdown("### 🔒 Controls & Residual Risk")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Parse existing controls
                        existing_controls = selected_risk.get('existing_controls', '[]')
                        if isinstance(existing_controls, str):
                            try:
                                existing_controls = json.loads(existing_controls)
                            except:
                                existing_controls = []
                        st.metric("Controls in Place", len(existing_controls) if isinstance(existing_controls, list) else 0)
                    
                    with col2:
                        # Show ORIGINAL control rating from Agent 3 (never changes)
                        original_ctrl = selected_risk.get('control_rating', 0)
                        st.metric("Control Rating", f"{original_ctrl:.2f}/5")
                    
                    with col3:
                        # Show ORIGINAL residual risk from Agent 2 (never changes)
                        original_residual = selected_risk.get('residual_risk_rating', 0)
                        # 🔧 FIX: Calculate risk level from residual_risk_rating value
                        if original_residual >= 4.5:
                            residual_level = 'Extreme'
                            color = "🔴"
                        elif original_residual >= 3.5:
                            residual_level = 'High'
                            color = "🔴"
                        elif original_residual >= 2.5:
                            residual_level = 'Medium'
                            color = "🟡"
                        elif original_residual >= 1.5:
                            residual_level = 'Low'
                            color = "🟢"
                        else:
                            residual_level = 'Very Low'
                            color = "🟢"
                        st.metric("Residual Risk", f"{original_residual:.2f}", delta=f"{color} {residual_level}")
                    
                    # Control Gaps
                    control_gaps = selected_risk.get('control_gaps', '[]')
                    if isinstance(control_gaps, str):
                        try:
                            control_gaps = json.loads(control_gaps)
                        except:
                            control_gaps = []
                    
                    if control_gaps and isinstance(control_gaps, list):
                        st.markdown("**Control Gaps:**")
                        for gap in control_gaps:
                            if isinstance(gap, dict):
                                st.markdown(f"- {gap.get('gap_description', gap)}")
                            else:
                                st.markdown(f"- {gap}")
                    
                    st.markdown("---")
                    
                    # Mitigation Plan
                    st.markdown("### 📋 Mitigation Plan")
                    mitigation_plan = selected_risk.get('mitigation_plan', 'No mitigation plan available')
                    st.info(mitigation_plan if mitigation_plan else 'No mitigation plan available')
                    
                    st.markdown("---")
                    
                    # Treatment Decision
                    decision = selected_risk.get('treatment_decision', 'Pending')
                    
                    # ═══════════════════════════════════════════════════════════════
                    # ACCEPT WORKFLOW DISPLAY
                    # ═══════════════════════════════════════════════════════════════
                    
                    if decision == 'ACCEPT':
                        st.markdown("### ✋ Risk Acceptance Details")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric("Treatment Decision", decision, delta="🟢")
                        
                        with col2:
                            st.metric("Priority", selected_risk.get('priority', 'Not set'))
                        
                        st.markdown("---")
                        
                        # Extract acceptance form data
                        acceptance_form = selected_risk.get('acceptance_form', '{}')
                        if isinstance(acceptance_form, str):
                            try:
                                acceptance_form = json.loads(acceptance_form)
                            except:
                                acceptance_form = {}
                        
                        # Justification
                        st.markdown("#### 📝 Justification for Risk Acceptance")
                        justification = selected_risk.get('acceptance_reason', '')
                        if not justification and isinstance(acceptance_form, dict):
                            justification_section = acceptance_form.get('justification', {})
                            justification = justification_section.get('justification_text', 'No justification provided')
                        st.info(justification if justification else 'No justification provided')
                        
                        # Compensating Controls
                        st.markdown("#### 🛡️ Compensating Controls")
                        
                        # Try recommended_controls first (where compensating controls are stored)
                        compensating_controls = selected_risk.get('recommended_controls', '[]')
                        if isinstance(compensating_controls, str):
                            try:
                                compensating_controls = json.loads(compensating_controls)
                            except:
                                compensating_controls = []
                        
                        if compensating_controls and isinstance(compensating_controls, list) and len(compensating_controls) > 0:
                            for idx, control in enumerate(compensating_controls, 1):
                                if isinstance(control, dict):
                                    # Get control name
                                    control_name = control.get('control_name') or control.get('gap_description') or control.get('label') or f'Control {idx}'
                                    
                                    with st.expander(f"🛡️ {control_name}", expanded=False):
                                        # Show fields that Agent 3 outputs
                                        rationale = control.get('rationale') or control.get('description') or control.get('evidence')
                                        if rationale:
                                            st.markdown(f"**Rationale:** {rationale}")
                                        
                                        col1, col2, col3 = st.columns(3)
                                        
                                        with col1:
                                            priority = control.get('priority') or control.get('severity')
                                            if priority:
                                                st.markdown(f"**Priority:** {priority}")
                                        
                                        with col2:
                                            ctrl_type = control.get('control_type')
                                            if ctrl_type:
                                                st.markdown(f"**Type:** {ctrl_type}")
                                        
                                        with col3:
                                            effectiveness = control.get('expected_effectiveness') or control.get('current_rating')
                                            if effectiveness:
                                                st.markdown(f"**Effectiveness:** {effectiveness}/5")
                                elif isinstance(control, str):
                                    st.markdown(f"- {control}")
                        else:
                            st.warning("No compensating controls specified")
                        
                        st.markdown("---")
                        
                        # Validity
                        st.markdown("#### 📅 Validity Period")
                        valid_until = selected_risk.get('valid_until_date', 'Not set')
                        st.metric("Valid Until", valid_until)
                        st.caption("Risk acceptance expires on this date and requires re-evaluation")
                        
                        # Approval Details
                        st.markdown("---")
                        st.markdown("#### ✅ Approval Details")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Risk Owner:**")
                            st.info(selected_risk.get('risk_owner', 'Unassigned'))
                        
                        with col2:
                            # Extract approver from approver_ciso JSON
                            approver_name = 'Not specified'
                            approver_ciso = selected_risk.get('approver_ciso', '{}')
                            if isinstance(approver_ciso, str):
                                try:
                                    approver_data = json.loads(approver_ciso)
                                    approver_name = approver_data.get('name', 'Not specified')
                                except:
                                    pass
                            elif isinstance(approver_ciso, dict):
                                approver_name = approver_ciso.get('name', 'Not specified')
                            
                            st.markdown("**Approved By:**")
                            st.info(approver_name)
                    
                    # ═══════════════════════════════════════════════════════════════
                    # TREAT WORKFLOW DISPLAY
                    # ═══════════════════════════════════════════════════════════════
                    
                    elif decision == 'TREAT':
                        st.markdown("### 💊 Treatment Plan")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric("Treatment Decision", decision, delta="🔴")
                        
                        with col2:
                            st.metric("Priority", selected_risk.get('priority', 'Not set'))
                        
                        st.markdown("---")
                        
                        # Treatment Plan
                        treatment_plan = selected_risk.get('treatment_plan', '{}')
                        if isinstance(treatment_plan, str):
                            try:
                                treatment_plan = json.loads(treatment_plan)
                            except:
                                treatment_plan = {}
                        
                        if treatment_plan and isinstance(treatment_plan, dict):
                            # Expected Outcomes
                            expected = treatment_plan.get('expected_outcomes', {})
                            if expected:
                                st.markdown("#### 📈 Expected Outcomes")
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    current = expected.get('current_risk_rating', 0)
                                    after = expected.get('expected_risk_rating_after_treatment', 0)
                                    st.metric("Risk Rating", f"{current} → {after}")
                                
                                with col2:
                                    reduction = expected.get('risk_reduction_percentage', '0%')
                                    st.metric("Risk Reduction", reduction, delta="✅")
                                
                                with col3:
                                    current_res = expected.get('current_residual_risk', 0)
                                    after_res = expected.get('expected_residual_risk_after_treatment', 0)
                                    st.metric("Residual Risk", f"{current_res} → {after_res}")
                                
                                st.markdown("---")
                            
                            # Treatment Actions
                            actions = treatment_plan.get('treatment_actions', [])
                            if actions:
                                st.markdown("#### 📝 Treatment Actions")
                                for idx, action in enumerate(actions, 1):
                                    # ✅ FIX: Use correct field names
                                    action_title = action.get('control_gap', action.get('control_name', f'Action {idx}'))
                                    with st.expander(f"**Action {idx}:** {action_title}", expanded=False):
                                        description = action.get('description_of_activities', action.get('description', 'N/A'))
                                        st.markdown(f"**Description:** {description}")
                                        
                                        col1, col2, col3 = st.columns(3)
                                        
                                        with col1:
                                            duration = action.get('estimated_duration_days', action.get('timeline_days', 0))
                                            st.metric("Timeline", f"{duration} days")
                                            target = action.get('proposed_completion_date', action.get('target_completion', 'TBD'))
                                            st.caption(f"Target: {target}")
                                        
                                        with col2:
                                            cost = action.get('estimated_cost', action.get('cost_estimate', '$0'))
                                            st.metric("Cost", cost)
                                        
                                        with col3:
                                            st.caption("**Owner:**")
                                            owner = action.get('implementation_responsibility', action.get('owner', 'Unassigned'))
                                            st.info(owner)
                                        
                                        success = action.get('method_for_evaluation', action.get('success_criteria', 'N/A'))
                                        st.markdown(f"**Success Criteria:** {success}")
                                        improvement = action.get('expected_risk_reduction', action.get('expected_improvement', 'N/A'))
                                        st.markdown(f"**Expected Improvement:** {improvement}")
                            else:
                                st.warning("No treatment actions defined")
                            
                            # Resource Summary
                            resource_summary = treatment_plan.get('resource_summary', {})
                            if resource_summary:
                                st.markdown("---")
                                st.markdown("#### 💰 Resource Summary")
                                
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    st.metric("Total Cost", resource_summary.get('total_cost', '$0'))
                                
                                with col2:
                                    st.metric("Duration", f"{resource_summary.get('total_duration_days', 0)} days")
                                
                                with col3:
                                    st.metric("People Required", resource_summary.get('people_required', 0))
                        else:
                            st.warning("No treatment plan details available")
                    
                    # ═══════════════════════════════════════════════════════════════
                    # TRANSFER WORKFLOW DISPLAY
                    # ═══════════════════════════════════════════════════════════════
                    
                    elif decision == 'TRANSFER':
                        st.markdown("### 🔄 Risk Transfer Details")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric("Treatment Decision", decision, delta="🔵")
                        
                        with col2:
                            st.metric("Priority", selected_risk.get('priority', 'Not set'))
                        
                        st.markdown("---")
                        
                        # Extract transfer form data
                        transfer_form = selected_risk.get('transfer_form', '{}')
                        if isinstance(transfer_form, str):
                            try:
                                transfer_form = json.loads(transfer_form)
                            except:
                                transfer_form = {}
                        
                        if transfer_form and isinstance(transfer_form, dict):
                            # Extract from sections structure
                            sections = transfer_form.get('sections', [])
                            transfer_data = {}
                            
                            if sections:
                                for section in sections:
                                    fields = section.get('fields', [])
                                    for field in fields:
                                        field_name = field.get('field_name', '').lower()
                                        field_value = field.get('value')
                                        
                                        if 'transfer method' in field_name:
                                            transfer_data['transfer_method'] = field_value
                                        elif 'third party name' in field_name:
                                            transfer_data['third_party_name'] = field_value
                                        elif 'scope of transfer' in field_name:
                                            transfer_data['scope_of_transfer'] = field_value
                                        elif 'contract reference' in field_name:
                                            transfer_data['contract_reference'] = field_value
                                        elif 'transfer start date' in field_name:
                                            transfer_data['transfer_start_date'] = field_value
                                        elif 'transfer end date' in field_name:
                                            transfer_data['transfer_end_date'] = field_value
                                        elif 'residual risk rating' in field_name:
                                            transfer_data['residual_risk_rating'] = field_value
                                        elif 'review frequency' in field_name:
                                            transfer_data['review_frequency'] = field_value
                            
                            # Fallback to direct keys if sections not found
                            if not transfer_data:
                                transfer_data = transfer_form
                            
                            # Transfer Method & Third Party
                            st.markdown("#### 🏢 Transfer Arrangement")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                transfer_method = transfer_data.get('transfer_method', 'Not specified')
                                st.info(f"**Transfer Method:** {transfer_method}")
                            
                            with col2:
                                third_party = transfer_data.get('third_party_name', 'Not specified')
                                st.info(f"**Third Party:** {third_party}")
                            
                            # Scope & Contract
                            st.markdown("---")
                            st.markdown("#### 📄 Transfer Details")
                            
                            scope = transfer_data.get('scope_of_transfer', 'Not specified')
                            st.markdown(f"**Scope of Transfer:** {scope}")
                            
                            contract_ref = transfer_data.get('contract_reference', 'Not specified')
                            st.markdown(f"**Contract Reference:** {contract_ref}")
                            
                            # Dates
                            col1, col2 = st.columns(2)
                            with col1:
                                start_date = transfer_data.get('transfer_start_date', 'Not specified')
                                st.metric("Transfer Start Date", start_date)
                            
                            with col2:
                                end_date = transfer_data.get('transfer_end_date', 'Not specified')
                                st.metric("Transfer End Date", end_date)
                            
                            # Residual Risk & Review
                            st.markdown("---")
                            st.markdown("#### 📊 Risk Monitoring")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                residual = transfer_data.get('residual_risk_rating', selected_risk.get('residual_risk_rating', 0))
                                st.metric("Residual Risk Rating", f"{residual}")
                            
                            with col2:
                                review_freq = transfer_data.get('review_frequency', 'Not specified')
                                st.metric("Review Frequency", review_freq)
                        else:
                            st.warning("No transfer details available")
                    
                    # ═══════════════════════════════════════════════════════════════
                    # TERMINATE WORKFLOW DISPLAY
                    # ═══════════════════════════════════════════════════════════════
                    
                    elif decision == 'TERMINATE':
                        st.markdown("### ⛔ Risk Termination Details")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric("Treatment Decision", decision, delta="🔴")
                        
                        with col2:
                            st.metric("Priority", selected_risk.get('priority', 'Not set'))
                        
                        st.markdown("---")
                        
                        # Extract terminate form data
                        terminate_form = selected_risk.get('terminate_form', '{}')
                        if isinstance(terminate_form, str):
                            try:
                                terminate_form = json.loads(terminate_form)
                            except:
                                terminate_form = {}
                        
                        if terminate_form and isinstance(terminate_form, dict):
                            # Extract from sections structure
                            sections = terminate_form.get('sections', [])
                            terminate_data = {}
                            
                            if sections:
                                for section in sections:
                                    fields = section.get('fields', [])
                                    for field in fields:
                                        field_name = field.get('field_name', '').lower()
                                        field_value = field.get('value')
                                        
                                        if 'termination justification' in field_name:
                                            terminate_data['termination_justification'] = field_value
                                        elif 'business impact' in field_name:
                                            terminate_data['business_impact'] = field_value
                                        elif 'approval authority' in field_name:
                                            terminate_data['approval_authority'] = field_value
                                        elif 'termination actions' in field_name:
                                            terminate_data['termination_actions'] = field_value
                                        elif 'completion date' in field_name:
                                            terminate_data['completion_date'] = field_value
                                        elif 'residual risk' in field_name:
                                            terminate_data['residual_risk'] = field_value
                                        elif 'closure status' in field_name:
                                            terminate_data['closure_status'] = field_value
                            
                            # Fallback to direct keys
                            if not terminate_data:
                                terminate_data = terminate_form
                            
                            # Termination Justification
                            st.markdown("#### 📝 Termination Justification")
                            
                            justification = terminate_data.get('termination_justification', 'Not specified')
                            st.info(justification)
                            
                            # Business Impact
                            st.markdown("---")
                            st.markdown("#### 💼 Business Impact")
                            
                            business_impact = terminate_data.get('business_impact', 'Not specified')
                            st.markdown(business_impact)
                            
                            # Approval & Actions
                            st.markdown("---")
                            st.markdown("#### ✅ Approval & Actions")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                approval_authority = terminate_data.get('approval_authority', 'Not specified')
                                st.info(f"**Approval Authority:** {approval_authority}")
                            
                            with col2:
                                completion_date = terminate_data.get('completion_date', 'Not specified')
                                st.metric("Completion Date", completion_date)
                            
                            # Termination Actions
                            termination_actions = terminate_data.get('termination_actions', 'Not specified')
                            st.markdown(f"**Termination Actions:** {termination_actions}")
                            
                            # Residual Risk & Closure
                            st.markdown("---")
                            st.markdown("#### 📊 Risk Closure")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                residual = terminate_data.get('residual_risk', 'Not specified')
                                st.metric("Residual Risk", residual)
                            
                            with col2:
                                closure_status = terminate_data.get('closure_status', 'Not specified')
                                st.metric("Closure Status", closure_status)
                        else:
                            st.warning("No termination details available")
                    
                    # ═══════════════════════════════════════════════════════════════
                    # FOLLOW-UP HISTORY DISPLAY
                    # ═══════════════════════════════════════════════════════════════
                    
                    followup_answers = selected_risk.get('followup_answers')
                    if followup_answers:
                        st.markdown("### 🔄 Follow-up History")
                        
                        # Parse follow-up history
                        if isinstance(followup_answers, str):
                            try:
                                followup_history = json.loads(followup_answers)
                            except:
                                followup_history = []
                        else:
                            followup_history = followup_answers if isinstance(followup_answers, list) else []
                        
                        if followup_history:
                            # Show summary metrics
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric("Total Follow-ups", len(followup_history))
                            
                            with col2:
                                last_followup = followup_history[-1] if followup_history else {}
                                last_date = last_followup.get('followup_date', 'N/A')
                                st.metric("Last Follow-up", last_date.split(' ')[0] if last_date != 'N/A' else 'N/A')
                            
                            with col3:
                                completion = selected_risk.get('completion_percentage', 0)
                                st.metric("Progress", f"{completion}%")
                            
                            with col4:
                                next_date = selected_risk.get('next_followup_date', 'N/A')
                                st.metric("Next Follow-up", next_date if next_date else 'Completed')
                            
                            st.markdown("---")
                            
                            # Display each follow-up
                            for idx, followup in enumerate(followup_history, 1):
                                followup_date = followup.get('followup_date', 'Unknown date')
                                decision_type = followup.get('decision_type', 'Unknown')
                                
                                with st.expander(f"📋 Follow-up #{idx} - {followup_date} ({decision_type})", expanded=(idx == len(followup_history))):
                                    # Summary - Get from database fields directly (LATEST values)
                                    col1, col2 = st.columns(2)
                                    
                                    with col1:
                                        # Get status from database
                                        impl_status = selected_risk.get('status', 'Open')
                                        st.info(f"**Status:** {impl_status}")
                                    
                                    with col2:
                                        # Get completion from database (latest value)
                                        # For latest follow-up, show current completion_percentage
                                        if idx == len(followup_history):
                                            completion_pct = selected_risk.get('completion_percentage', 0)
                                        else:
                                            # For older follow-ups, try to extract from answers
                                            answers = followup.get('answers', {})
                                            completion_pct = answers.get('overall_completion', 0)
                                            if not completion_pct:
                                                for key, val in answers.items():
                                                    if 'completion' in key.lower() and 'percentage' in key.lower():
                                                        try:
                                                            completion_pct = int(val)
                                                            break
                                                        except:
                                                            pass
                                        st.info(f"**Completion:** {completion_pct}%")
                                    
                                    # ✅ NEW: Show Agent 3 & Agent 2 results if this is the latest follow-up
                                    if idx == len(followup_history):
                                        current_ctrl = selected_risk.get('current_control_rating')
                                        current_res = selected_risk.get('current_residual_risk')
                                        risk_reduction = selected_risk.get('risk_reduction_percentage')
                                        
                                        if current_ctrl is not None or current_res is not None or risk_reduction is not None:
                                            st.markdown("---")
                                            st.markdown("🤖 **AI Re-assessment Results:**")
                                            
                                            col1, col2, col3 = st.columns(3)
                                            
                                            with col1:
                                                if current_ctrl is not None:
                                                    original_ctrl = selected_risk.get('control_rating', 0)
                                                    st.metric("Control Rating", f"{current_ctrl:.2f}/5",
                                                             delta=f"+{current_ctrl - original_ctrl:.2f}")
                                            
                                            with col2:
                                                if current_res is not None:
                                                    original_res = selected_risk.get('residual_risk_rating', 0)
                                                    st.metric("Residual Risk", f"{current_res:.2f}/5",
                                                             delta=f"-{original_res - current_res:.2f}",
                                                             delta_color="inverse")
                                            
                                            with col3:
                                                if risk_reduction is not None:
                                                    st.metric("Risk Reduction", f"{risk_reduction:.0f}%",
                                                             delta="✅ Improved" if risk_reduction > 0 else "⚠️ Increased")
                                    
                                    st.markdown("---")
                                    st.markdown("**📝 Questionnaire Answers:**")
                                    
                                    # Display all answers
                                    answers = followup.get('answers', {})
                                    if answers:
                                        for question_id, answer in answers.items():
                                            if answer and str(answer).strip():
                                                st.markdown(f"**{question_id}:** {answer}")
                                    else:
                                        st.caption("No answers recorded")
                        else:
                            st.info("No follow-up history available")
                    
                    # ═══════════════════════════════════════════════════════════════
                    # PENDING DECISION
                    # ═══════════════════════════════════════════════════════════════
                    
                    elif decision == 'Pending':
                        st.markdown(f"### 📋 Treatment Decision: {decision}")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric("Treatment Decision", decision, delta="🟡")
                        
                        with col2:
                            st.metric("Priority", selected_risk.get('priority', 'Not set'))
                        
                        st.info("⏳ Treatment decision not yet made. Complete Agent 4 workflow to set decision.")
                    
                    st.markdown("---")
                    
                    # Action Buttons
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        if st.button("✏️ Edit Risk", key=f"edit_{selected_risk_id}", use_container_width=True):
                            st.info("🚧 Edit functionality coming soon!")
                    
                    with col2:
                        if st.button("🔄 Update Status", key=f"update_{selected_risk_id}", use_container_width=True):
                            st.info("🚧 Status update coming soon!")
                    
                    with col3:
                        if st.button("💬 Add Comment", key=f"comment_{selected_risk_id}", use_container_width=True):
                            st.info("🚧 Comments coming soon!")
                    
                    with col4:
                        if st.button("📥 Export PDF", key=f"pdf_{selected_risk_id}", use_container_width=True):
                            st.info("🚧 PDF export coming soon!")
    
    # ═══════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.caption("🎯 Risk Register - Phase 5 Complete")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    # For testing
    st.set_page_config(
        page_title="Risk Register",
        page_icon="🎯",
        layout="wide"
    )
    render_risk_register_page()