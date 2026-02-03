"""
Memory-Aware RAG Tool Wrapper
Checks memory cache before performing RAG searches to speed up assessments
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase2_risk_resolver.database.memory_cache import (
    get_methodology_cache,
    save_methodology_cache,
    get_rag_cache,
    save_rag_cache
)
from phase2_risk_resolver.tools.rag_tool import search_knowledge_base_function


def search_with_memory(query: str) -> str:
    """
    Memory-aware RAG search
    
    1. Check rag_cache first
    2. If found, return cached result (FAST)
    3. If not found, do RAG search and cache result
    
    Args:
        query: RAG query text
    
    Returns:
        Search result (from cache or fresh RAG)
    """
    # Check cache first
    cached_result = get_rag_cache(query)
    
    if cached_result:
        print(f"⚡ CACHE HIT: Using cached result for query")
        return cached_result
    
    # Cache miss - do RAG search
    print(f"🔍 CACHE MISS: Performing RAG search...")
    result = search_knowledge_base_function(query)
    
    # Save to cache for next time
    save_rag_cache(query, result)
    print(f"💾 Cached result for future use")
    
    return result


def get_methodology(cache_key: str, rag_query: str = None) -> any:
    """
    Get methodology from cache or RAG
    
    1. Check methodology_cache first
    2. If found, return cached value (FAST)
    3. If not found and rag_query provided, do RAG search and cache
    
    Args:
        cache_key: Key to lookup in methodology_cache
        rag_query: Optional RAG query if cache miss
    
    Returns:
        Methodology value (from cache or fresh RAG)
    """
    # Check cache first
    cached_value = get_methodology_cache(cache_key)
    
    if cached_value:
        print(f"⚡ METHODOLOGY CACHE HIT: {cache_key}")
        return cached_value
    
    # Cache miss
    if rag_query:
        print(f"🔍 METHODOLOGY CACHE MISS: {cache_key}")
        print(f"   Performing RAG search...")
        result = search_knowledge_base_function(rag_query)
        
        # Save to cache
        save_methodology_cache(cache_key, result)
        print(f"💾 Cached methodology: {cache_key}")
        
        return result
    
    return None


# Convenience functions for common methodology lookups

def get_cia_methodology():
    """Get CIA methodology from cache or RAG"""
    return get_methodology(
        'cia_methodology',
        'What impact assessment methodology is used? CIA? DREAD? Custom?'
    )


def get_cia_rating_scale():
    """Get CIA rating scale from cache or RAG"""
    return get_methodology(
        'cia_rating_scale',
        'What rating scale is used for CIA impact ratings? What are the levels?'
    )


def get_risk_calculation():
    """Get risk calculation formula from cache or RAG"""
    return get_methodology(
        'risk_calculation',
        'What is the risk calculation formula? How is risk value calculated?'
    )


def get_probability_scale():
    """Get probability/likelihood scale from cache or RAG"""
    return get_methodology(
        'probability_scale',
        'What is the probability or likelihood scale? What are the levels?'
    )


def get_impact_scale():
    """Get impact scale from cache or RAG"""
    return get_methodology(
        'impact_scale',
        'What is the impact scale? What are the impact levels?'
    )


def get_control_framework():
    """Get control framework from cache or RAG"""
    return get_methodology(
        'control_framework',
        'What control framework is used? ISO 27001? NIST? COBIT?'
    )


def get_control_effectiveness_scale():
    """Get control effectiveness scale from cache or RAG"""
    return get_methodology(
        'control_effectiveness_scale',
        'What is the control effectiveness rating scale? What are the levels?'
    )


def get_control_rating_method():
    """Get control rating calculation method from cache or RAG"""
    return get_methodology(
        'control_rating_method',
        'How is the overall control rating calculated? What is the formula?'
    )


# ============================================================================
# Agent 0 (Questionnaire) Methodology Functions
# ============================================================================

def get_asset_identification_structure():
    """Get asset identification structure from cache or RAG"""
    return get_methodology(
        'asset_identification_structure',
        'What fields are used to identify assets? Asset name, asset type, asset ID, owner, location?'
    )


def get_asset_type_categories():
    """Get asset type categories from cache or RAG"""
    return get_methodology(
        'asset_type_categories',
        'What are the asset type categories? Physical, Software, Information, Service, People?'
    )


def get_overall_impact_scale():
    """Get overall impact rating scale from cache or RAG"""
    return get_methodology(
        'overall_impact_scale',
        'What is the overall impact rating scale for questionnaires? What are the levels?'
    )


def get_overall_probability_scale():
    """Get overall probability/likelihood scale from cache or RAG"""
    return get_methodology(
        'overall_probability_scale',
        'What is the overall probability or likelihood scale for questionnaires? What are the levels?'
    )


def get_business_criticality_scale():
    """Get business criticality scale from cache or RAG"""
    return get_methodology(
        'business_criticality_scale',
        'What is the business criticality scale? Low, Medium, High, Critical?'
    )


def get_data_classification_scale():
    """Get data classification scale from cache or RAG"""
    return get_methodology(
        'data_classification_scale',
        'What is the data classification scale? Public, Internal, Confidential, Restricted?'
    )


# Print cache stats on import (for debugging)
if __name__ != "__main__":
    from phase2_risk_resolver.database.memory_cache import get_cache_stats
    try:
        stats = get_cache_stats()
        if stats:
            total_entries = (stats['methodology_cache']['entries'] + 
                           stats['questionnaire_templates']['entries'] + 
                           stats['rag_cache']['entries'])
            if total_entries > 0:
                print(f"⚡ Memory System Active: {total_entries} cached entries")
    except:
        pass
