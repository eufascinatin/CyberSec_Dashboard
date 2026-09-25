import streamlit as st
from core.db import get_system_settings, update_system_settings, check_server_status

def system_management():
    st.subheader("⚙️ System Settings")
    st.markdown("Configure core platform settings, including the primary central database connection.")
    
    settings = get_system_settings()
    
    with st.form("system_settings_form"):
        st.write("**Central Database Configuration**")
        st.info("This is the main datastore where global telemetry and audit events are stored.")
        
        new_uri = st.text_input("Central MongoDB URI", value=settings['central_db_uri'])
        new_db_name = st.text_input("Central Database Name", value=settings['central_db_name'])
        
        c1, c2 = st.columns(2)
        with c1:
            save_clicked = st.form_submit_button("Save Settings", type="primary", use_container_width=True)
        with c2:
            test_clicked = st.form_submit_button("Test Connection", use_container_width=True)
            
    if test_clicked:
        status = check_server_status(new_uri)
        if status == "Online":
            st.success(f"✅ Connection successful to {new_uri}!")
        else:
            st.error(f"❌ Connection failed. Ensure the server is reachable and credentials are correct.")
            
    if save_clicked:
        if "manage_system" not in st.session_state.get("permissions", []):
            st.error("You do not have permission to manage system settings.")
        else:
            update_system_settings(new_uri, new_db_name)
            st.success("System settings updated successfully!")
            st.rerun()
