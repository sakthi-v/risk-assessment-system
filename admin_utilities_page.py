"""
Admin Utilities Page - Database Migration & Email Testing
"""
import streamlit as st
import asyncio
import os
from dotenv import load_dotenv
from email_sender import send_email_smtp

load_dotenv()

st.set_page_config(page_title="Admin Utilities", page_icon="🔧", layout="wide")

st.title("🔧 Admin Utilities")
st.markdown("---")

# Tab layout
tab1, tab2 = st.tabs(["📧 Email Test", "🗄️ Database Migration"])

# ============================================
# TAB 1: EMAIL TEST
# ============================================
with tab1:
    st.header("📧 Test Email Functionality")
    st.info("Send a test email to verify Gmail SMTP configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        test_email = st.text_input("Recipient Email", value="vel518496@gmail.com")
        test_subject = st.text_input("Subject", value="Test Email from Risk Assessment System")
    
    with col2:
        test_body = st.text_area("Email Body", value="This is a test email to verify SMTP configuration is working correctly.", height=100)
    
    if st.button("📤 Send Test Email", type="primary"):
        with st.spinner("Sending email..."):
            try:
                result = send_email_smtp(
                    to_email=test_email,
                    subject=test_subject,
                    body=test_body
                )
                
                if result:
                    st.success(f"✅ Email sent successfully to {test_email}")
                else:
                    st.error("❌ Failed to send email. Check logs for details.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    st.markdown("---")
    st.subheader("📋 Current Email Configuration")
    st.code(f"""
Email Address: {os.getenv('EMAIL_ADDRESS', 'Not configured')}
SMTP Server: {os.getenv('EMAIL_SMTP_SERVER', 'Not configured')}
SMTP Port: {os.getenv('EMAIL_SMTP_PORT', 'Not configured')}
App Base URL: {os.getenv('APP_BASE_URL', 'Not configured')}
    """)

# ============================================
# TAB 2: DATABASE MIGRATION
# ============================================
with tab2:
    st.header("🗄️ Migrate Database to Turso")
    st.info("This will copy all data from local SQLite to Turso cloud database")
    
    # Show current configuration
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📍 Current Database")
        use_turso = os.getenv("USE_TURSO", "false").lower() == "true"
        if use_turso:
            st.success("✅ Using Turso (Cloud)")
            st.code(os.getenv("TURSO_DATABASE_URL", "Not configured"))
        else:
            st.warning("⚠️ Using Local SQLite")
            st.code("database/risk_register.db")
    
    with col2:
        st.subheader("🎯 Target Database")
        st.info("Turso Cloud Database")
        turso_url = os.getenv("TURSO_DATABASE_URL", "Not configured")
        st.code(turso_url)
    
    st.markdown("---")
    
    st.warning("⚠️ **Warning**: This will overwrite all data in Turso database!")
    
    confirm = st.checkbox("I understand this will replace all data in Turso")
    
    if st.button("🚀 Start Migration", type="primary", disabled=not confirm):
        with st.spinner("Migrating database... This may take a few minutes..."):
            try:
                # Import and run migration
                import libsql_client
                import sqlite3
                
                async def run_migration():
                    turso_url = os.getenv("TURSO_DATABASE_URL")
                    turso_token = os.getenv("TURSO_AUTH_TOKEN")
                    
                    st.write("📡 Connecting to Turso...")
                    turso_client = libsql_client.create_client(url=turso_url, auth_token=turso_token)
                    
                    local_db = "database/risk_register.db"
                    
                    if not os.path.exists(local_db):
                        st.error(f"❌ Local database not found: {local_db}")
                        return False
                    
                    local_conn = sqlite3.connect(local_db)
                    local_cursor = local_conn.cursor()
                    
                    st.write("📊 Reading local database...")
                    
                    # Get all tables
                    local_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in local_cursor.fetchall()]
                    
                    progress_bar = st.progress(0)
                    total_tables = len(tables)
                    
                    for idx, table in enumerate(tables):
                        st.write(f"📋 Migrating table: **{table}**")
                        
                        # Get table schema
                        local_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
                        create_sql = local_cursor.fetchone()[0]
                        
                        # Create table in Turso
                        try:
                            await turso_client.execute(f"DROP TABLE IF EXISTS {table}")
                            await turso_client.execute(create_sql)
                        except Exception as e:
                            st.warning(f"⚠️ Table creation: {e}")
                        
                        # Get all data
                        local_cursor.execute(f"SELECT * FROM {table}")
                        rows = local_cursor.fetchall()
                        
                        if not rows:
                            st.write(f"  ℹ️ No data in {table}")
                            progress_bar.progress((idx + 1) / total_tables)
                            continue
                        
                        # Get column names
                        local_cursor.execute(f"PRAGMA table_info({table})")
                        columns = [col[1] for col in local_cursor.fetchall()]
                        
                        # Insert data
                        placeholders = ",".join(["?" for _ in columns])
                        insert_sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
                        
                        migrated = 0
                        for row in rows:
                            try:
                                await turso_client.execute(insert_sql, list(row))
                                migrated += 1
                            except Exception as e:
                                pass  # Skip errors
                        
                        st.write(f"  ✅ Migrated {migrated}/{len(rows)} rows")
                        progress_bar.progress((idx + 1) / total_tables)
                    
                    local_conn.close()
                    return True
                
                # Run async migration
                success = asyncio.run(run_migration())
                
                if success:
                    st.success("✅ Migration completed successfully!")
                    st.balloons()
                else:
                    st.error("❌ Migration failed")
                    
            except Exception as e:
                st.error(f"❌ Migration error: {str(e)}")
                st.exception(e)
    
    st.markdown("---")
    st.info("💡 **Tip**: After migration, update `.env` file to set `USE_TURSO=true`")
