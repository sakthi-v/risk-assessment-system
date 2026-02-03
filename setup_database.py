"""
Simple Database Initialization Script
Place this file in project root and run: python setup_database.py
"""

import sqlite3
import os

# Database path
db_path = os.path.join('database', 'risk_register.db')

print("="*80)
print("SETTING UP RISK REGISTER DATABASE")
print("="*80)
print(f"Database: {db_path}\n")

# Create database directory if doesn't exist
os.makedirs('database', exist_ok=True)

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create risks table
print("Creating 'risks' table...")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS risks (
        -- IDENTIFICATION
        risk_id TEXT PRIMARY KEY,
        risk_number INTEGER,
        
        -- RISK DETAILS
        risk_title TEXT NOT NULL,
        risk_description TEXT NOT NULL,
        threat_name TEXT,
        vulnerabilities TEXT,
        
        -- ASSET INFORMATION
        asset_id TEXT,
        asset_name TEXT,
        asset_type TEXT,
        asset_owner TEXT,
        asset_business_value TEXT,
        asset_criticality TEXT,
        
        -- RISK ASSESSMENT (FROM AGENTS 1-2)
        impact_level INTEGER,
        impact_category TEXT,
        probability_level INTEGER,
        probability_category TEXT,
        risk_value INTEGER,
        risk_rating INTEGER,
        risk_evaluation_level TEXT,
        risk_classification TEXT,
        
        -- CIA IMPACT (FROM AGENT 1)
        confidentiality_impact TEXT,
        confidentiality_rating INTEGER,
        integrity_impact TEXT,
        integrity_rating INTEGER,
        availability_impact TEXT,
        availability_rating INTEGER,
        overall_impact_rating INTEGER,
        
        -- CONTROLS & RESIDUAL RISK (FROM AGENT 3)
        controls_in_place TEXT,
        total_controls_count INTEGER,
        preventive_avg REAL,
        detective_avg REAL,
        corrective_avg REAL,
        control_rating REAL,
        control_effectiveness TEXT,
        residual_risk_value REAL,
        residual_risk_classification TEXT,
        control_gaps TEXT,
        recommended_controls TEXT,
        
        -- RISK CATEGORIZATION
        risk_category TEXT,
        risk_trigger TEXT,
        
        -- OWNERSHIP & MANAGEMENT
        risk_owner TEXT,
        risk_owner_email TEXT,
        risk_approver TEXT,
        
        -- TREATMENT (FROM AGENT 4)
        management_decision TEXT,
        mitigation_plan TEXT,
        treatment_actions TEXT,
        treatment_priority TEXT,
        
        -- STATUS & TIMELINE
        status TEXT DEFAULT 'Open',
        date_identified TEXT,
        date_added TEXT DEFAULT (datetime('now')),
        target_closure_date TEXT,
        date_closed TEXT,
        last_updated TEXT DEFAULT (datetime('now')),
        
        -- ADDITIONAL INFO
        comments TEXT,
        acceptance_reason TEXT,
        
        -- SOURCE TRACKING
        assessment_id TEXT,
        created_by TEXT,
        questionnaire_used INTEGER DEFAULT 0,
        
        -- AUDIT TRAIL
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        
        -- WORKFLOW FORMS (AGENT 4 WORKFLOWS)
        treatment_decision TEXT,
        acceptance_form TEXT,
        acceptance_questionnaire_answers TEXT,
        transfer_form TEXT,
        transfer_questionnaire_answers TEXT,
        terminate_form TEXT,
        terminate_questionnaire_answers TEXT,
        
        -- FOLLOW-UP TRACKING
        followup_status TEXT,
        followup_date TEXT,
        followup_answers TEXT,
        action_owner TEXT
    )
""")

print("Table created!\n")

# Create indexes
print("Creating indexes...")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_rating ON risks(risk_rating)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON risks(status)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_owner ON risks(risk_owner)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_date_identified ON risks(date_identified)")
print("Indexes created!\n")

# Create trigger for auto-update
print("Creating triggers...")
cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS update_timestamp 
    AFTER UPDATE ON risks
    BEGIN
        UPDATE risks 
        SET updated_at = datetime('now')
        WHERE risk_id = NEW.risk_id;
    END
""")
print("Triggers created!\n")

# Commit
conn.commit()

# Verify
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='risks'")
if cursor.fetchone():
    print("SUCCESS! 'risks' table exists in database")
    
    # Count rows
    cursor.execute("SELECT COUNT(*) FROM risks")
    count = cursor.fetchone()[0]
    print(f"Current rows in table: {count}\n")
else:
    print("ERROR: Table not created!\n")

conn.close()

print("="*80)
print("SETUP COMPLETE!")
print("="*80)
print("\nYou can now save risks to the Risk Register!\n")