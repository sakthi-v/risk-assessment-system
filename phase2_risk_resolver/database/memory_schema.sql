-- ============================================================================
-- MEMORY SYSTEM SCHEMA - Speed Optimization Tables
-- ============================================================================
-- Purpose: Cache methodology, questionnaires, and RAG results to reduce
--          assessment time from 60 min to 18-22 min (65-70% faster)
-- ============================================================================

-- ============================================================================
-- TABLE 1: methodology_cache
-- ============================================================================
-- Stores: CIA scales, risk formulas, control frameworks discovered by agents
-- Source: Extracted from agent_1_raw, agent_2_raw, agent_3_raw
-- ============================================================================

DROP TABLE IF EXISTS methodology_cache;

CREATE TABLE methodology_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT UNIQUE NOT NULL,
    cache_value TEXT NOT NULL,
    created_date TEXT DEFAULT (datetime('now')),
    last_used TEXT DEFAULT (datetime('now')),
    usage_count INTEGER DEFAULT 0
);

CREATE INDEX idx_methodology_key ON methodology_cache(cache_key);

-- ============================================================================
-- TABLE 2: questionnaire_templates
-- ============================================================================
-- Stores: Asset questionnaires, decision forms, follow-up templates
-- Source: Extracted from acceptance_form, transfer_form, terminate_form, followup_answers
-- ============================================================================

DROP TABLE IF EXISTS questionnaire_templates;

CREATE TABLE questionnaire_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_type TEXT NOT NULL,
    template_key TEXT NOT NULL,
    template_json TEXT NOT NULL,
    created_date TEXT DEFAULT (datetime('now')),
    last_used TEXT DEFAULT (datetime('now')),
    usage_count INTEGER DEFAULT 0,
    UNIQUE(template_type, template_key)
);

CREATE INDEX idx_template_type_key ON questionnaire_templates(template_type, template_key);

-- ============================================================================
-- TABLE 3: rag_cache
-- ============================================================================
-- Stores: RAG search results for common queries
-- Source: Built naturally as agents perform RAG searches
-- ============================================================================

DROP TABLE IF EXISTS rag_cache;

CREATE TABLE rag_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_hash TEXT UNIQUE NOT NULL,
    query_text TEXT NOT NULL,
    cached_result TEXT NOT NULL,
    created_date TEXT DEFAULT (datetime('now')),
    last_used TEXT DEFAULT (datetime('now')),
    hit_count INTEGER DEFAULT 0
);

CREATE INDEX idx_query_hash ON rag_cache(query_hash);

-- ============================================================================
-- TRIGGERS FOR AUTO-UPDATE last_used
-- ============================================================================

CREATE TRIGGER update_methodology_last_used 
AFTER UPDATE OF usage_count ON methodology_cache
BEGIN
    UPDATE methodology_cache 
    SET last_used = datetime('now')
    WHERE id = NEW.id;
END;

CREATE TRIGGER update_template_last_used 
AFTER UPDATE OF usage_count ON questionnaire_templates
BEGIN
    UPDATE questionnaire_templates 
    SET last_used = datetime('now')
    WHERE id = NEW.id;
END;

CREATE TRIGGER update_rag_last_used 
AFTER UPDATE OF hit_count ON rag_cache
BEGIN
    UPDATE rag_cache 
    SET last_used = datetime('now')
    WHERE id = NEW.id;
END;
