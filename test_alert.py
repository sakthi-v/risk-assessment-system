import streamlit as st
from phase2_risk_resolver.database.followup_checker import get_risks_needing_followup
from database_manager import get_database_connection

st.title("🔍 Follow-up Alert Debug Test")

try:
    st.info("Testing database connection...")
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM risks")
    total = cursor.fetchone()[0]
    st.success(f"✅ Total risks: {total}")
    
    cursor.execute("SELECT COUNT(*) FROM risks WHERE treatment_decision IS NOT NULL")
    with_decision = cursor.fetchone()[0]
    st.success(f"✅ Risks with decision: {with_decision}")
    
    cursor.execute("SELECT risk_id, created_at, treatment_decision FROM risks LIMIT 5")
    samples = cursor.fetchall()
    st.write("Sample risks:", samples)
    
    conn.close()
    
    st.info("Calling get_risks_needing_followup()...")
    risks = get_risks_needing_followup(days_threshold=5)
    
    st.success(f"✅ Returned {len(risks) if risks else 0} risks")
    
    if risks:
        for r in risks[:3]:
            st.write(r)
    else:
        st.error("❌ No risks returned!")
        
except Exception as e:
    st.error(f"❌ Error: {str(e)}")
    import traceback
    st.code(traceback.format_exc())
