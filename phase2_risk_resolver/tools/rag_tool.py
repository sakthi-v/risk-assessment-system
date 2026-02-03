"""
RAG Tool - Connects CrewAI agents to Phase 1 RAG Knowledge Base
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pickle
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import google.generativeai as genai


class RAGKnowledgeBase:
    """Interface to Phase 1 RAG Knowledge Base"""
    
    def __init__(self, api_key: str, knowledge_base_dir: Path):
        self.knowledge_base_dir = knowledge_base_dir
        self.api_key = api_key
        self._load_knowledge_base()
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-3-flash-preview')
    
    def _load_knowledge_base(self):
        """Load vectorizer and documents from Phase 1"""
        try:
            # Load documents
            with open(self.knowledge_base_dir / "documents.pkl", 'rb') as f:
                self.documents = pickle.load(f)
            
            # Load vectorizer
            with open(self.knowledge_base_dir / "vectorizer.pkl", 'rb') as f:
                self.vectorizer = pickle.load(f)
            
            # Load document vectors
            with open(self.knowledge_base_dir / "document_vectors.pkl", 'rb') as f:
                self.document_vectors = pickle.load(f)
            
            self.document_texts = [doc['text'] for doc in self.documents]
            self.document_names = [doc['filename'] for doc in self.documents]
            
            print(f"RAG Knowledge Base loaded: {len(self.documents)} documents")
            
        except Exception as e:
            print(f"Error loading knowledge base: {str(e)}")
            raise
    
    def search(self, query: str, top_k: int = 5) -> str:
        """Search knowledge base and return relevant information"""
        try:
            # Vectorize query
            query_vector = self.vectorizer.transform([query])
            
            # Calculate similarities
            similarities = cosine_similarity(query_vector, self.document_vectors).flatten()
            
            # Get top k results
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            
            # Gather context from relevant documents
            context = ""
            for idx in top_indices:
                if similarities[idx] > 0.03:  # Minimum similarity threshold
                    context += f"\n{'='*80}\n"
                    context += f"Document: {self.document_names[idx]}\n"
                    context += f"Relevance: {similarities[idx]:.2%}\n"
                    context += f"{'='*80}\n"
                    # Limit context per document
                    context += self.document_texts[idx][:50000] + "\n"
            
            if not context:
                return "No relevant information found in knowledge base."
            
            # Use Gemini to generate focused answer
            prompt = f"""You are a Risk Management expert. Based ONLY on the following documents from 
the organization's knowledge base, answer this query with maximum detail and accuracy.

QUERY: {query}

CONTEXT FROM KNOWLEDGE BASE:
{context}

INSTRUCTIONS:
1. Extract the EXACT information requested from the documents
2. Include specific criteria, definitions, tables, formulas if present
3. Cite the document name and section where you found the information
4. If the information is in a table, reproduce the table structure
5. Be comprehensive - include all relevant details
6. If information is not found, clearly state that

ANSWER:"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            return f"Error searching knowledge base: {str(e)}"


# Global RAG instance and current API key
_rag_instance = None
_current_api_key = None
_knowledge_base_dir = None


def initialize_rag(api_key: str, knowledge_base_dir: Path):
    """Initialize the RAG system - call this once at startup"""
    global _rag_instance, _current_api_key, _knowledge_base_dir
    _current_api_key = api_key
    _knowledge_base_dir = knowledge_base_dir
    _rag_instance = RAGKnowledgeBase(api_key, knowledge_base_dir)


def update_rag_api_key(new_api_key: str):
    """Update RAG API key when rotation happens"""
    global _rag_instance, _current_api_key
    if _rag_instance is not None and new_api_key != _current_api_key:
        _current_api_key = new_api_key
        # Re-configure Gemini with new key
        genai.configure(api_key=new_api_key)
        _rag_instance.api_key = new_api_key
        _rag_instance.model = genai.GenerativeModel('gemini-3-flash-preview')
        print(f"✅ RAG API key updated")


def search_knowledge_base_function(query: str, use_cache: bool = True) -> str:
    """
    Function wrapper for RAG search - used by CrewAI tool
    Auto-reinitializes if needed, uses cache by default
    
    Args:
        query: RAG query text
        use_cache: If True, use cache. If False, force fresh query (for questionnaires)
    """
    global _rag_instance, _current_api_key, _knowledge_base_dir
    
    # ✅ Check cache first (unless disabled)
    if use_cache:
        try:
            from ..database.memory_cache import get_rag_cache, save_rag_cache
            cached_result = get_rag_cache(query)
            if cached_result:
                print("🔍 CACHE HIT: Using cached result")
                return cached_result
            else:
                print("🔍 CACHE MISS: Performing RAG search...")
        except Exception as e:
            print(f"Warning: Cache check failed: {str(e)}")
    else:
        print("🔍 Performing FRESH RAG search (cache disabled for questionnaire)...")
    
    if _rag_instance is None:
        # Try to get current API key and initialize
        try:
            from api_key_manager import get_active_api_key
            current_key = get_active_api_key()
            
            # If knowledge_base_dir not set, try default location
            if _knowledge_base_dir is None:
                _knowledge_base_dir = Path("knowledge_base")
            
            if current_key:
                print(f"Auto-initializing RAG with knowledge base at: {_knowledge_base_dir}")
                initialize_rag(current_key, _knowledge_base_dir)
            else:
                return "ERROR: No API key available. RAG Knowledge Base cannot be initialized."
        except Exception as e:
            return f"ERROR: RAG initialization failed: {str(e)}. Call initialize_rag() first."
    
    # Check if API key needs updating
    try:
        from api_key_manager import get_active_api_key
        current_key = get_active_api_key()
        if current_key and current_key != _current_api_key:
            print(f"Updating RAG API key...")
            update_rag_api_key(current_key)
    except Exception as e:
        print(f"Warning: Could not update RAG API key: {str(e)}")
        pass  # Continue with existing key
    
    # Perform RAG search
    result = _rag_instance.search(query, top_k=5)
    
    # ✅ Save to cache (unless disabled)
    if use_cache:
        try:
            from ..database.memory_cache import save_rag_cache
            save_rag_cache(query, result)
            print("💾 Cached result for future use")
        except Exception as e:
            print(f"Warning: Cache save failed: {str(e)}")
    else:
        print("✅ Fresh RAG result returned (not cached)")
    
    return result