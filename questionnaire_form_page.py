"""
📋 Questionnaire Form Page
External stakeholders access this to fill questionnaires
"""

import streamlit as st
import json
from datetime import datetime, date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from database_manager import get_database_connection

DB_PATH = 'database/risk_register.db'

def get_questionnaire_by_token(token):
    """Fetch questionnaire from database using token"""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT token, asset_name, questionnaire_type, questions, status, recipient_email
        FROM pending_questionnaires
        WHERE token = ?
    """, (token,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'token': result[0],
            'asset_name': result[1],
            'questionnaire_type': result[2],
            'questions': json.loads(result[3]),
            'status': result[4],
            'recipient_email': result[5]
        }
    return None

def save_questionnaire_answers(token, answers):
    """Save answers to database"""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE pending_questionnaires
        SET answers = ?, status = 'completed', completed_date = ?
        WHERE token = ?
    """, (json.dumps(answers), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), token))
    
    conn.commit()
    conn.close()

def show_questionnaire_form(token):
    """Display questionnaire form with full structure"""
    
    st.set_page_config(page_title="Risk Assessment Questionnaire", page_icon="📋")
    
    if not token:
        st.error("❌ Invalid questionnaire link")
        st.stop()
    
    # Fetch questionnaire
    questionnaire_data = get_questionnaire_by_token(token)
    
    if not questionnaire_data:
        st.error("❌ Questionnaire not found")
        st.stop()
    
    if questionnaire_data['status'] == 'Completed':
        st.success("✅ This questionnaire has already been completed")
        st.info("Thank you for your response!")
        st.stop()
    
    # Display form header
    st.title("📋 Risk Assessment Questionnaire")
    st.markdown(f"**Asset:** {questionnaire_data['asset_name']}")
    st.markdown(f"**Type:** {questionnaire_data['questionnaire_type']}")
    st.markdown(f"**Recipient:** {questionnaire_data['recipient_email']}")
    st.divider()
    
    # Get questionnaire structure from questions field
    questionnaire = questionnaire_data['questions']
    
    # Decode HTML entities in questionnaire
    import html
    def decode_html_recursive(obj):
        if isinstance(obj, str):
            return html.unescape(obj)
        elif isinstance(obj, dict):
            return {k: decode_html_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [decode_html_recursive(item) for item in obj]
        return obj
    
    questionnaire = decode_html_recursive(questionnaire)
    
    # ✅ DETECT QUESTIONNAIRE TYPE AND USE APPROPRIATE RENDERING
    questionnaire_type = questionnaire_data['questionnaire_type']
    is_followup = questionnaire_type.startswith('FOLLOWUP_')
    is_agent0 = questionnaire_type == 'Agent0'
    is_accept = questionnaire_type == 'ACCEPT'
    is_transfer = questionnaire_type == 'TRANSFER'
    is_terminate = questionnaire_type == 'TERMINATE'
    
    if isinstance(questionnaire, dict) and 'sections' in questionnaire:
        # Collect answers dictionary
        answers = {}
        
        if is_followup:
            # 🔄 FOLLOW-UP QUESTIONNAIRE (Copied EXACTLY from followup_page.py line 714)
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
            section_counter = 1
            
            for section in questionnaire.get('sections', []):
                section_title = section.get('title', 'Section')
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
                    
                    if not f_name or f_name == 'Field':
                        continue
                    
                    if f_type == 'display':
                        st.info(f"**{f_name}:** {f_value}")
                        continue
                    
                    if f_type == 'select':
                        options = field.get('options', [])
                        answers[f_id] = st.selectbox(f_name, options=options, key=f"fq_{f_id}", placeholder=f_placeholder)
                    elif f_type == 'number':
                        answers[f_id] = st.number_input(f_name, min_value=0, max_value=100, key=f"fq_{f_id}")
                    elif f_type == 'textarea':
                        answers[f_id] = st.text_area(f_name, key=f"fq_{f_id}", placeholder=f_placeholder, height=100)
                    elif f_type == 'date':
                        answers[f_id] = st.date_input(f_name, key=f"fq_{f_id}")
                    else:
                        answers[f_id] = st.text_input(f_name, key=f"fq_{f_id}", placeholder=f_placeholder)
            
            if st.button("✅ Submit Follow-up & Update Risk Register", type="primary", use_container_width=True):
                for key, value in answers.items():
                    if hasattr(value, 'strftime'):
                        answers[key] = value.strftime('%Y-%m-%d')
                save_questionnaire_answers(token, answers)
                st.success("✅ Thank you! Your follow-up answers have been submitted successfully.")
                st.balloons()
        
        
        elif is_agent0:
            # 🤖 AGENT 0 QUESTIONNAIRE RENDERING (Risk Assessment)
            st.info("📋 **Risk Assessment Questionnaire** - Provide asset information for risk analysis")
            
            for section_idx, section in enumerate(questionnaire.get('sections', [])):
                section_name = section.get('section_name', section.get('title', f'Section {section_idx + 1}'))
                st.markdown(f"### 📋 {section_name}")
                
                if section.get('section_purpose'):
                    st.caption(f"**Purpose:** {section['section_purpose']}")
                if section.get('section_description'):
                    st.caption(section['section_description'])
                
                for question in section.get('questions', []):
                    q_id = question.get('question_id')
                    q_text = question.get('question_text')
                    q_type = question.get('question_type', 'text')
                    q_options = question.get('options', [])
                    q_help = question.get('help_text', '')
                    q_required = question.get('required', False)
                    
                    if question.get('why_this_matters'):
                        q_help += f"\n\n💡 Why this matters: {question['why_this_matters']}"
                    
                    display_text = f"{q_text} {'*' if q_required else ''}"
                    
                    if q_type == 'text':
                        answers[q_id] = st.text_input(display_text, key=f"a0_{q_id}", help=q_help)
                    elif q_type == 'textarea':
                        answers[q_id] = st.text_area(display_text, key=f"a0_{q_id}", help=q_help, height=100)
                    elif q_type in ['dropdown', 'select']:
                        display_options = []
                        for opt in q_options:
                            if isinstance(opt, dict):
                                display_options.append(opt.get('label', opt.get('value', str(opt))))
                            else:
                                display_options.append(str(opt))
                        
                        if not q_required:
                            display_options = ['-- Select --'] + display_options
                        
                        selected = st.selectbox(display_text, options=display_options, key=f"a0_{q_id}", help=q_help)
                        answers[q_id] = None if selected == '-- Select --' else selected
                    elif q_type == 'multiselect':
                        display_options = []
                        for opt in q_options:
                            if isinstance(opt, dict):
                                display_options.append(opt.get('label', opt.get('value', str(opt))))
                            else:
                                display_options.append(str(opt))
                        
                        answers[q_id] = st.multiselect(display_text, options=display_options, key=f"a0_{q_id}", help=q_help)
                    elif q_type == 'number':
                        answers[q_id] = st.number_input(display_text, key=f"a0_{q_id}", help=q_help, min_value=0)
                    elif q_type in ['rating', 'rating_scale']:
                        scale = question.get('scale', '1-5')
                        if '-' in scale:
                            try:
                                min_val, max_val = map(int, scale.split('-'))
                            except:
                                min_val, max_val = 1, 5
                        else:
                            min_val, max_val = 1, 5
                        
                        answers[q_id] = st.slider(display_text, min_value=min_val, max_value=max_val, key=f"a0_{q_id}", help=q_help)
                    else:
                        answers[q_id] = st.text_input(display_text, key=f"a0_{q_id}", help=q_help)
            
            # Submit button for Agent 0
            if st.button("📤 Submit Risk Assessment Questionnaire", use_container_width=True, type="primary"):
                save_questionnaire_answers(token, answers)
                st.success("✅ Thank you! Your risk assessment answers have been submitted successfully.")
                st.balloons()
        
        elif is_transfer:
            # 🔄 TRANSFER QUESTIONNAIRE (Copied EXACTLY from main_app.py line 3513)
            st.markdown("##### 📝 Transfer Details (Please Fill)")
            st.caption("Provide the following transfer-specific information:")
            
            sections = questionnaire.get('sections', [])
            
            for section_idx, section in enumerate(sections):
                section_title = section.get('title') or section.get('section_title', 'Section')
                st.markdown(f"##### {section_title}")
                
                section_desc = section.get('description', '')
                if section_desc:
                    st.caption(section_desc)
                
                questions = section.get('questions', section.get('fields', []))
                
                for q_idx, question in enumerate(questions):
                    q_id = question.get('id', question.get('question_id', question.get('field_id', question.get('field_name', 'Q'))))
                    # CRITICAL: field_name IS the question text for TRANSFER questionnaire
                    q_text = question.get('field_name') or question.get('text') or question.get('question_text') or question.get('question') or question.get('label') or question.get('description', 'Question')
                    q_type = question.get('type', question.get('question_type', question.get('field_type', 'text')))
                    q_help = question.get('help_text', question.get('help', ''))
                    q_required = question.get('required', False)
                    options = question.get('options', [])
                    
                    widget_key = f"transfer_s{section_idx}_q{q_idx}_{q_id}"
                    default_value = question.get('value', '')
                    
                    if q_required:
                        q_text = f"{q_text} *"
                    
                    if q_type == 'display':
                        display_value = question.get('value', '')
                        st.info(f"**{q_text}**\n\n{display_value}")
                        answers[q_id] = display_value
                        continue
                    
                    if q_type in ['text_area', 'textarea']:
                        answers[q_id] = st.text_area(q_text, value=default_value or '', key=widget_key, help=q_help, height=100)
                    elif q_type == 'text':
                        answers[q_id] = st.text_input(q_text, value=default_value or '', key=widget_key, help=q_help)
                    elif q_type == 'number':
                        min_val = question.get('min', question.get('min_value', 0))
                        answers[q_id] = st.number_input(q_text, value=float(default_value) if default_value else 0.0, key=widget_key, help=q_help, min_value=float(min_val))
                    elif q_type == 'date':
                        answers[q_id] = st.date_input(q_text, value=date.today(), key=widget_key, help=q_help)
                    elif q_type in ['select', 'dropdown']:
                        if options:
                            display_options = [opt.get('label', opt.get('value', str(opt))) if isinstance(opt, dict) else str(opt) for opt in options]
                            answers[q_id] = st.selectbox(q_text, options=display_options, key=widget_key, help=q_help)
                        else:
                            answers[q_id] = st.text_input(q_text, key=widget_key, help=q_help)
                    else:
                        answers[q_id] = st.text_input(q_text, key=widget_key, help=q_help)
            
            if st.button("✅ Submit & Generate Transfer Form", use_container_width=True, type="primary"):
                for key, value in answers.items():
                    if hasattr(value, 'strftime'):
                        answers[key] = value.strftime('%Y-%m-%d')
                save_questionnaire_answers(token, answers)
                st.success("✅ Thank you! Your risk transfer questionnaire has been submitted successfully.")
                st.balloons()
        
        elif is_accept:
            # ✅ ACCEPT QUESTIONNAIRE (Copied EXACTLY from main_app.py line 4605)
            for section in questionnaire.get('sections', []):
                section_title = section.get('title', section.get('section_title', 'Section'))
                st.markdown(f"#### {section_title}")
                
                for question in section.get('questions', []):
                    q_id = question.get('id', question.get('question_id', 'Q'))
                    # ✅ FIX: ACCEPT uses 'question' field, not 'text' or 'question_text'
                    q_text = question.get('question', question.get('text', question.get('question_text', 'Question')))
                    q_type = question.get('type', question.get('question_type', 'text'))
                    q_help = question.get('help_text', question.get('help', ''))
                    q_required = question.get('required', False)
                    options = question.get('options', [])
                    default_value = question.get('value', '')
                    
                    if q_required:
                        q_text = f"{q_text} *"
                    
                    if q_type == 'display':
                        st.info(f"**{q_text}:** {default_value}")
                        answers[q_id] = default_value
                        continue
                    
                    if q_type in ['text_area', 'textarea']:
                        val = st.text_area(q_text, value=default_value or '', key=f"accept_{q_id}", help=q_help, height=100)
                        answers[q_id] = val
                    elif q_type == 'text':
                        val = st.text_input(q_text, value=default_value or '', key=f"accept_{q_id}", help=q_help)
                        answers[q_id] = val
                    elif q_type == 'email':
                        val = st.text_input(q_text, value=default_value or '', key=f"accept_{q_id}", help=q_help, placeholder="email@example.com")
                        answers[q_id] = val
                    elif q_type == 'number':
                        val = st.number_input(q_text, key=f"accept_{q_id}", help=q_help, min_value=0)
                        answers[q_id] = val
                    elif q_type == 'date':
                        val = st.date_input(q_text, value=date.today(), key=f"accept_{q_id}", help=q_help)
                        answers[q_id] = val
                    elif q_type in ['select', 'dropdown']:
                        if options:
                            display_options = [opt.get('label', opt.get('value', str(opt))) if isinstance(opt, dict) else str(opt) for opt in options]
                            val = st.selectbox(q_text, options=display_options, key=f"accept_{q_id}", help=q_help)
                            answers[q_id] = val
                        else:
                            val = st.text_input(q_text, key=f"accept_{q_id}", help=q_help)
                            answers[q_id] = val
                    elif q_type == 'radio':
                        if options:
                            val = st.radio(q_text, options=options, key=f"accept_{q_id}", help=q_help)
                            answers[q_id] = val
                        else:
                            val = st.text_input(q_text, key=f"accept_{q_id}", help=q_help)
                            answers[q_id] = val
                    elif q_type in ['checkbox', 'multiselect']:
                        if options:
                            # ✅ FIX: Don't use markdown bold to avoid *** issue
                            st.write(f"**{q_text}**")
                            if q_help:
                                st.caption(q_help)
                            
                            selected = []
                            for idx, opt in enumerate(options):
                                if isinstance(opt, dict):
                                    # ✅ FIX: Handle both control format and gap format
                                    control_name = opt.get('label', opt.get('control_name', opt.get('gap_description', f'Control {idx+1}')))
                                    control_desc = opt.get('description', opt.get('gap_description', ''))
                                    priority = opt.get('priority', 'N/A')
                                    control_type = opt.get('control_type', 'N/A')
                                    cost = opt.get('cost', 'N/A')
                                    timeline = opt.get('timeline', 'N/A')
                                    complexity = opt.get('complexity', 'N/A')
                                    risk_reduction = opt.get('risk_reduction', 'N/A')
                                    severity = opt.get('severity', '')
                                    
                                    with st.expander(f"✅ {control_name}", expanded=False):
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            if control_desc:
                                                st.markdown(f"**Description:** {control_desc}")
                                            if priority != 'N/A':
                                                st.markdown(f"**Priority:** {priority}")
                                            if control_type != 'N/A':
                                                st.markdown(f"**Type:** {control_type}")
                                            if severity:
                                                severity_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "CRITICAL": "⚠️"}.get(severity, "")
                                                st.markdown(f"**{severity_color} Severity:** {severity}")
                                        
                                        with col2:
                                            if cost != 'N/A':
                                                st.markdown(f"**💰 Cost:** {cost}")
                                            if timeline != 'N/A':
                                                st.markdown(f"**⏱️ Timeline:** {timeline}")
                                            if risk_reduction != 'N/A':
                                                st.markdown(f"**📉 Risk Reduction:** {risk_reduction}")
                                        
                                        if complexity != 'N/A':
                                            st.markdown(f"**Complexity:** {complexity}")
                                        
                                        if st.checkbox(f"Select {control_name}", key=f"accept_{q_id}_opt_{idx}"):
                                            selected.append(opt)
                                else:
                                    if st.checkbox(str(opt), key=f"accept_{q_id}_opt_{idx}"):
                                        selected.append(str(opt))
                            
                            answers[q_id] = selected
                        else:
                            st.warning(f"⚠️ No options available for {q_text}")
                            answers[q_id] = []
                    else:
                        val = st.text_input(q_text, key=f"accept_{q_id}", help=q_help)
                        answers[q_id] = val
            
            if st.button("✅ Submit & Generate Acceptance Form", type="primary", use_container_width=True):
                for key, value in answers.items():
                    if hasattr(value, 'strftime'):
                        answers[key] = value.strftime('%Y-%m-%d')
                save_questionnaire_answers(token, answers)
                st.success("✅ Thank you! Your risk acceptance questionnaire has been submitted successfully.")
                st.balloons()
        
        elif is_terminate:
            # 🚫 TERMINATE QUESTIONNAIRE (Copied EXACTLY from main_app.py line 3891)
            st.markdown("##### 📝 Termination Details (Please Fill)")
            st.caption("Provide the following termination-specific information:")
            
            for section_idx, section in enumerate(questionnaire.get('sections', [])):
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
                    
                    widget_key = f"terminate_s{section_idx}_q{q_idx}_{q_id}"
                    default_value = question.get('value', '')
                    
                    if q_required:
                        q_text = f"{q_text} *"
                    
                    if q_type == 'display':
                        pre_filled_value = question.get('value', question.get('default_value', 'N/A'))
                        st.info(f"**{q_text}:** {pre_filled_value}")
                        answers[q_id] = pre_filled_value
                        continue
                    
                    if q_type in ['text_area', 'textarea']:
                        val = st.text_area(q_text, value=default_value or '', key=widget_key, help=q_help, height=100)
                        answers[q_id] = val
                    elif q_type == 'text':
                        val = st.text_input(q_text, value=default_value or '', key=widget_key, help=q_help)
                        answers[q_id] = val
                    elif q_type == 'number':
                        min_val = question.get('min', question.get('min_value', 0))
                        val = st.number_input(q_text, value=float(default_value) if default_value else 0.0, key=widget_key, help=q_help, min_value=float(min_val))
                        answers[q_id] = val
                    elif q_type == 'date':
                        val = st.date_input(q_text, value=date.today(), key=widget_key, help=q_help)
                        answers[q_id] = val
                    elif q_type in ['select', 'dropdown']:
                        if options:
                            display_options = [opt.get('label', opt.get('value', str(opt))) if isinstance(opt, dict) else str(opt) for opt in options]
                            val = st.selectbox(q_text, options=display_options, key=widget_key, help=q_help)
                            answers[q_id] = val
                        else:
                            val = st.text_input(q_text, key=widget_key, help=q_help)
                            answers[q_id] = val
                    else:
                        val = st.text_input(q_text, key=widget_key, help=q_help)
                        answers[q_id] = val
            
            if st.button("✅ Submit & Generate Termination Form", type="primary", use_container_width=True):
                for key, value in answers.items():
                    if hasattr(value, 'strftime'):
                        answers[key] = value.strftime('%Y-%m-%d')
                save_questionnaire_answers(token, answers)
                st.success("✅ Thank you! Your risk termination questionnaire has been submitted successfully.")
                st.balloons()
        
        else:
            # 📋 GENERIC QUESTIONNAIRE RENDERING (fallback for unknown types)
            st.warning(f"⚠️ **Unknown Questionnaire Type:** {questionnaire_type}")
            st.info("📋 **Generic Questionnaire** - Using fallback rendering")
            for section_idx, section in enumerate(questionnaire.get('sections', [])):
                section_title = section.get('section_title', section.get('section_name', section.get('title', '')))
                if section_title and section_title.strip().lower() != 'section':
                    st.markdown(f"### {section_title}")
                    section_help = section.get('help_text', section.get('section_purpose', section.get('description', '')))
                    if section_help:
                        st.caption(f"ℹ️ {section_help}")
                
                questions_list = section.get('questions', section.get('fields', []))
                for q_idx, qu in enumerate(questions_list):
                    q_id = qu.get('question_id', qu.get('id', f'Q{section_idx}_{q_idx}'))
                    q_text = qu.get('question_text', qu.get('question', qu.get('text', 'Question')))
                    q_text = str(q_text).replace('**', '').replace('__', '').replace('_', '').strip()
                    q_text = ' '.join(q_text.split())
                    q_type = qu.get('question_type', qu.get('type', 'text'))
                    q_help = qu.get('help_text', '')
                    q_placeholder = qu.get('placeholder', '')
                    q_required = qu.get('required', False)
                    options = qu.get('options', [])
                    widget_key = f"q_s{section_idx}_q{q_idx}_{q_id}"
                    
                    display_text = f"{q_text} {'*' if q_required else ''}"
                    
                    if q_type == 'display':
                        display_value = qu.get('value', '')
                        st.info(f"ℹ️ {q_text}: {display_value}")
                        answers[q_id] = display_value
                        continue
                    
                    if q_type in ['text_area', 'textarea']:
                        answers[q_id] = st.text_area(display_text, key=widget_key, help=q_help, placeholder=q_placeholder, height=100)
                    elif q_type == 'date':
                        date_val = st.date_input(display_text, value=date.today(), key=widget_key, help=q_help)
                        answers[q_id] = date_val.strftime('%Y-%m-%d') if date_val else ''
                    elif q_type == 'text':
                        answers[q_id] = st.text_input(display_text, key=widget_key, help=q_help, placeholder=q_placeholder)
                    elif q_type in ['select', 'dropdown']:
                        if options:
                            opts = [opt.get('label', opt.get('value', str(opt))) if isinstance(opt, dict) else str(opt) for opt in options]
                            answers[q_id] = st.selectbox(display_text, options=opts, key=widget_key, help=q_help)
                        else:
                            answers[q_id] = st.text_input(display_text, key=widget_key, help=q_help, placeholder=q_placeholder)
                    elif q_type in ['checkbox', 'multiselect']:
                        st.write(f"**{q_text}**")
                        if q_help:
                            st.caption(f"ℹ️ {q_help}")
                        
                        selected_items = []
                        for idx, opt in enumerate(options):
                            if isinstance(opt, dict):
                                ctrl_name = opt.get('label', opt.get('control_name', opt.get('gap_description', f'Control {idx+1}')))
                                ctrl_name = str(ctrl_name).replace('**', '')
                                
                                with st.expander(f"🛡️ {ctrl_name}", expanded=False):
                                    if opt.get('description'):
                                        desc = str(opt['description']).replace('**', '')
                                        st.info(desc)
                                    elif opt.get('gap_description'):
                                        gap_desc = str(opt['gap_description']).replace('**', '')
                                        st.info(f"**Gap:** {gap_desc}")
                                    
                                    if opt.get('evidence'):
                                        st.caption(f"📋 Evidence: {opt['evidence']}")
                                    if opt.get('impact'):
                                        st.caption(f"⚠️ Impact: {opt['impact']}")
                                    if opt.get('severity'):
                                        severity_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(opt['severity'], "⚪")
                                        st.caption(f"{severity_color} Severity: {opt['severity']}")
                                    
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
                                    
                                    if st.checkbox(f"Select {ctrl_name}", key=f"{widget_key}_opt_{idx}"):
                                        selected_items.append(ctrl_name)
                            else:
                                if st.checkbox(str(opt), key=f"{widget_key}_opt_{idx}"):
                                    selected_items.append(str(opt))
                        
                        answers[q_id] = selected_items
                    else:
                        answers[q_id] = st.text_input(display_text, key=widget_key, help=q_help, placeholder=q_placeholder)
            
            # Submit button for generic questionnaire
            if st.button("📤 Submit Answers", use_container_width=True, type="primary"):
                save_questionnaire_answers(token, answers)
                st.success("✅ Thank you! Your answers have been submitted successfully.")
                st.balloons()
    else:
        # Fallback: plain questions list
        answers = {}
        for idx, question in enumerate(questionnaire, 1):
            answers[f"Q{idx}"] = st.text_area(f"**Question {idx}:** {question}", height=100, key=f"q_{idx}")
        
        if st.button("📤 Submit Answers", use_container_width=True):
            if all(answers.values()):
                save_questionnaire_answers(token, answers)
                st.success("✅ Thank you! Your answers have been submitted successfully.")
                st.balloons()
            else:
                st.error("❌ Please answer all questions before submitting")
