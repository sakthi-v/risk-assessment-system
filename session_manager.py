"""
Session Manager - Auto-save and restore agent results
Saves progress to DATABASE (not files) for cloud persistence
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import streamlit as st
from database_manager import get_database_connection

# Session storage directory (for backward compatibility with local files)
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

class SessionManager:
    """Manages saving and loading of agent execution sessions"""
    
    def _ensure_sessions_table(self):
        """Ensure sessions table exists in database"""
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_name TEXT UNIQUE NOT NULL,
                    session_data TEXT NOT NULL,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error creating sessions table: {e}")
    
    def __init__(self):
        self.sessions_dir = SESSIONS_DIR
        self.current_session_file = None
        self._ensure_sessions_table()
    
    def create_session_id(self, asset_name: str) -> str:
        """Create a unique session ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_asset_name = "".join(c for c in asset_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_asset_name = safe_asset_name.replace(' ', '_')[:30]
        return f"session_{safe_asset_name}_{timestamp}"
    
    def save_session(self, 
                    asset_data: Dict[str, Any],
                    agent_1_result: Optional[Dict] = None,
                    agent_2_result: Optional[Dict] = None,
                    agent_3_result: Optional[Dict] = None,
                    agent_4_result: Optional[Dict] = None) -> str:
        """
        Save current session to DATABASE (not file)
        Returns the session name
        """
        # Create session ID
        session_id = self.create_session_id(asset_data.get('asset_name', 'unknown'))
        
        # Prepare session data
        session_data = {
            'session_id': session_id,
            'asset_data': asset_data,
            'agent_1_result': agent_1_result,
            'agent_2_result': agent_2_result,
            'agent_3_result': agent_3_result,
            'agent_4_result': agent_4_result,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'progress': {
                'agent_1': 'complete' if agent_1_result else 'pending',
                'agent_2': 'complete' if agent_2_result else 'pending',
                'agent_3': 'complete' if agent_3_result else 'pending',
                'agent_4': 'complete' if agent_4_result else 'pending',
            }
        }
        
        # Save to DATABASE
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            
            # Insert or replace session
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (session_name, session_data, updated_date)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (session_id, json.dumps(session_data, ensure_ascii=False)))
            
            conn.commit()
            conn.close()
            
            self.current_session_file = session_id
            return session_id
        except Exception as e:
            print(f"Error saving session to database: {e}")
            return None
    
    def load_session(self, session_name: str) -> Dict[str, Any]:
        """Load session from DATABASE"""
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT session_data FROM sessions WHERE session_name = ?", (session_name,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return json.loads(result[0])
            return None
        except Exception as e:
            print(f"Error loading session: {e}")
            return None
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get list of recent sessions from DATABASE"""
        sessions = []
        
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_name, session_data, updated_date
                FROM sessions
                ORDER BY updated_date DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                try:
                    session_name, session_data_json, updated_date = row
                    session_data = json.loads(session_data_json)
                    
                    sessions.append({
                        'file': session_name,  # For compatibility
                        'session_id': session_data.get('session_id'),
                        'asset_name': session_data.get('asset_data', {}).get('asset_name', 'Unknown'),
                        'last_updated': session_data.get('last_updated'),
                        'progress': session_data.get('progress', {}),
                        'data': session_data
                    })
                except Exception as e:
                    print(f"Error parsing session {session_name}: {e}")
                    continue
        except Exception as e:
            print(f"Error getting recent sessions: {e}")
        
        return sessions
    
    def delete_session(self, session_name: str):
        """Delete a session from DATABASE"""
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE session_name = ?", (session_name,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error deleting session: {e}")
    
    def restore_to_session_state(self, session_data: Dict[str, Any]):
        """Restore session data to Streamlit session state"""
        # Restore asset data
        if 'asset_data' in session_data:
            st.session_state.sample_assets = [session_data['asset_data']]
            st.session_state.selected_asset = session_data['asset_data']
        
        # Restore agent results
        if session_data.get('agent_1_result'):
            st.session_state.impact_result = session_data['agent_1_result']
        
        if session_data.get('agent_2_result'):
            st.session_state.risk_result = session_data['agent_2_result']
        
        if session_data.get('agent_3_result'):
            st.session_state.control_result = session_data['agent_3_result']
        
        if session_data.get('agent_4_result'):
            st.session_state.decision_result = session_data['agent_4_result']
        
        # Mark session as restored
        st.session_state.session_restored = True
        st.session_state.restored_session_id = session_data.get('session_id')


# Global instance
_session_manager = None

def get_session_manager() -> SessionManager:
    """Get or create the global session manager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def auto_save_session():
    """
    Auto-save current session state
    Call this after each agent completes
    """
    manager = get_session_manager()
    
    # Check if we have an asset selected
    if not st.session_state.get('sample_assets'):
        return None
    
    asset_data = st.session_state.sample_assets[0] if st.session_state.sample_assets else None
    if not asset_data:
        return None
    
    # Save session
    session_file = manager.save_session(
        asset_data=asset_data,
        agent_1_result=st.session_state.get('impact_result'),
        agent_2_result=st.session_state.get('risk_result'),
        agent_3_result=st.session_state.get('control_result'),
        agent_4_result=st.session_state.get('decision_result')
    )
    
    return session_file


def show_session_restore_ui():
    """
    Show UI for restoring previous sessions
    Call this at the top of Risk Assessment page
    """
    manager = get_session_manager()
    recent_sessions = manager.get_recent_sessions(limit=5)
    
    # DEBUG: Always show count
    if recent_sessions:
        st.info(f"🔍 DEBUG: Found {len(recent_sessions)} saved sessions")
    else:
        st.info("🔍 DEBUG: No saved sessions found")
        return False
    
    # Check if already restored in this session
    if st.session_state.get('session_restored'):
        # Show which session is currently loaded
        if st.session_state.get('restored_session_id'):
            st.success(f"✅ **Session Active**: {st.session_state.get('restored_session_id')}")
        return True
    
    # Show restore UI - ALWAYS EXPANDED AND PROMINENT
    st.warning("⚠️ **PREVIOUS SESSIONS FOUND!** Your work from yesterday is saved. Resume below or start fresh.")
    
    with st.expander("📂 📂 📂 RESUME PREVIOUS SESSION (Click Here)", expanded=True):
        for idx, session in enumerate(recent_sessions):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"**{session['asset_name']}**")
                st.caption(f"Last updated: {session['last_updated']}")
            
            with col2:
                progress = session['progress']
                completed = sum(1 for status in progress.values() if status == 'complete')
                st.metric("Progress", f"{completed}/4 agents")
                
                # Show which agents are complete
                status_text = " ".join([
                    "✅" if progress.get(f'agent_{i}') == 'complete' else "⏳"
                    for i in range(1, 5)
                ])
                st.caption(status_text)
            
            with col3:
                if st.button("📂 Resume", key=f"resume_{idx}", use_container_width=True):
                    manager.restore_to_session_state(session['data'])
                    st.success(f"✅ Restored session: {session['asset_name']}")
                    st.rerun()
                
                if st.button("🗑️", key=f"delete_{idx}", help="Delete this session"):
                    manager.delete_session(session['file'])
                    st.success("🗑️ Session deleted")
                    st.rerun()
            
            st.markdown("---")
        
        if st.button("🆕 Start Fresh (Ignore Previous Sessions)", type="secondary", use_container_width=True):
            st.session_state.session_restored = True  # Mark as handled
            st.rerun()
    
    return False
