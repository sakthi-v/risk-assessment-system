-- ============================================================================
-- RISK REGISTER DATABASE SCHEMA (SQLite)
-- ============================================================================

DROP TABLE IF EXISTS risks;

CREATE TABLE risks (
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
);

-- INDEXES
CREATE INDEX idx_risk_rating ON risks(risk_rating);
CREATE INDEX idx_status ON risks(status);
CREATE INDEX idx_risk_owner ON risks(risk_owner);
CREATE INDEX idx_date_identified ON risks(date_identified);

-- TRIGGER FOR AUTO-UPDATE
CREATE TRIGGER update_timestamp 
AFTER UPDATE ON risks
BEGIN
    UPDATE risks 
    SET updated_at = datetime('now')
    WHERE risk_id = NEW.risk_id;
END;

-- ============================================================================
-- PENDING QUESTIONNAIRES TABLE (EMAIL WORKFLOW)
-- ============================================================================

DROP TABLE IF EXISTS pending_questionnaires;

CREATE TABLE pending_questionnaires (
    token TEXT PRIMARY KEY,
    asset_name TEXT,
    questionnaire_type TEXT,
    questions TEXT,
    answers TEXT,
    recipient_email TEXT,
    status TEXT,
    created_date TEXT,
    completed_date TEXT
);

CREATE INDEX idx_questionnaire_status ON pending_questionnaires(status);
CREATE INDEX idx_questionnaire_token ON pending_questionnaires(token);

-- ============================================================================
-- PENDING QUESTIONNAIRES TABLE (EMAIL WORKFLOW)
-- ============================================================================

DROP TABLE IF EXISTS pending_questionnaires;

CREATE TABLE pending_questionnaires (
    token TEXT PRIMARY KEY,
    asset_name TEXT,
    questionnaire_type TEXT,
    questions TEXT,
    answers TEXT,
    recipient_email TEXT,
    status TEXT,
    created_date TEXT,
    completed_date TEXT
);

CREATE INDEX idx_questionnaire_status ON pending_questionnaires(status);
CREATE INDEX idx_questionnaire_token ON pending_questionnaires(token);