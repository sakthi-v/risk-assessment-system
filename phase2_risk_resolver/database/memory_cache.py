"""
Memory Cache Helper Functions
Provides functions to check, save, and retrieve cached data from memory tables
"""
import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "../../database/risk_register.db"

# ============================================================================
# TABLE 1: methodology_cache Functions
# ============================================================================

def get_methodology_cache(cache_key):
    """
    Get cached methodology data
    
    Args:
        cache_key: Key to lookup (e.g., 'cia_rating_scale', 'risk_formula')
    
    Returns:
        Cached value (parsed JSON) or None if not found
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT cache_value FROM methodology_cache 
            WHERE cache_key = ?
        """, (cache_key,))
        
        result = cursor.fetchone()
        
        if result:
            # Update usage count
            cursor.execute("""
                UPDATE methodology_cache 
                SET usage_count = usage_count + 1 
                WHERE cache_key = ?
            """, (cache_key,))
            conn.commit()
            
            conn.close()
            return json.loads(result[0])
        
        conn.close()
        return None
    except Exception as e:
        print(f"Error getting methodology cache: {e}")
        return None


def save_methodology_cache(cache_key, cache_value):
    """
    Save methodology data to cache
    
    Args:
        cache_key: Key to store under
        cache_value: Value to store (will be JSON serialized)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cache_value_json = json.dumps(cache_value, ensure_ascii=False)
        
        cursor.execute("""
            INSERT OR REPLACE INTO methodology_cache 
            (cache_key, cache_value, created_date, last_used, usage_count)
            VALUES (?, ?, datetime('now'), datetime('now'), 0)
        """, (cache_key, cache_value_json))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving methodology cache: {e}")
        return False


# ============================================================================
# TABLE 2: questionnaire_templates Functions
# ============================================================================

def get_questionnaire_template(template_type, template_key):
    """
    Get cached questionnaire template
    
    Args:
        template_type: Type of template ('ASSET', 'DECISION', 'FOLLOWUP')
        template_key: Key for template (e.g., 'Database Server', 'ACCEPT', 'TREAT_FOLLOWUP')
    
    Returns:
        Template (parsed JSON) or None if not found
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT template_json FROM questionnaire_templates 
            WHERE template_type = ? AND template_key = ?
        """, (template_type, template_key))
        
        result = cursor.fetchone()
        
        if result:
            # Update usage count
            cursor.execute("""
                UPDATE questionnaire_templates 
                SET usage_count = usage_count + 1 
                WHERE template_type = ? AND template_key = ?
            """, (template_type, template_key))
            conn.commit()
            
            conn.close()
            return json.loads(result[0])
        
        conn.close()
        return None
    except Exception as e:
        print(f"Error getting questionnaire template: {e}")
        return None


def save_questionnaire_template(template_type, template_key, template_json):
    """
    Save questionnaire template to cache
    
    Args:
        template_type: Type of template ('ASSET', 'DECISION', 'FOLLOWUP')
        template_key: Key for template
        template_json: Template data (will be JSON serialized)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        template_json_str = json.dumps(template_json, ensure_ascii=False)
        
        cursor.execute("""
            INSERT OR REPLACE INTO questionnaire_templates 
            (template_type, template_key, template_json, created_date, last_used, usage_count)
            VALUES (?, ?, ?, datetime('now'), datetime('now'), 0)
        """, (template_type, template_key, template_json_str))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving questionnaire template: {e}")
        return False


# ============================================================================
# TABLE 3: rag_cache Functions
# ============================================================================

def get_rag_cache(query_text):
    """
    Get cached RAG search result
    
    Args:
        query_text: RAG query text
    
    Returns:
        Cached result (parsed JSON) or None if not found
    """
    try:
        query_hash = hashlib.md5(query_text.encode()).hexdigest()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT cached_result FROM rag_cache 
            WHERE query_hash = ?
        """, (query_hash,))
        
        result = cursor.fetchone()
        
        if result:
            # Update hit count
            cursor.execute("""
                UPDATE rag_cache 
                SET hit_count = hit_count + 1 
                WHERE query_hash = ?
            """, (query_hash,))
            conn.commit()
            
            conn.close()
            return json.loads(result[0])
        
        conn.close()
        return None
    except Exception as e:
        print(f"Error getting RAG cache: {e}")
        return None


def save_rag_cache(query_text, cached_result):
    """
    Save RAG search result to cache
    
    Args:
        query_text: RAG query text
        cached_result: Result to cache (will be JSON serialized)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        query_hash = hashlib.md5(query_text.encode()).hexdigest()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cached_result_json = json.dumps(cached_result, ensure_ascii=False)
        
        cursor.execute("""
            INSERT OR REPLACE INTO rag_cache 
            (query_hash, query_text, cached_result, created_date, last_used, hit_count)
            VALUES (?, ?, ?, datetime('now'), datetime('now'), 0)
        """, (query_hash, query_text, cached_result_json))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving RAG cache: {e}")
        return False


# ============================================================================
# Utility Functions
# ============================================================================

def get_cache_stats():
    """
    Get statistics about cache usage
    
    Returns:
        Dictionary with cache statistics
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*), SUM(usage_count) FROM methodology_cache")
        methodology_stats = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*), SUM(usage_count) FROM questionnaire_templates")
        template_stats = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*), SUM(hit_count) FROM rag_cache")
        rag_stats = cursor.fetchone()
        
        conn.close()
        
        return {
            'methodology_cache': {
                'entries': methodology_stats[0] or 0,
                'total_hits': methodology_stats[1] or 0
            },
            'questionnaire_templates': {
                'entries': template_stats[0] or 0,
                'total_hits': template_stats[1] or 0
            },
            'rag_cache': {
                'entries': rag_stats[0] or 0,
                'total_hits': rag_stats[1] or 0
            }
        }
    except Exception as e:
        print(f"Error getting cache stats: {e}")
        return None
