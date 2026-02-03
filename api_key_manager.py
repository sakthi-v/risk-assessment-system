"""
API Key Manager with Automatic Rotation
Handles multiple Gemini API keys and rotates when quota is exceeded
"""
import os
from typing import List, Optional
from dotenv import load_dotenv
import streamlit as st

class APIKeyManager:
    """Manages multiple API keys with automatic rotation on quota exceeded"""
    
    def __init__(self):
        """Initialize API key manager"""
        load_dotenv()
        self.api_keys = self._load_api_keys()
        self.current_index = 0
        
        # Always ensure session state is initialized
        self._ensure_session_state()
    
    def _ensure_session_state(self):
        """Ensure session state variables are initialized"""
        if 'api_key_index' not in st.session_state:
            st.session_state.api_key_index = 0
        if 'failed_keys' not in st.session_state:
            st.session_state.failed_keys = set()
    
    def _load_api_keys(self) -> List[str]:
        """Load all API keys from environment"""
        keys = []
        for i in range(1, 12):  # Support up to 11 keys now
            key = os.getenv(f'GEMINI_API_KEY_{i}')
            if key:
                keys.append(key)
        
        if not keys:
            raise ValueError("No API keys found in .env file!")
        
        return keys
    
    def get_current_key(self) -> str:
        """Get the current active API key"""
        if not self.api_keys:
            raise ValueError("No API keys available!")
        
        # Ensure session state is initialized
        self._ensure_session_state()
        
        index = st.session_state.api_key_index
        return self.api_keys[index]
    
    def rotate_key(self, reason: str = "quota_exceeded") -> Optional[str]:
        """
        Rotate to the next available API key
        Returns the new key or None if all keys are exhausted
        """
        # Ensure session state is initialized
        self._ensure_session_state()
        
        current_key = self.get_current_key()
        st.session_state.failed_keys.add(current_key)
        
        # Try to find next available key
        for _ in range(len(self.api_keys)):
            st.session_state.api_key_index = (st.session_state.api_key_index + 1) % len(self.api_keys)
            next_key = self.get_current_key()
            
            if next_key not in st.session_state.failed_keys:
                st.success(f"🔄 Rotated to API Key #{st.session_state.api_key_index + 1} ({reason})")
                return next_key
        
        # All keys exhausted
        st.error("❌ All API keys have exceeded their quota. Please wait or add more keys.")
        return None
    
    def reset_failed_keys(self):
        """Reset the failed keys set (call this after quota reset period)"""
        st.session_state.failed_keys = set()
        st.session_state.api_key_index = 0
        st.success("✅ API key rotation reset. Starting fresh with Key #1")
    
    def get_status(self) -> dict:
        """Get current status of API keys"""
        # Ensure session state is initialized
        self._ensure_session_state()
        
        return {
            'total_keys': len(self.api_keys),
            'current_index': st.session_state.api_key_index + 1,
            'failed_count': len(st.session_state.failed_keys),
            'available_count': len(self.api_keys) - len(st.session_state.failed_keys)
        }
    
    def is_quota_error(self, error_message: str) -> bool:
        """Check if error is related to quota/rate limit"""
        quota_keywords = [
            'quota',
            'rate limit',
            'too many requests',
            '429',
            'resource exhausted',
            'RESOURCE_EXHAUSTED'
        ]
        error_lower = str(error_message).lower()
        return any(keyword in error_lower for keyword in quota_keywords)


# Global instance
_api_key_manager = None

def get_api_key_manager() -> APIKeyManager:
    """Get or create the global API key manager instance"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def get_active_api_key() -> str:
    """Get the currently active API key"""
    manager = get_api_key_manager()
    return manager.get_current_key()


def handle_api_error(error: Exception, operation: str = "API call") -> Optional[str]:
    """
    Handle API errors and rotate keys if needed
    Returns new API key if rotated, None if all keys exhausted
    """
    manager = get_api_key_manager()
    error_msg = str(error)
    
    if manager.is_quota_error(error_msg):
        st.warning(f"⚠️ API quota exceeded during {operation}. Rotating to next key...")
        return manager.rotate_key(reason="quota_exceeded")
    else:
        # Not a quota error, don't rotate
        st.error(f"❌ Error during {operation}: {error_msg}")
        return None
