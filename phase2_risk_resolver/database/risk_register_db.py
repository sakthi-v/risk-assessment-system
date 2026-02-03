"""
Risk Register Database Module
Handles all database operations for the risk register
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database_manager import get_database_connection


class RiskRegisterDB:
    """Database manager for Risk Register"""
    
    def __init__(self, db_path: str = "database/risk_register.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.ensure_database_exists()
    
    def ensure_database_exists(self):
        """Create database and tables if they don't exist"""
        # Create database directory if needed
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if database exists
        db_file = Path(self.db_path)
        if not db_file.exists():
            print(f"📊 Creating new risk register database at: {self.db_path}")
            self._create_database()
        else:
            print(f"✅ Risk register database found at: {self.db_path}")
    
    def _create_database(self):
        """Create database tables from schema"""
        schema_path = Path(__file__).parent / "schema.sql"
        
        if not schema_path.exists():
            print(f"⚠️ Schema file not found at: {schema_path}")
            return
        
        # Read schema
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Execute schema
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
        conn.close()
        
        print("✅ Database tables created successfully!")
    
    def _get_connection(self):
        """Get database connection"""
        return get_database_connection()
    
    def generate_risk_id(self) -> str:
        """Generate next risk ID (RSK-001, RSK-002, etc.)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get highest risk number
        cursor.execute("SELECT MAX(risk_number) FROM risks")
        result = cursor.fetchone()
        
        if result[0] is None:
            next_number = 1
        else:
            next_number = result[0] + 1
        
        conn.close()
        
        return f"RSK-{next_number:03d}"
    
    def add_risk(self, risk_data: Dict[str, Any]) -> str:
        """
        Add new risk to register
        
        Args:
            risk_data: Dictionary with risk information
            
        Returns:
            risk_id: Generated risk ID (e.g., RSK-001)
        """
        # Generate risk ID if not provided
        if 'risk_id' not in risk_data:
            risk_data['risk_id'] = self.generate_risk_id()
            risk_data['risk_number'] = int(risk_data['risk_id'].split('-')[1])
        
        # Convert JSON fields to strings
        json_fields = ['vulnerabilities', 'controls_in_place', 'control_gaps', 
                      'recommended_controls', 'treatment_actions']
        for field in json_fields:
            if field in risk_data and isinstance(risk_data[field], (list, dict)):
                risk_data[field] = json.dumps(risk_data[field])
        
        # Build INSERT query
        columns = ', '.join(risk_data.keys())
        placeholders = ', '.join(['?' for _ in risk_data])
        query = f"INSERT INTO risks ({columns}) VALUES ({placeholders})"
        
        # Execute
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, list(risk_data.values()))
        conn.commit()
        conn.close()
        
        print(f"✅ Risk {risk_data['risk_id']} added to register")
        return risk_data['risk_id']
    
    def update_risk(self, risk_id: str, updates: Dict[str, Any]):
        """Update existing risk"""
        # Convert JSON fields
        json_fields = ['vulnerabilities', 'controls_in_place', 'control_gaps', 
                      'recommended_controls', 'treatment_actions']
        for field in json_fields:
            if field in updates and isinstance(updates[field], (list, dict)):
                updates[field] = json.dumps(updates[field])
        
        # Build UPDATE query
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        query = f"UPDATE risks SET {set_clause} WHERE risk_id = ?"
        
        # Execute
        conn = self._get_connection()
        cursor = conn.cursor()
        values = list(updates.values()) + [risk_id]
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        print(f"✅ Risk {risk_id} updated")
    
    def get_risk(self, risk_id: str) -> Optional[Dict[str, Any]]:
        """Get single risk by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM risks WHERE risk_id = ?", (risk_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return None
        
        # Convert to dictionary
        risk = dict(row)
        
        # Parse JSON fields
        json_fields = ['vulnerabilities', 'controls_in_place', 'control_gaps', 
                      'recommended_controls', 'treatment_actions']
        for field in json_fields:
            if risk.get(field):
                try:
                    risk[field] = json.loads(risk[field])
                except:
                    pass
        
        return risk
    
    def get_all_risks(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Get all risks with optional filters
        
        Args:
            filters: Dictionary of filters, e.g.:
                {
                    'status': 'Open',
                    'risk_rating': 5,
                    'risk_owner': 'CTO'
                }
        
        Returns:
            List of risk dictionaries
        """
        query = "SELECT * FROM risks"
        params = []
        
        if filters:
            where_clauses = []
            for key, value in filters.items():
                where_clauses.append(f"{key} = ?")
                params.append(value)
            query += " WHERE " + " AND ".join(where_clauses)
        
        query += " ORDER BY risk_rating DESC, date_identified DESC"
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        risks = []
        for row in rows:
            risk = dict(row)
            
            # Parse JSON fields
            json_fields = ['vulnerabilities', 'controls_in_place', 'control_gaps', 
                          'recommended_controls', 'treatment_actions']
            for field in json_fields:
                if risk.get(field):
                    try:
                        risk[field] = json.loads(risk[field])
                    except:
                        pass
            
            risks.append(risk)
        
        return risks
    
    def get_summary(self) -> Dict[str, Any]:
        """Get risk register summary statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Total risks
        cursor.execute("SELECT COUNT(*) FROM risks")
        total_risks = cursor.fetchone()[0]
        
        # By status
        cursor.execute("""
            SELECT status, COUNT(*) 
            FROM risks 
            GROUP BY status
        """)
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # By risk rating
        cursor.execute("""
            SELECT risk_rating, COUNT(*) 
            FROM risks 
            GROUP BY risk_rating
            ORDER BY risk_rating DESC
        """)
        rating_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # High priority (rating >= 4)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM risks 
            WHERE risk_rating >= 4 AND status != 'Closed'
        """)
        high_priority = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_risks': total_risks,
            'status_counts': status_counts,
            'rating_counts': rating_counts,
            'high_priority': high_priority,
            'open_risks': status_counts.get('Open', 0),
            'closed_risks': status_counts.get('Closed', 0)
        }
    
    def delete_risk(self, risk_id: str):
        """Delete a risk (use carefully!)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM risks WHERE risk_id = ?", (risk_id,))
        conn.commit()
        conn.close()
        
        print(f"⚠️ Risk {risk_id} deleted")
    
    def close_database(self):
        """Close database connection (if needed)"""
        pass  # SQLite auto-closes


# Example usage
if __name__ == "__main__":
    print("Testing Risk Register Database...")
    
    # Initialize database
    db = RiskRegisterDB()
    
    # Test: Add a sample risk
    sample_risk = {
        'risk_title': 'Test Risk - Unauthorized Database Access',
        'risk_description': 'Risk of unauthorized access to database server',
        'asset_name': 'Database Server',
        'asset_type': 'Database',
        'impact_level': 5,
        'probability_level': 5,
        'risk_value': 25,
        'risk_rating': 5,
        'risk_evaluation_level': 'EXTREME',
        'risk_classification': 'NON-ACCEPTABLE',
        'risk_owner': 'CTO',
        'management_decision': 'TREAT',
        'status': 'Open',
        'date_identified': datetime.now().strftime('%Y-%m-%d')
    }
    
    risk_id = db.add_risk(sample_risk)
    print(f"\n✅ Created risk: {risk_id}")
    
    # Test: Get the risk
    risk = db.get_risk(risk_id)
    print(f"\n📋 Retrieved risk: {risk['risk_title']}")
    
    # Test: Get summary
    summary = db.get_summary()
    print(f"\n📊 Summary: {summary}")
    
    print("\n✅ Database tests passed!")