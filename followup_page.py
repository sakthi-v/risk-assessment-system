"""
Follow-up Page - IMPROVED VERSION
Properly analyzes follow-up answers and updates Risk Register
"""

import streamlit as st
import json
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from phase2_risk_resolver.database.followup_checker import get_risks_needing_followup
from phase2_risk_resolver.agents.agent_followup_questionnaire import generate_followup_questionnaire
from phase2_risk_resolver.database.save_followup import save_followup_to_risk_register
from phase2_risk_resolver.database.risk_register_queries import get_overdue_followups
from phase2_risk_resolver.agents.monitoring_logic import get_all_risk_alerts, get_monitoring_stats
import sqlite3


def analyze_followup_answers(answers: Dict[str, Any], questionnaire: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze follow-up answers and extract structured data for database update
    
    Returns:
        Dictionary with fields to update in Risk Register
    """
    
    update_data = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'followup_history': []
    }
    
    # Track completion information
    action_statuses = []
    completion_percentages = []
    blockers = []
    control_effectiveness_ratings = []
    
    # Analyze each answer
    for q_id, answer in answers.items():
        if not answer:
            continue
        
        answer_str = str(answer).upper()
        
        # ==============================================================
        # SECTION 1: IMPLEMENTATION STATUS
        # ==============================================================
        
        # Detect action status questions
        if 'STATUS' in q_id.upper() or 'Q1.' in q_id:
            action_statuses.append(answer)
            
            # Determine overall status
            if 'COMPLETED' in answer_str:
                update_data['status'] = 'Completed'
            elif 'BLOCKED' in answer_str:
                update_data['status'] = 'Blocked'
            elif 'IN_PROGRESS' in answer_str or 'IN PROGRESS' in answer_str:
                if update_data.get('status') != 'Blocked':  # Blocked takes priority
                    update_data['status'] = 'In Progress'
            elif 'NOT_STARTED' in answer_str or 'NOT STARTED' in answer_str:
                if 'status' not in update_data:
                    update_data['status'] = 'Open'
        
        # Detect completion percentage questions
        if 'PERCENTAGE' in q_id.upper() or 'COMPLETE' in q_id.upper():
            try:
                pct = float(answer)
                completion_percentages.append(pct)
            except:
                pass
        
        # Detect blocker questions
        if 'BLOCKER' in q_id.upper() or 'CHALLENGE' in q_id.upper():
            if answer and len(str(answer).strip()) > 0:
                blockers.append(str(answer))
        
        # ==============================================================
        # SECTION 2: CONTROL EFFECTIVENESS
        # ==============================================================
        
        # Detect control effectiveness ratings
        if 'EFFECTIVE' in q_id.upper() and ('RATING' in q_id.upper() or 'Q2.' in q_id):
            try:
                rating = float(answer)
                control_effectiveness_ratings.append(rating)
            except:
                pass
        
        # ==============================================================
        # SECTION 3: RISK REASSESSMENT
        # ==============================================================
        
        # Detect if risk level changed
        if 'RISK' in q_id.upper() and 'DECREASED' in answer_str:
            update_data['risk_level_changed'] = 'DECREASED'
        elif 'RISK' in q_id.upper() and 'INCREASED' in answer_str:
            update_data['risk_level_changed'] = 'INCREASED'
        elif 'RISK' in q_id.upper() and 'SAME' in answer_str:
            update_data['risk_level_changed'] = 'SAME'
        
        # Detect security incidents
        if 'INCIDENT' in q_id.upper():
            if 'YES' in answer_str:
                update_data['security_incidents'] = 'YES'
            elif 'NO' in answer_str:
                update_data['security_incidents'] = 'NO'
        
        # ==============================================================
        # SECTION 4: RESOURCES & TIMELINE
        # ==============================================================
        
        # Detect timeline status
        if 'ON TRACK' in answer_str or 'ON_TRACK' in answer_str:
            update_data['timeline_status'] = 'On Track'
        elif 'DELAYED' in answer_str:
            update_data['timeline_status'] = 'Delayed'
        elif 'AHEAD' in answer_str:
            update_data['timeline_status'] = 'Ahead of Schedule'
        
        # Detect revised completion date
        if 'REVISED' in q_id.upper() and isinstance(answer, (str, datetime)):
            update_data['revised_completion_date'] = str(answer)
        
        # Detect resource adequacy
        if 'RESOURCE' in q_id.upper() or 'ADEQUATE' in q_id.upper():
            if 'ADEQUATE' in answer_str:
                update_data['resources_adequate'] = 'YES'
            elif 'INSUFFICIENT' in answer_str:
                update_data['resources_adequate'] = 'NO'
        
        # ==============================================================
        # SECTION 5: LESSONS LEARNED
        # ==============================================================
        
        # Capture lessons learned
        if 'WORKED WELL' in q_id.upper() or 'SUCCESS' in q_id.upper():
            if answer and len(str(answer).strip()) > 0:
                update_data['lessons_learned_success'] = str(answer)
        
        if 'CHALLENGE' in q_id.upper() or 'DIFFICULTY' in q_id.upper():
            if answer and len(str(answer).strip()) > 0:
                update_data['lessons_learned_challenges'] = str(answer)
        
        if 'DIFFERENTLY' in q_id.upper() or 'IMPROVE' in q_id.upper():
            if answer and len(str(answer).strip()) > 0:
                update_data['lessons_learned_improvements'] = str(answer)
        
        # ==============================================================
        # SECTION 6: NEXT STEPS
        # ==============================================================
        
        # Capture next steps
        if 'NEXT STEP' in q_id.upper() or 'NEXT ACTION' in q_id.upper():
            if answer and len(str(answer).strip()) > 0:
                update_data['next_steps'] = str(answer)
        
        # Capture support needed
        if 'SUPPORT' in q_id.upper() or 'RESOURCE' in q_id.upper():
            if answer and len(str(answer).strip()) > 0:
                update_data['support_needed'] = str(answer)
        
        # Capture next follow-up date
        if 'NEXT FOLLOW' in q_id.upper() or 'SCHEDULE' in q_id.upper():
            if isinstance(answer, (str, datetime)):
                update_data['next_followup_date'] = str(answer)
    
    # ==================================================================
    # CALCULATE AGGREGATE METRICS
    # ==================================================================
    
    # Calculate average completion percentage
    if completion_percentages:
        avg_completion = sum(completion_percentages) / len(completion_percentages)
        update_data['completion_percentage'] = round(avg_completion, 2)
    
    # Combine blockers
    if blockers:
        update_data['current_blockers'] = ' | '.join(blockers)
    
    # Calculate average control effectiveness
    if control_effectiveness_ratings:
        avg_effectiveness = sum(control_effectiveness_ratings) / len(control_effectiveness_ratings)
        update_data['avg_control_effectiveness'] = round(avg_effectiveness, 2)
        
        # If controls are more effective, reduce residual risk
        # This is a simple heuristic - you can make it more sophisticated
        if avg_effectiveness >= 4:
            update_data['notes'] = 'Controls highly effective - Consider reducing residual risk'
        elif avg_effectiveness >= 3:
            update_data['notes'] = 'Controls moderately effective - Monitor closely'
        else:
            update_data['notes'] = 'Controls need improvement - Risk remains high'
    
    # Default status if not set
    if 'status' not in update_data:
        if completion_percentages and avg_completion >= 100:
            update_data['status'] = 'Completed'
        elif completion_percentages and avg_completion > 0:
            update_data['status'] = 'In Progress'
        else:
            update_data['status'] = 'Open'
    
    # Store complete follow-up record
    followup_record = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'answers': answers,
        'summary': {
            'status': update_data.get('status'),
            'completion_pct': update_data.get('completion_percentage'),
            'blockers': len(blockers),
            'control_effectiveness': update_data.get('avg_control_effectiveness')
        }
    }
    update_data['followup_history'].append(followup_record)
    
    return update_data


def render_followup_page(api_key: str):
    """Main function to render Follow-up page"""
    
    st.title("🔄 Risk Decision Follow-up")
    st.markdown("### Monitor and reassess risks based on management decisions")
    
    if not api_key:
        st.error("❌ API Key required! Please check sidebar.")
        return
    
    # ═══════════════════════════════════════════════════════════════
    # PENDING FOLLOW-UP QUESTIONNAIRES (EMAIL WORKFLOW)
    # ═══════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown("## 📧 Pending Follow-up Questionnaires")
    
    # Add refresh button
    col_caption, col_refresh = st.columns([4, 1])
    with col_caption:
        st.caption("View follow-up questionnaires sent via email and load completed responses")
    with col_refresh:
        if st.button("🔄 Refresh", key="refresh_pending_followup", help="Check for new completed questionnaires"):
            st.rerun()
    
    try:
        conn = sqlite3.connect('database/risk_register.db')
        cursor = conn.cursor()
        
        # Check if risk_id column exists, add if missing
        cursor.execute("PRAGMA table_info(pending_questionnaires)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'risk_id' not in columns:
            cursor.execute("ALTER TABLE pending_questionnaires ADD COLUMN risk_id TEXT")
            conn.commit()
        
        # Get completed follow-up questionnaires
        cursor.execute("""
            SELECT token, asset_name, recipient_email, questionnaire_type, 
                   answers, questions, created_date, risk_id, completed_date
            FROM pending_questionnaires
            WHERE LOWER(status) = 'completed' AND questionnaire_type LIKE 'FOLLOWUP_%'
            ORDER BY completed_date DESC
        """)
        completed = [{
            'token': row[0], 'asset_name': row[1], 'recipient_email': row[2],
            'questionnaire_type': row[3], 'answers': row[4], 'questions': row[5],
            'created_date': row[6], 'risk_id': row[7], 'completed_date': row[8]
        } for row in cursor.fetchall()]
        
        # Get pending follow-up questionnaires
        cursor.execute("""
            SELECT token, asset_name, recipient_email, questionnaire_type, created_date, risk_id
            FROM pending_questionnaires
            WHERE LOWER(status) = 'pending' AND questionnaire_type LIKE 'FOLLOWUP_%'
            ORDER BY created_date DESC
        """)
        pending = [{
            'token': row[0], 'asset_name': row[1], 'recipient_email': row[2],
            'questionnaire_type': row[3], 'created_date': row[4], 'risk_id': row[5]
        } for row in cursor.fetchall()]
        
        conn.close()
        
        # Display completed questionnaires
        if completed:
            st.success(f"✅ {len(completed)} Completed Follow-up Questionnaire(s) - Ready to Process")
            
            for q in completed:
                st.markdown(f"**Risk ID:** {q['risk_id']} | **Asset:** {q['asset_name']}")
                st.caption(f"📧 From: {q['recipient_email']} | ⏰ Completed: {q.get('completed_date', 'N/A')}")
                st.caption(f"Type: {q['questionnaire_type']}")
                
                if st.button(f"📥 Process Follow-up", key=f"load_followup_{q['token']}", type="primary"):
                    with st.spinner("🤖 Processing follow-up and running AI re-assessment..."):
                        try:
                            # Get answers and questionnaire
                            answers = json.loads(q['answers']) if isinstance(q['answers'], str) else q['answers']
                            questionnaire = json.loads(q['questions']) if isinstance(q['questions'], str) else q['questions']
                            
                            # Get risk from database
                            conn = sqlite3.connect('database/risk_register.db')
                            cursor = conn.cursor()
                            cursor.execute("SELECT * FROM risks WHERE risk_id = ?", (q['risk_id'],))
                            risk_row = cursor.fetchone()
                            conn.close()
                            
                            if not risk_row:
                                st.error(f"❌ Risk {q['risk_id']} not found in database")
                            else:
                                # Save follow-up with AI re-assessment
                                result = save_followup_to_risk_register(
                                    risk_id=q['risk_id'],
                                    answers=answers,
                                    questionnaire=questionnaire,
                                    api_key=api_key
                                )
                                
                                if result['success']:
                                    st.success(f"✅ {result['message']}")
                                    
                                    # Show before/after comparison
                                    if result.get('new_residual_risk') is not None:
                                        st.markdown("### 📊 Risk Reduction Summary")
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            st.markdown("**BEFORE**")
                                            # 🔧 FIX: Get old residual risk from database
                                            conn = sqlite3.connect('database/risk_register.db')
                                            cursor = conn.cursor()
                                            cursor.execute("SELECT residual_risk_rating FROM risks WHERE risk_id = ?", (q['risk_id'],))
                                            row = cursor.fetchone()
                                            conn.close()
                                            old_residual = row[0] if row and row[0] else result.get('old_residual_risk', 0)
                                            st.metric("Residual Risk", f"{old_residual}/5")
                                        
                                        with col2:
                                            st.markdown("**AFTER**")
                                            new_residual = result.get('new_residual_risk')
                                            st.metric("Residual Risk", f"{new_residual}/5",
                                                    delta=f"-{old_residual - new_residual:.1f}" if new_residual < old_residual else f"+{new_residual - old_residual:.1f}",
                                                    delta_color="inverse")
                                        
                                        if result.get('risk_reduction_percentage'):
                                            reduction = result['risk_reduction_percentage']
                                            if reduction > 0:
                                                st.success(f"✅ Risk Reduced: {reduction:.0f}%")
                                            elif reduction < 0:
                                                st.error(f"⚠️ Risk Increased: {abs(reduction):.0f}%")
                                    
                                    # 🆕 NEW: Show Agent outputs
                                    with st.expander("📊 AI Analysis Details", expanded=True):
                                        if result.get('agent_3_result'):
                                            st.markdown("### 🔧 Agent 3: Control Re-evaluation")
                                            agent3 = result['agent_3_result']
                                            col1, col2, col3 = st.columns(3)
                                            with col1:
                                                st.metric("Controls Analyzed", agent3.get('controls_analyzed', 'N/A'))
                                            with col2:
                                                st.metric("In Progress", agent3.get('controls_in_progress', 'N/A'))
                                            with col3:
                                                st.metric("Implementation %", f"{agent3.get('implementation_percentage', 0)}%")
                                            
                                            st.markdown(f"**New Control Rating:** {agent3.get('new_control_rating', 'N/A')}/5")
                                            st.markdown(f"**Control Improvement:** +{agent3.get('control_improvement', 'N/A')}")
                                            
                                            if agent3.get('effectiveness_summary'):
                                                st.info(f"**Summary:** {agent3['effectiveness_summary']}")
                                            
                                            if agent3.get('key_improvements'):
                                                st.success("**Key Improvements:**")
                                                for imp in agent3['key_improvements']:
                                                    st.write(f"✅ {imp}")
                                            
                                            if agent3.get('remaining_gaps'):
                                                st.warning("**Remaining Gaps:**")
                                                for gap in agent3['remaining_gaps']:
                                                    st.write(f"⚠️ {gap}")
                                        
                                        if result.get('agent_2_result'):
                                            st.markdown("### 📊 Agent 2: Risk Recalculation")
                                            agent2 = result['agent_2_result']
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                st.markdown("**BEFORE:**")
                                                st.markdown(f"- Control Rating: {agent2.get('original_control_rating', 'N/A')}/5")
                                                st.markdown(f"- Residual Risk: {agent2.get('original_residual_risk', 'N/A')}/5")
                                                st.markdown(f"- Risk Level: {agent2.get('risk_level_before', 'N/A')}")
                                            with col2:
                                                st.markdown("**AFTER:**")
                                                st.markdown(f"- Control Rating: {agent2.get('new_control_rating', 'N/A')}/5")
                                                st.markdown(f"- Residual Risk: {agent2.get('new_residual_risk', 'N/A')}/5")
                                                st.markdown(f"- Risk Level: {agent2.get('risk_level_after', 'N/A')}")
                                            
                                            st.markdown(f"**Risk Reduction:** {agent2.get('risk_reduction_percentage', 'N/A')}%")
                                            st.markdown(f"**Trend:** {agent2.get('risk_trend', 'N/A')}")
                                            
                                            if agent2.get('recommendation'):
                                                st.info(f"**Recommendation:** {agent2['recommendation']}")
                                    
                                    # 🆕 NEW: Add link to view in Risk Register
                                    st.markdown("---")
                                    st.success("✅ Risk Register has been updated with follow-up results!")
                                    st.info("💡 Go to **Risk Register** page from the sidebar to view updated risk details.")
                                    
                                    # Add rerun button to refresh and clear completed questionnaire
                                    if st.button("🔄 Refresh Page", type="primary", key=f"refresh_{q['token']}"):
                                        st.rerun()
                                    
                                    # Mark questionnaire as saved (will disappear from pending list)
                                    conn = sqlite3.connect('database/risk_register.db')
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE pending_questionnaires SET status = 'saved' WHERE token = ?", (q['token'],))
                                    conn.commit()
                                    conn.close()
                                else:
                                    st.error(f"❌ {result['message']}")
                        
                        except Exception as e:
                            st.error(f"❌ Error processing follow-up: {str(e)}")
                            import traceback
                            with st.expander("Debug"):
                                st.code(traceback.format_exc())
                
                st.markdown("---")
        
        # Display pending questionnaires
        if pending:
            st.warning(f"⏳ {len(pending)} Pending Follow-up Questionnaire(s) - Waiting for Response")
            
            for q in pending:
                st.markdown(f"**Risk ID:** {q['risk_id']} | **Asset:** {q['asset_name']}")
                st.caption(f"📧 Sent to: {q['recipient_email']} | ⏰ Sent: {q.get('created_date', 'N/A')}")
                st.caption(f"🔗 Token: {q['token']}")
                st.markdown("---")
        
        # Show message if no questionnaires found
        if not completed and not pending:
            st.info("ℹ️ No follow-up questionnaires sent yet. Use the manual workflow below to generate and send follow-up questionnaires.")
    
    except Exception as e:
        st.error(f"❌ Error loading questionnaires: {str(e)}")
        import traceback
        with st.expander("Debug"):
            st.code(traceback.format_exc())
    
    # ═══════════════════════════════════════════════════════════════
    # OVERDUE FOLLOW-UP ALERTS
    # ═══════════════════════════════════════════════════════════════
    
    # ✅ PHASE 3: Show overdue follow-up alerts
    try:
        conn = sqlite3.connect('database/risk_register.db')
        cursor = conn.cursor()
        
        # Add missing columns for follow-up tracking
        missing_columns = [
            ('next_followup_date', 'TEXT'),
            ('followup_count', 'INTEGER DEFAULT 0'),
            ('last_followup_date', 'TEXT'),
            ('completion_percentage', 'REAL DEFAULT 0'),
            ('control_effectiveness', 'TEXT'),
            ('timeline_status', 'TEXT'),
            ('revised_completion_date', 'TEXT'),
            ('current_control_rating', 'REAL'),
            ('current_residual_risk', 'REAL'),
            ('risk_reduction_percentage', 'REAL'),
            ('last_reassessment_date', 'TEXT'),
            ('residual_risk_rating', 'REAL')
        ]
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(risks)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        # Add missing columns
        for col_name, col_type in missing_columns:
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE risks ADD COLUMN {col_name} {col_type}")
        
        conn.commit()
        conn.close()
    except Exception as e:
        pass  # Silently continue if columns already exist
    
    # ═══════════════════════════════════════════════════════════════
    # OVERDUE FOLLOW-UP ALERTS
    # ═══════════════════════════════════════════════════════════════
    
    try:
        overdue_risks = get_overdue_followups()
        
        if overdue_risks:
            st.error(f"⚠️ {len(overdue_risks)} risk(s) have overdue follow-ups!")
            
            for risk in overdue_risks[:5]:  # Show top 5
                days_overdue = int(risk['days_overdue'])
                st.warning(
                    f"🔴 **{risk['risk_id']}** - {risk['asset_name']} | "
                    f"Overdue by **{days_overdue} days** | "
                    f"Progress: {risk['completion_percentage'] or 0}% | "
                    f"Follow-ups: {risk['followup_count']}"
                )
            
            if len(overdue_risks) > 5:
                st.caption(f"... and {len(overdue_risks) - 5} more overdue follow-ups")
            
            st.markdown("---")
    except Exception as e:
        pass  # Silently fail if table doesn't have new columns yet
    
    # Get risks needing follow-up (5+ days old)
    try:
        risks_needing_followup = get_risks_needing_followup(days_threshold=5)
    except Exception as e:
        st.error(f"❌ Error loading risks: {str(e)}")
        import traceback
        with st.expander("Debug Info"):
            st.code(traceback.format_exc())
        return
    
    if not risks_needing_followup:
        st.success("✅ No risks need follow-up at this time!")
        st.info("💡 Risks will appear here 5 days after they are created in the Risk Register")
        return
    
    # ═══════════════════════════════════════════════════════════════
    # DISPLAY RISKS NEEDING FOLLOW-UP
    # ═══════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown(f"## ⚠️ {len(risks_needing_followup)} Risk(s) Need Follow-up")
    st.caption("These risks were created 5+ days ago and require follow-up assessment")
    
    # Display risks in a table
    st.markdown("### 📋 Risks Pending Follow-up:")
    
    for idx, risk in enumerate(risks_needing_followup, 1):
        followup_num = (risk.get('followup_count', 0) or 0) + 1  # Next follow-up number
        with st.expander(f"**{idx}. {risk['risk_id']} - {risk['asset_name']}** ({risk['days_since_creation']} days old) - Follow-up #{followup_num}", expanded=(idx==1)):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"**Risk ID:** {risk['risk_id']}")
                st.markdown(f"**Asset:** {risk['asset_name']}")
                st.markdown(f"**Threat:** {risk['threat_name']}")
            
            with col2:
                st.markdown(f"**Decision:** {risk['treatment_decision']}")
                st.markdown(f"**Created:** {risk['created_at']}")
                st.markdown(f"**Days Old:** {risk['days_since_creation']}")
            
            with col3:
                st.markdown(f"**Status:** {risk.get('status', 'Open')}")
                st.markdown(f"**Follow-ups Done:** {risk.get('followup_count', 0)}")
                st.markdown(f"**Progress:** {risk.get('completion_percentage', 0)}%")
            
            # Button to start follow-up for this risk
            if st.button(f"📝 Fill Follow-up Questionnaire", key=f"followup_btn_{risk['risk_id']}", type="primary"):
                st.session_state.selected_followup_risk = risk
                st.rerun()
        
        # ═══════════════════════════════════════════════════════════════
        # GENERATE FOLLOW-UP QUESTIONNAIRE (IF RISK SELECTED)
        # ═══════════════════════════════════════════════════════════════
    
    if 'selected_followup_risk' in st.session_state:
        selected_risk = st.session_state.selected_followup_risk
        
        st.markdown("---")
        st.markdown(f"## 📋 Follow-up for: {selected_risk['risk_id']}")
        
        # Show risk summary
        with st.expander("📊 Risk Details", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Risk ID:** {selected_risk['risk_id']}")
                st.markdown(f"**Asset:** {selected_risk['asset_name']}")
                st.markdown(f"**Threat:** {selected_risk['threat_name']}")
            with col2:
                st.markdown(f"**Decision:** {selected_risk['treatment_decision']}")
                st.markdown(f"**Created:** {selected_risk['created_at']}")
                st.markdown(f"**Days Old:** {selected_risk['days_since_creation']}")
        
        st.markdown("---")
        st.markdown("## 🤖 Step 2: Generate Follow-up Questionnaire")
        
        # Dynamic message based on decision type
        decision = selected_risk['treatment_decision']
        if decision == 'ACCEPT':
            st.info("💡 AI will generate questions to monitor the accepted risk and verify compensating controls")
        elif decision == 'TREAT':
            st.info("💡 AI will analyze the treatment plan and generate questions to track implementation progress")
        elif decision == 'TRANSFER':
            st.info("💡 AI will generate questions to verify risk transfer arrangements and monitor third-party controls")
        elif decision == 'TERMINATE':
            st.info("💡 AI will generate questions to confirm risk termination and verify asset/process discontinuation")
        else:
            st.info("💡 AI will generate intelligent follow-up questions based on the risk decision")
        
        if st.button("🔄 Generate Follow-up Questionnaire", type="primary", use_container_width=True):
            with st.spinner("🤖 AI is generating follow-up questionnaire..."):
                try:
                    questionnaire = generate_followup_questionnaire(selected_risk)
                    
                    if 'error' in questionnaire:
                        st.error(f"❌ Error: {questionnaire['error']}")
                        if 'raw_output' in questionnaire:
                            with st.expander("Debug Output"):
                                st.text(questionnaire['raw_output'])
                    else:
                        st.session_state.followup_questionnaire = questionnaire
                        st.session_state.followup_risk_id = selected_risk['risk_id']
                        st.success("✅ Follow-up questionnaire generated!")
                        
                        # Show follow-up number
                        followup_num = (selected_risk.get('followup_count', 0) or 0) + 1
                        st.info(f"🔢 This is Follow-up #{followup_num} for this risk")
                        
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())
        
        # ═══════════════════════════════════════════════════════════════
        # DISPLAY QUESTIONNAIRE
        # ═══════════════════════════════════════════════════════════════
        
        if 'followup_questionnaire' in st.session_state and \
           st.session_state.get('followup_risk_id') == selected_risk['risk_id']:
            
            st.markdown("---")
            st.markdown("## 📝 Step 3: Fill Follow-up Questionnaire")
            
            # 📧 EMAIL OPTION - Send questionnaire to stakeholder
            st.info("💡 **Choose how to fill the follow-up questionnaire:**")
            
            with st.expander("📧 Option 1: Send via Email", expanded=False):
                st.caption("Send questionnaire to risk owner/stakeholder")
                
                # Pre-fill with risk owner email
                default_email = selected_risk.get('risk_owner', '')
                recipient_email_followup = st.text_input(
                    "Recipient Email",
                    value=default_email,
                    key="followup_email_recipient",
                    placeholder="stakeholder@company.com"
                )
                
                if st.button("📧 Send Follow-up Questionnaire Email", type="primary", disabled=not recipient_email_followup):
                    with st.spinner(f"📧 Sending email to {recipient_email_followup}..."):
                        try:
                            from email_sender import send_questionnaire_email
                            
                            questionnaire = st.session_state.followup_questionnaire
                            
                            # Determine questionnaire type based on decision
                            q_type = f"FOLLOWUP_{selected_risk['treatment_decision']}"
                            
                            result = send_questionnaire_email(
                                recipient_email=recipient_email_followup,
                                asset_name=selected_risk['asset_name'],
                                questionnaire=questionnaire,
                                questionnaire_type=q_type,
                                risk_id=selected_risk['risk_id']
                            )
                            
                            if result.get('success'):
                                st.success(f"✅ Email sent successfully to {recipient_email_followup}!")
                                st.info(f"📋 **Tracking Token:** {result['token']}")
                                st.caption("The recipient will receive a link to fill the questionnaire online. Once completed, it will appear in 'Pending Follow-up Questionnaires' section above.")
                                
                                # Clear session state
                                if 'followup_questionnaire' in st.session_state:
                                    del st.session_state.followup_questionnaire
                                if 'followup_risk_id' in st.session_state:
                                    del st.session_state.followup_risk_id
                                if 'selected_followup_risk' in st.session_state:
                                    del st.session_state.selected_followup_risk
                                
                                import time
                                time.sleep(2)
                                st.rerun()
                            else:
                                error_msg = result.get('error', 'Unknown error')
                                st.error(f"❌ Failed to send email: {error_msg}")
                                
                                with st.expander("💡 Troubleshooting Tips"):
                                    st.markdown("""
                                    **Common issues:**
                                    - Outlook not installed or not default email client
                                    - Windows security blocking COM automation
                                    - Antivirus blocking script access to Outlook
                                    
                                    **Solutions:**
                                    1. Install Microsoft Outlook
                                    2. Set Outlook as default email client
                                    3. Run this app as Administrator
                                    4. Add Python to antivirus exceptions
                                    5. Use manual option below instead
                                    """)
                        
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                            import traceback
                            with st.expander("Debug"):
                                st.code(traceback.format_exc())
            
            with st.expander("✍️ Option 2: Fill Manually", expanded=True):
                st.info("👇 Scroll down to see the questionnaire form below")
            
            questionnaire = st.session_state.followup_questionnaire
            
            # Show metadata dynamically
            metadata = questionnaire.get('questionnaire_metadata', {})
            risk_ctx = questionnaire.get('risk_context', {})
            
            with st.expander("📊 Questionnaire Info", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Type:** {metadata.get('questionnaire_type', f"{selected_risk['treatment_decision']} Follow-up")}")
                    st.markdown(f"**Generated:** {metadata.get('generation_date', datetime.now().strftime('%Y-%m-%d'))}")
                    st.markdown(f"**Days Since Created:** {metadata.get('days_since_identification', selected_risk['days_since_creation'])}")
                with col2:
                    # 🔧 FIX: Get target_completion_date from database
                    target_date = selected_risk.get('target_completion_date', 'N/A')
                    if not target_date or target_date == 'N/A' or target_date == 'Not set':
                        # Calculate from created_at + 90 days
                        if selected_risk.get('created_at'):
                            try:
                                from datetime import timedelta
                                created = datetime.strptime(selected_risk['created_at'].split()[0], '%Y-%m-%d')
                                target_date = (created + timedelta(days=90)).strftime('%Y-%m-%d')
                            except:
                                target_date = 'N/A'
                    
                    st.markdown(f"**Target Date:** {target_date}")
                    
                    # Calculate days until target
                    days_until = metadata.get('days_until_target', 'N/A')
                    if days_until == 'N/A' and target_date != 'N/A':
                        try:
                            target_dt = datetime.strptime(target_date, '%Y-%m-%d')
                            days_until = (target_dt - datetime.now()).days
                        except:
                            pass
                    
                    st.markdown(f"**Days Until Target:** {days_until}")
            
            # Create form
            with st.form("followup_questionnaire_form"):
                answers = {}
                
                # 🔧 FIX: Decode HTML entities in questionnaire
                import html
                def clean_html_recursive(obj):
                    if isinstance(obj, str):
                        return html.unescape(obj)
                    elif isinstance(obj, dict):
                        return {k: clean_html_recursive(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [clean_html_recursive(item) for item in obj]
                    return obj
                
                questionnaire = clean_html_recursive(questionnaire)
                
                # 🔧 FIX: Renumber sections sequentially
                section_counter = 1
                
                for section in questionnaire.get('sections', []):
                    section_title = section.get('title', 'Section')
                    # Remove existing section numbers if present
                    import re
                    section_title = re.sub(r'^Section\s*\d+:\s*', '', section_title)
                    
                    st.markdown(f"### 📑 Section {section_counter}: {section_title}")
                    section_counter += 1
                    
                    if section.get('description'):
                        st.caption(section['description'])
                    
                    st.markdown("")
                    
                    for field in section.get('fields', []):
                        f_id = field.get('id', '')
                        f_name = field.get('field_name', 'Field')
                        f_type = field.get('type', 'text')
                        f_placeholder = field.get('placeholder', '')
                        f_value = field.get('value', '')
                        
                        # Skip if no field name
                        if not f_name or f_name == 'Field':
                            continue
                        
                        # Skip display fields (pre-filled)
                        if f_type == 'display':
                            st.info(f"**{f_name}:** {f_value}")
                            continue
                        
                        # Display based on type
                        if f_type == 'select':
                            options = field.get('options', [])
                            answers[f_id] = st.selectbox(
                                f_name,
                                options=options,
                                key=f"fq_{f_id}",
                                placeholder=f_placeholder
                            )
                        
                        elif f_type == 'number':
                            answers[f_id] = st.number_input(
                                f_name,
                                min_value=0,
                                max_value=100,
                                key=f"fq_{f_id}"
                            )
                        
                        elif f_type == 'textarea':
                            answers[f_id] = st.text_area(
                                f_name,
                                key=f"fq_{f_id}",
                                placeholder=f_placeholder,
                                height=100
                            )
                        
                        elif f_type == 'date':
                            answers[f_id] = st.date_input(
                                f_name,
                                key=f"fq_{f_id}"
                            )
                        
                        else:  # Default text
                            answers[f_id] = st.text_input(
                                f_name,
                                key=f"fq_{f_id}",
                                placeholder=f_placeholder
                            )
                
                # Submit button
                submitted = st.form_submit_button(
                    "✅ Submit Follow-up & Update Risk Register",
                    type="primary",
                    use_container_width=True
                )
            
            # Process submission
            if submitted:
                with st.spinner("🤖 Running AI agents to recalculate risk..."):
                    try:
                        # Save to database with API key for agent execution
                        result = save_followup_to_risk_register(
                            risk_id=selected_risk['risk_id'],
                            answers=answers,
                            questionnaire=questionnaire,
                            api_key=api_key
                        )
                        
                        if result['success']:
                            st.success(f"✅ {result['message']}")
                            
                            # 📊 SHOW BEFORE/AFTER COMPARISON
                            if result.get('new_residual_risk') is not None:
                                st.markdown("---")
                                st.markdown("## 📊 Risk Reduction Summary")
                                
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.markdown("### BEFORE (Initial Assessment)")
                                    st.metric("Control Rating", f"{selected_risk.get('control_rating', 'N/A')}/5")
                                    st.metric("Residual Risk", f"{selected_risk.get('residual_risk_rating', 'N/A')}/5")
                                    st.markdown(f"**Status:** {selected_risk.get('status', 'Open')}")
                                
                                with col2:
                                    st.markdown("### AFTER (Current Follow-up)")
                                    
                                    new_control = result.get('new_control_rating')
                                    old_control = selected_risk.get('control_rating', 0)
                                    if new_control:
                                        st.metric("Control Rating", f"{new_control}/5", 
                                                delta=f"+{new_control - old_control:.1f}" if new_control > old_control else f"{new_control - old_control:.1f}")
                                    
                                    new_residual = result.get('new_residual_risk')
                                    old_residual = selected_risk.get('residual_risk_rating', 0)
                                    if new_residual is not None:
                                        st.metric("Residual Risk", f"{new_residual}/5",
                                                delta=f"-{old_residual - new_residual:.1f}" if new_residual < old_residual else f"+{new_residual - old_residual:.1f}",
                                                delta_color="inverse")
                                    
                                    st.markdown(f"**Status:** {result.get('status', 'In Progress')}")
                                
                                # Show progress
                                if result.get('risk_reduction_percentage') is not None:
                                    st.markdown("### 📈 Progress")
                                    risk_reduction = result['risk_reduction_percentage']
                                    if risk_reduction > 0:
                                        st.success(f"✅ Risk Reduced: {risk_reduction:.0f}%")
                                    elif risk_reduction < 0:
                                        st.error(f"⚠️ Risk Increased: {abs(risk_reduction):.0f}%")
                                    else:
                                        st.info("ℹ️ Risk level unchanged")
                            
                            st.info(f"📊 Total follow-ups recorded: {result['followup_count']}")
                            
                            # Show summary with proper formatting
                            with st.expander("📊 Follow-up Details", expanded=True):
                                import html
                                
                                if result.get('agent_3_result'):
                                    st.markdown("### 🔧 Agent 3 (Control Re-evaluation)")
                                    agent3 = result['agent_3_result']
                                    st.markdown(f"**Controls Analyzed:** {agent3.get('controls_analyzed', 'N/A')}")
                                    st.markdown(f"**Controls Implemented:** {agent3.get('controls_implemented', 'N/A')}")
                                    st.markdown(f"**Implementation %:** {agent3.get('implementation_percentage', 'N/A')}%")
                                    st.markdown(f"**New Control Rating:** {agent3.get('new_control_rating', 'N/A')}/5")
                                    st.markdown(f"**Control Improvement:** +{agent3.get('control_improvement', 'N/A')}")
                                    if agent3.get('effectiveness_summary'):
                                        st.info(f"**Summary:** {html.unescape(agent3['effectiveness_summary'])}")
                                    if agent3.get('key_improvements'):
                                        st.success("**Key Improvements:**")
                                        for imp in agent3['key_improvements']:
                                            st.write(f"✅ {html.unescape(str(imp))}")
                                
                                if result.get('agent_2_result'):
                                    st.markdown("### 📊 Agent 2 (Risk Recalculation)")
                                    agent2 = result['agent_2_result']
                                    st.markdown(f"**Risk Rating:** {agent2.get('inherent_risk_rating', 'N/A')}/5 (unchanged)")
                                    st.markdown(f"**Original Control Rating:** {agent2.get('original_control_rating', 'N/A')}/5")
                                    st.markdown(f"**New Control Rating:** {agent2.get('new_control_rating', 'N/A')}/5")
                                    st.markdown(f"**Original Residual Risk:** {agent2.get('original_residual_risk', 'N/A')}/5")
                                    st.markdown(f"**New Residual Risk:** {agent2.get('new_residual_risk', 'N/A')}/5")
                                    st.markdown(f"**Risk Reduction:** {agent2.get('risk_reduction_percentage', 'N/A')}%")
                                    st.markdown(f"**Risk Level:** {agent2.get('risk_level_before', 'N/A')} → {agent2.get('risk_level_after', 'N/A')}")
                                    st.markdown(f"**Trend:** {agent2.get('risk_trend', 'N/A')}")
                                    if agent2.get('recommendation'):
                                        st.info(f"**Recommendation:** {html.unescape(agent2['recommendation'])}")
                            
                            # Clear session state
                            if st.button("🔄 Complete Another Follow-up"):
                                if 'selected_followup_risk' in st.session_state:
                                    del st.session_state.selected_followup_risk
                                if 'followup_questionnaire' in st.session_state:
                                    del st.session_state.followup_questionnaire
                                if 'followup_risk_id' in st.session_state:
                                    del st.session_state.followup_risk_id
                                st.rerun()
                        else:
                            st.error(f"❌ {result['message']}")
                        
                    except Exception as e:
                        st.error(f"❌ Error saving follow-up: {str(e)}")
                        import traceback
                        with st.expander("Error Details"):
                            st.code(traceback.format_exc())


if __name__ == "__main__":
    st.set_page_config(
        page_title="Risk Follow-up",
        page_icon="🔄",
        layout="wide"
    )
    
    # Mock API key for testing
    api_key = "test_key"
    render_followup_page(api_key)