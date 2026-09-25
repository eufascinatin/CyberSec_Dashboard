import streamlit as st
import sqlite3
import time
from core.db import DB_FILE
from core.auth import hash_password, verify_password

@st.dialog("Change Password")
def change_password_dialog():
    st.write("Change password for **{}**".format(st.session_state.get("username_logged_in", "Unknown")))
    with st.form("change_password_form"):
        current_pw = st.text_input("Current Password", type="password")
        new_pw = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm New Password", type="password")
        
        submitted = st.form_submit_button("Update Password")
        if submitted:
            if not current_pw or not new_pw or not confirm_pw:
                st.error("All fields are required!")
            elif new_pw != confirm_pw:
                st.error("New passwords do not match!")
            else:
                username = st.session_state.get("username_logged_in")
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT password FROM users WHERE username=?", (username,))
                result = c.fetchone()
                
                if not result or not verify_password(current_pw, result[0]):
                    st.error("Current password is incorrect!")
                    conn.close()
                else:
                    c.execute("UPDATE users SET password=? WHERE username=?", (hash_password(new_pw), username))
                    conn.commit()
                    conn.close()
                    st.success("Password updated successfully!")
                    time.sleep(1)
                    st.rerun()
