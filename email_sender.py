"""
📧 Email Sender for Questionnaires
Sends questionnaires via SMTP (cloud) or Outlook (local) with web form links
"""

import uuid
import sqlite3
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
from database_manager import get_database_connection

load_dotenv()

DB_PATH = 'database/risk_register.db'

def send_email_smtp(recipient_email, subject, html_body):
    """
    Send email via SMTP (Gmail/Outlook) - Works on cloud and local
    """
    try:
        email_address = os.getenv('EMAIL_ADDRESS')
        email_password = os.getenv('EMAIL_PASSWORD')
        smtp_server = os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('EMAIL_SMTP_PORT', '587'))
        
        if not email_address or not email_password:
            raise Exception("Email credentials not configured in .env file")
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = email_address
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Attach HTML body
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        # Send via SMTP
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)
        
        print(f"[SUCCESS] Email sent via SMTP to {recipient_email}")
        return True
        
    except Exception as e:
        print(f"[ERROR] SMTP send failed: {e}")
        return False

def send_email_outlook(recipient_email, subject, html_body):
    """
    Send email via Outlook - Works only on local Windows with Outlook installed
    """
    try:
        import win32com.client as win32
        import pythoncom
        
        pythoncom.CoInitialize()
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        
        mail.To = recipient_email
        mail.Subject = subject
        mail.HTMLBody = html_body
        mail.Send()
        
        pythoncom.CoUninitialize()
        print(f"[SUCCESS] Email sent via Outlook to {recipient_email}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Outlook send failed: {e}")
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except:
            pass
        return False

def send_questionnaire_email(recipient_email, asset_name, questionnaire, questionnaire_type, risk_id=None, agent_results=None):
    """
    Send questionnaire via email with web form link
    Auto-detects best method: SMTP (cloud/local) or Outlook (local only)
    
    Args:
        recipient_email: Email address of recipient
        asset_name: Name of asset
        questionnaire: Full questionnaire dict structure
        questionnaire_type: 'Agent0', 'ACCEPT', 'TRANSFER', 'TERMINATE', 'FOLLOWUP_*'
        risk_id: Risk ID (for follow-ups)
        agent_results: Dict with Agent 1-3 results (for Agent 4 workflows)
    
    Returns:
        dict: {'success': True/False, 'token': token or 'error': error_msg}
    """
    
    # Generate unique token
    token = str(uuid.uuid4())
    
    # Get base URL from environment (supports localhost, ngrok, or cloud)
    base_url = os.getenv('APP_BASE_URL', 'http://localhost:8501')
    form_url = f"{base_url}/?page=form&token={token}"
    
    # Prepare email content
    subject = f"Risk Assessment Questionnaire - {asset_name}"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #0066cc;">🔒 Risk Assessment Questionnaire</h2>
        <p><strong>Asset:</strong> {asset_name}</p>
        <p><strong>Type:</strong> {questionnaire_type}</p>
        <p>Please click the link below to fill the questionnaire:</p>
        <p>
            <a href="{form_url}" 
               style="background-color: #0066cc; color: white; padding: 10px 20px; 
                      text-decoration: none; border-radius: 5px; display: inline-block;">
                Fill Questionnaire
            </a>
        </p>
        <p style="color: #666; font-size: 12px;">
            This link is valid for 7 days.<br>
            Token: {token}
        </p>
    </body>
    </html>
    """
    
    # Try SMTP first (works on cloud and local)
    email_sent = send_email_smtp(recipient_email, subject, html_body)
    
    # If SMTP fails, try Outlook (local only)
    if not email_sent:
        print("[WARNING] SMTP failed, trying Outlook...")
        email_sent = send_email_outlook(recipient_email, subject, html_body)
    
    # If email sent successfully, save to database
    if email_sent:
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            
            # Store full questionnaire structure
            questions_json = json.dumps(questionnaire)
            
            # Store agent results if provided
            agent_results_json = json.dumps(agent_results) if agent_results else None
            
            cursor.execute("""
                INSERT INTO pending_questionnaires 
                (token, asset_name, questionnaire_type, questions, recipient_email, status, created_date, agent_results, risk_id)
                VALUES (?, ?, ?, ?, ?, 'Pending', ?, ?, ?)
            """, (token, asset_name, questionnaire_type, questions_json, 
                  recipient_email, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), agent_results_json, risk_id))
            
            conn.commit()
            conn.close()
            
            return {'success': True, 'token': token}
            
        except Exception as e:
            error_msg = f"Email sent but database save failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {'success': False, 'error': error_msg}
    else:
        error_msg = "Failed to send email via both SMTP and Outlook"
        print(f"[ERROR] {error_msg}")
        return {'success': False, 'error': error_msg}

def check_questionnaire_status(token):
    """Check if questionnaire has been completed"""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT status, answers, completed_date
        FROM pending_questionnaires
        WHERE token = ?
    """, (token,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'status': result[0],
            'answers': json.loads(result[1]) if result[1] else None,
            'completed_date': result[2]
        }
    return None

def get_all_pending_questionnaires():
    """Get all pending questionnaires"""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT token, asset_name, questionnaire_type, recipient_email, created_date, status
        FROM pending_questionnaires
        ORDER BY created_date DESC
    """)
    
    results = cursor.fetchall()
    conn.close()
    
    return [
        {
            'token': r[0],
            'asset_name': r[1],
            'questionnaire_type': r[2],
            'recipient_email': r[3],
            'created_date': r[4],
            'status': r[5]
        }
        for r in results
    ]
