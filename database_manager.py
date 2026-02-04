"""
Database Manager - Handles both Local SQLite and Turso Cloud Database
Automatically switches between local and cloud based on USE_TURSO environment variable
"""

import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

USE_TURSO = os.getenv('USE_TURSO', 'false').lower() == 'true'

def get_database_connection():
    """
    Get database connection - automatically uses Turso if USE_TURSO=true, otherwise local SQLite
    """
    if USE_TURSO:
        try:
            import libsql_client
            url = os.getenv('TURSO_DATABASE_URL')
            auth_token = os.getenv('TURSO_AUTH_TOKEN')
            
            if not url or not auth_token:
                print("⚠️ Turso credentials not found, falling back to local SQLite")
                return sqlite3.connect('database/risk_register.db')
            
            # Convert libsql:// to https:// for HTTP protocol (more stable than WebSocket)
            if url.startswith('libsql://'):
                url = url.replace('libsql://', 'https://')
            
            client = libsql_client.create_client_sync(
                url=url,
                auth_token=auth_token
            )
            return TursoConnection(client)
        except ImportError:
            print("⚠️ libsql_client not installed, falling back to local SQLite")
            return sqlite3.connect('database/risk_register.db')
        except Exception as e:
            print(f"⚠️ Turso connection failed: {e}, falling back to local SQLite")
            return sqlite3.connect('database/risk_register.db')
    else:
        return sqlite3.connect('database/risk_register.db')


class TursoConnection:
    """Wrapper to make Turso client compatible with sqlite3 interface"""
    
    def __init__(self, client):
        self.client = client
        self._in_transaction = False
    
    def cursor(self):
        return TursoCursor(self.client)
    
    def commit(self):
        pass  # Turso auto-commits
    
    def close(self):
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TursoCursor:
    """Cursor wrapper for Turso client"""
    
    def __init__(self, client):
        self.client = client
        self._results = None
        self._rowcount = 0
    
    def execute(self, query, params=None):
        try:
            if params:
                result = self.client.execute(query, params)
            else:
                result = self.client.execute(query)
            
            self._results = result.rows if hasattr(result, 'rows') else []
            self._rowcount = len(self._results) if self._results else 0
            return self
        except Exception as e:
            print(f"❌ Turso execute error: {e}")
            raise
    
    def executemany(self, query, params_list):
        for params in params_list:
            self.execute(query, params)
        return self
    
    def fetchone(self):
        if self._results and len(self._results) > 0:
            return tuple(self._results[0])
        return None
    
    def fetchall(self):
        if self._results:
            return [tuple(row) for row in self._results]
        return []
    
    def fetchmany(self, size=1):
        if self._results:
            result = [tuple(row) for row in self._results[:size]]
            self._results = self._results[size:]
            return result
        return []
    
    @property
    def rowcount(self):
        return self._rowcount
    
    def close(self):
        self._results = None


def test_connection():
    """Test database connection"""
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        conn.close()
        
        db_type = "Turso Cloud" if USE_TURSO else "Local SQLite"
        print(f"✅ Database connection successful ({db_type})")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing database connection...")
    test_connection()
