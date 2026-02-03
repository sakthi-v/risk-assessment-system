"""
Database Initialization Script
Creates the risks table with all required fields
Run this ONCE to set up the database
"""

import sqlite3
import os


def create_risk_register_database():
    """
    Create Risk Register database with risks table
    """
    
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'risk_register.db')
    db_path = os.path.normpath(db_path)
    
    print("="*80)
    print("🔧 INITIALIZING RISK REGISTER DATABASE")
    print("="*80)
    print(f"Database location: {db_path}\n")
    
    # Connect to database (creates file if doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Drop existing table if needed (optional - comment out to preserve data)
    # cursor.execute("DROP TABLE IF EXISTS risks")
    
    # Create risks table
    print("📋 Creating 'risks' table...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risks (
            -- Primary Key
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            risk_id TEXT UNIQUE NOT NULL,
            
            -- Asset Information
            asset_name TEXT NOT NULL,
            asset_type TEXT,
            
            -- Threat Information
            threat_name TEXT NOT NULL,
            threat_description TEXT,
            
            -- Risk Ratings (Inherent)
            inherent_risk_rating REAL,
            inherent_risk_level TEXT,
            likelihood_rating REAL,
            
            -- CIA Impact
            confidentiality_impact REAL,
            integrity_impact REAL,
            availability_impact REAL,
            
            -- Controls
            existing_controls TEXT,              -- JSON array
            control_rating REAL,
            
            -- Residual Risk
            residual_risk_rating REAL,
            residual_risk_level TEXT,
            
            -- Control Gaps & Recommendations
            control_gaps TEXT,                   -- JSON array
            recommended_controls TEXT,           -- JSON array
            
            -- Treatment Plan (Agent 4 outputs)
            treatment_plan TEXT,                 -- JSON object
            rtp_answers TEXT,                    -- JSON object
            treatment_decision TEXT,             -- TREAT, ACCEPT, TRANSFER, TERMINATE
            risk_owner TEXT,
            priority TEXT,                       -- CRITICAL, HIGH, MEDIUM, LOW
            target_completion_date TEXT,
            
            -- Status & Tracking
            status TEXT DEFAULT 'Open',          -- Open, In Progress, Closed
            identified_date TEXT,
            last_updated TEXT,
            review_date TEXT,
            closure_date TEXT,
            
            -- Additional Info
            comments TEXT,
            
            -- Raw Agent Outputs (for reference)
            agent_1_raw TEXT,                    -- JSON object
            agent_2_raw TEXT,                    -- JSON object
            agent_3_raw TEXT,                    -- JSON object
            agent_4_raw TEXT                     -- JSON object
        )
    """)
    
    print("✅ 'risks' table created successfully!\n")
    
    # Create indexes for better query performance
    print("📊 Creating indexes...")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_id ON risks(risk_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_asset_name ON risks(asset_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON risks(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_priority ON risks(priority)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_owner ON risks(risk_owner)")
    
    print("✅ Indexes created successfully!\n")
    
    # Commit changes
    conn.commit()
    
    # Verify table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='risks'")
    result = cursor.fetchone()
    
    if result:
        print("✅ Verification: 'risks' table exists in database")
        
        # Show table schema
        cursor.execute("PRAGMA table_info(risks)")
        columns = cursor.fetchall()
        
        print(f"\n📋 Table Schema ({len(columns)} columns):")
        print("-" * 80)
        for col in columns:
            col_id, name, col_type, notnull, default, pk = col
            pk_str = " (PRIMARY KEY)" if pk else ""
            notnull_str = " NOT NULL" if notnull else ""
            default_str = f" DEFAULT {default}" if default else ""
            print(f"{col_id+1:2d}. {name:30s} {col_type:10s}{pk_str}{notnull_str}{default_str}")
        
        print("-" * 80)
        
    else:
        print("❌ Error: Table was not created!")
    
    conn.close()
    
    print("\n" + "="*80)
    print("✅ DATABASE INITIALIZATION COMPLETE!")
    print("="*80)
    print("\n💡 You can now save risks to the Risk Register!\n")


def check_database_status():
    """
    Check if database and table exist
    """
    
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'risk_register.db')
    db_path = os.path.normpath(db_path)
    
    print("="*80)
    print("🔍 CHECKING DATABASE STATUS")
    print("="*80)
    
    # Check if file exists
    if os.path.exists(db_path):
        print(f"✅ Database file exists: {db_path}")
        
        # Check if table exists
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        if tables:
            print(f"\n📊 Tables in database:")
            for table in tables:
                print(f"   - {table[0]}")
                
                # Count rows
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                count = cursor.fetchone()[0]
                print(f"     (Contains {count} rows)")
        else:
            print("\n❌ No tables found in database!")
            print("💡 Run create_risk_register_database() to initialize")
        
        conn.close()
        
    else:
        print(f"❌ Database file not found: {db_path}")
        print("💡 Run create_risk_register_database() to create it")
    
    print("="*80 + "\n")


if __name__ == "__main__":
    import sys
    
    print("\n" + "="*80)
    print("🗄️  RISK REGISTER DATABASE SETUP")
    print("="*80 + "\n")
    
    # Check current status
    check_database_status()
    
    # Ask user if they want to initialize
    print("\n🔧 Do you want to initialize/reset the database?")
    print("   This will create the 'risks' table if it doesn't exist.")
    print("   (Existing data will be preserved)")
    
    response = input("\nProceed? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        create_risk_register_database()
        print("\n🎉 Setup complete! You can now use the Risk Register.")
    else:
        print("\n❌ Cancelled. No changes made.")
    
    print("\n" + "="*80)