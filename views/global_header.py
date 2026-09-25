import streamlit as st
import sqlite3
import pytz
from datetime import datetime
from core.db import DB_FILE
from views.change_password import change_password_dialog

def render_global_header(cookie_controller):
        username = st.session_state.get('username_logged_in', 'Admin')
        tz = pytz.timezone('Europe/Bratislava')
        current_time = datetime.now(tz).strftime('%d.%m.%Y %H:%M')
        
        st.markdown("""
        <style>
        .header-time { text-align: right; color: #aaa; }
        /* Stacked Layout for < 1150px (ensures user button doesn't shrink below ~230px) */
        @media (max-width: 1150px) {
            div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]:first-of-type {
                flex-direction: column;
            }
            div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="column"] {
                width: 100% !important;
                min-width: 100% !important;
                margin-bottom: 0.5rem;
            }
            .header-time {
                text-align: left;
            }
        }
        </style>
        """, unsafe_allow_html=True)
        
        col_title, col_time, col_settings, col_user = st.columns([5, 1.5, 1.5, 2], vertical_alignment="center")
        
        with col_title:
            st.markdown("<h2 style='margin:0; padding:0;'>Real-Time Data Flow Protection Dashboard</h2>", unsafe_allow_html=True)
            
        with col_time:
            @st.fragment(run_every="1s")
            def live_clock():
                tz = pytz.timezone('Europe/Bratislava')
                current_time = datetime.now(tz).strftime('%d.%m.%Y %H:%M:%S')
                st.markdown(f"""
                <div class='header-time'>
                    <small>⌚ {current_time} (CET)</small>
                </div>
                """, unsafe_allow_html=True)
            live_clock()
                
        with col_settings:
            perms = st.session_state.get("permissions", [])
            has_settings_perms = any(p in perms for p in ["manage_dashboard", "manage_sensor", "read_sensor", "manage_user", "read_user", "manage_server", "read_server", "manage_role", "read_role", "manage_permission", "read_permission", "audit_trails"])
            has_dashboard_perm = "read_dashboard" in perms
            
            if st.session_state.current_view == 'dashboard':
                if has_settings_perms:
                    if st.button("⚙️ Settings", use_container_width=True):
                        st.session_state.current_view = 'settings'
                        st.rerun()
            else:
                if has_dashboard_perm:
                    if st.button("🔙 Back", use_container_width=True):
                        st.session_state.current_view = 'dashboard'
                        st.rerun()
                        
        with col_user:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT title, first_name, last_name, email, phone_number FROM users WHERE username=?", (username,))
            user_info = c.fetchone()
            conn.close()
            
            display_name = username
            details_html = ""
            if user_info:
                title, fname, lname, email, phone = user_info
                title = (title or "").strip()
                fname = (fname or "").strip()
                lname = (lname or "").strip()
                email = (email or "").strip()
                phone = (phone or "").strip()
                
                parts = []
                if fname or lname:
                    # Title is only shown if last name is present
                    if title and lname: parts.append(title)
                    if fname: parts.append(fname)
                    if lname: parts.append(lname)
                
                if parts:
                    display_name = " ".join(parts)
                    
                if display_name != username or email or phone:
                    details_html += "<div style='font-size: 0.9em; margin-bottom: 10px; line-height: 1.4;'>"
                    if display_name != username:
                        details_html += f"<b>Username:</b> {username}<br>"
                    if email:
                        details_html += f"<b>Email:</b> {email}<br>"
                    if phone:
                        details_html += f"<b>Phone:</b> {phone}<br>"
                    details_html += "</div><hr style='margin: 10px 0;'>"

            with st.popover(f"👤 {display_name}", use_container_width=True):
                if details_html:
                    st.markdown(details_html, unsafe_allow_html=True)
                    
                if st.button("🔑 Change Password", use_container_width=True):
                    change_password_dialog()
                if st.button("🚪 Logout", use_container_width=True):
                    # Clear session token from DB
                    token = cookie_controller.get("session")
                    if token:
                        conn = sqlite3.connect(DB_FILE)
                        c = conn.cursor()
                        c.execute("UPDATE users SET session_token=NULL WHERE session_token=?", (token,))
                        conn.commit()
                        conn.close()
                    cookie_controller.remove("session")
                    st.query_params.clear()
                    st.session_state.clear()
                    st.rerun()
