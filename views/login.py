import streamlit as st
import sqlite3
import secrets
from core.db import DB_FILE
from core.auth import hash_password, verify_password
from datetime import datetime, timezone, timedelta

def check_password(cookie_controller):
    # Hide the top toolbar and footer
    st.markdown("""
        <style>
            [data-testid="stHeader"] {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

    # Persistent login via session token.
    # The CookieController needs one script rerun to sync its cookie store from the
    # browser before ANY read of it can be trusted: too early, cookie_controller.get()
    # either raises TypeError (its internal store is still None) or returns None even
    # when a valid session cookie exists, which used to make the login form render for
    # one frame before the real token was picked up on the next rerun. Gating here,
    # before the first cookie read of the whole function, covers both the crash and
    # the flicker in one place instead of reacting to them separately downstream.
    if "first_cookie_pass" not in st.session_state:
        st.session_state["first_cookie_pass"] = True
        
        loader_html = """
        <style>
        .cyber-loader-wrapper {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 70vh;
            flex-direction: column;
            font-family: 'Inter', system-ui, sans-serif;
        }
        .cyber-loader-container {
            position: relative;
            width: 160px; height: 160px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .cyber-ring {
            position: absolute;
            border-radius: 50%;
            border: 2px solid transparent;
        }
        .cyber-ring-1 {
            width: 140px; height: 140px;
            border-top: 2px solid #38BDF8;
            border-left: 2px solid #38BDF8;
            animation: cyber-spin 2s linear infinite;
            filter: drop-shadow(0 0 8px rgba(56,189,248,0.6));
        }
        .cyber-ring-2 {
            width: 110px; height: 110px;
            border-bottom: 2px solid #818CF8;
            border-right: 2px solid #818CF8;
            animation: cyber-spin-reverse 1.5s linear infinite;
            filter: drop-shadow(0 0 8px rgba(129,140,248,0.6));
        }
        .cyber-ring-3 {
            width: 80px; height: 80px;
            border-top: 2px solid #10B981;
            animation: cyber-spin 3s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite;
        }
        .cyber-core {
            width: 30px; height: 30px;
            background: radial-gradient(circle, #38BDF8 0%, transparent 70%);
            border-radius: 50%;
            animation: cyber-pulse 1.5s ease-in-out infinite;
        }
        .cyber-status-text {
            margin-top: 40px;
            color: #38BDF8;
            font-size: 16px;
            font-weight: 600;
            letter-spacing: 4px;
            text-transform: uppercase;
            animation: cyber-pulse-text 2s ease-in-out infinite;
        }
        @keyframes cyber-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes cyber-spin-reverse { 0% { transform: rotate(360deg); } 100% { transform: rotate(0deg); } }
        @keyframes cyber-pulse { 0%, 100% { transform: scale(0.8); opacity: 0.5; } 50% { transform: scale(1.2); opacity: 1; } }
        @keyframes cyber-pulse-text { 0%, 100% { opacity: 0.5; text-shadow: none; } 50% { opacity: 1; text-shadow: 0 0 10px rgba(56,189,248,0.8); } }
        </style>
        <div class="cyber-loader-wrapper">
            <div class="cyber-loader-container">
                <div class="cyber-ring cyber-ring-1"></div>
                <div class="cyber-ring cyber-ring-2"></div>
                <div class="cyber-ring cyber-ring-3"></div>
                <div class="cyber-core"></div>
            </div>
            <div class="cyber-status-text">INITIALIZING SYSTEM</div>
        </div>
        """
        st.markdown(loader_html, unsafe_allow_html=True)
        return False

    try:
        token = cookie_controller.get("session")
    except TypeError:
        token = None

    if token:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT username, role, COALESCE(last_activity, '') FROM users WHERE session_token=?", (token,))
        result = c.fetchone()
        
        token_valid = False
        if result:
            uname, rle, last_act_str = result
            now = datetime.now(timezone.utc)
            expired = False
            
            if last_act_str:
                try:
                    last_act = datetime.fromisoformat(last_act_str)
                    if now - last_act > timedelta(minutes=30):
                        expired = True
                except ValueError:
                    pass
                    
            if expired:
                cookie_controller.remove("session")
                c.execute("UPDATE users SET session_token=NULL WHERE session_token=?", (token,))
                conn.commit()
                if "password_correct" in st.session_state:
                    del st.session_state["password_correct"]
                st.warning("Session expired due to 30 minutes of inactivity. Please log in again.")
            else:
                c.execute("UPDATE users SET last_activity=? WHERE session_token=?", (now.isoformat(), token))
                conn.commit()
                token_valid = True
                
                if not st.session_state.get("password_correct", False):
                    st.session_state["username_logged_in"] = uname
                    st.session_state["password_correct"] = True
                    st.session_state["user_role"] = rle
                    c.execute("SELECT permissions FROM roles WHERE name=?", (rle,))
                    role_row = c.fetchone()
                    import json
                    st.session_state["permissions"] = json.loads(role_row[0]) if role_row else []
        else:
            cookie_controller.remove("session")
            if "password_correct" in st.session_state:
                del st.session_state["password_correct"]
                
        conn.close()
    # Defensively strip any stale auth-bypass query params from old bookmarked links.
    if "logged_in" in st.query_params or "username" in st.query_params or "session" in st.query_params:
        if "logged_in" in st.query_params: del st.query_params["logged_in"]
        if "username" in st.query_params: del st.query_params["username"]
        if "session" in st.query_params: del st.query_params["session"]

    def password_entered():
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Fallback to default values for existing sessions where schema might not be fully cached
        c.execute("SELECT password, role, COALESCE(is_locked, 0), COALESCE(failed_attempts, 0), COALESCE(must_change_password, 0) FROM users WHERE username=?", (st.session_state["username"],))
        result = c.fetchone()

        if result:
            db_pwd, role, is_locked, failed_attempts, must_change_pwd = result
            
            if is_locked == 1:
                st.session_state["login_error"] = "Account is locked. Please contact an administrator."
                conn.close()
                st.session_state["password_correct"] = False
                return

            if verify_password(st.session_state["password"], db_pwd):
                if must_change_pwd == 1:
                    st.session_state["force_password_change"] = True
                    st.session_state["change_pwd_username"] = st.session_state["username"]
                    conn.close()
                    return

                # Successful login
                c.execute("UPDATE users SET failed_attempts=0 WHERE username=?", (st.session_state["username"],))
                
                # Transparently upgrade legacy unsalted hashes to the salted format on login.
                if '$' not in db_pwd:
                    c.execute("UPDATE users SET password=? WHERE username=?",
                              (hash_password(st.session_state["password"]), st.session_state["username"]))
                    
                session_token = secrets.token_hex(32)
                now_iso = datetime.now(timezone.utc).isoformat()
                c.execute("UPDATE users SET session_token=?, last_activity=? WHERE username=?", (session_token, now_iso, st.session_state["username"]))
                conn.commit()
                cookie_controller.set("session", session_token)

                c.execute("SELECT permissions FROM roles WHERE name=?", (role,))
                role_row = c.fetchone()
                import json
                perms = json.loads(role_row[0]) if role_row else []
                conn.close()

                st.session_state["password_correct"] = True
                st.session_state["user_role"] = role
                st.session_state["permissions"] = perms
                st.session_state["username_logged_in"] = st.session_state["username"]
                st.session_state.pop("login_error", None)
                del st.session_state["password"]
            else:
                # Failed login
                failed_attempts += 1
                c.execute("UPDATE users SET failed_attempts=? WHERE username=?", (failed_attempts, st.session_state["username"]))
                
                # Check Admin failsafe
                c.execute("SELECT COUNT(*) FROM users WHERE role='Admin' AND COALESCE(is_locked, 0)=0")
                admin_count = c.fetchone()[0]
                is_sole_admin = (role == 'Admin' and admin_count <= 1)

                if is_sole_admin:
                    st.session_state["login_error"] = "Incorrect password."
                else:
                    if failed_attempts >= 5:
                        c.execute("UPDATE users SET is_locked=1 WHERE username=?", (st.session_state["username"],))
                        st.session_state["login_error"] = "Account locked due to 5 failed login attempts."
                    else:
                        st.session_state["login_error"] = f"Incorrect password. {5 - failed_attempts} attempts remaining."
                
                conn.commit()
                conn.close()
                st.session_state["password_correct"] = False
        else:
            conn.close()
            st.session_state["login_error"] = "User not known or password incorrect"
            st.session_state["password_correct"] = False

    if not st.session_state.get("password_correct", False):
        if st.session_state.get("force_password_change"):
            change_pwd_placeholder = st.empty()
            with change_pwd_placeholder.container():
                st.markdown('<style>div[data-testid="stForm"] {max-width: 600px; width: 90%; margin: 0 auto;}</style>', unsafe_allow_html=True)
                st.markdown("<h1 style='text-align: center;'>🔒 Change Password Required</h1>", unsafe_allow_html=True)
                with st.form("change_password_form"):
                    st.info("You must change your password on your first login.")
                    new_pwd = st.text_input("New Password", type="password")
                    confirm_pwd = st.text_input("Confirm New Password", type="password")
                    submit_pwd = st.form_submit_button("Change Password", use_container_width=True)
                    cancel_pwd = st.form_submit_button("Cancel", use_container_width=True)
                if cancel_pwd:
                    del st.session_state["force_password_change"]
                    st.rerun()
                if submit_pwd:
                    if new_pwd != confirm_pwd:
                        st.error("Passwords do not match!")
                    elif len(new_pwd) < 4:
                        st.error("Password must be at least 4 characters.")
                    else:
                        conn = sqlite3.connect(DB_FILE)
                        c = conn.cursor()
                        c.execute("SELECT password FROM users WHERE username=?", (st.session_state["change_pwd_username"],))
                        old_hash = c.fetchone()[0]
                        
                        if verify_password(new_pwd, old_hash):
                            st.error("New password must not be the same as your old password.")
                            conn.close()
                        else:
                            c.execute("UPDATE users SET password=?, must_change_password=0, failed_attempts=0 WHERE username=?", 
                                      (hash_password(new_pwd), st.session_state["change_pwd_username"]))
                            conn.commit()
                            conn.close()
                            st.success("Password changed successfully! Please log in with your new password.")
                            del st.session_state["force_password_change"]
                            if "change_pwd_username" in st.session_state:
                                del st.session_state["change_pwd_username"]
                            st.rerun()
            return False

        login_placeholder = st.empty()
        with login_placeholder.container():
            st.markdown('<style>div[data-testid="stForm"] {max-width: 600px; width: 90%; margin: 0 auto;}</style>', unsafe_allow_html=True)
            st.markdown("<h1 style='text-align: center;'>🛡️ CyberSec Admin Login</h1>", unsafe_allow_html=True)
            with st.form("login_form"):
                st.text_input("Username", key="username")
                st.text_input("Password", type="password", key="password")
                submit = st.form_submit_button("Login", use_container_width=True)
            
            if st.session_state.get("password_correct") is False:
                error_msg = st.session_state.get("login_error", "😕 User not known or password incorrect")
                st.markdown(f"<div style='max-width: 600px; margin: 0 auto;'><div style='color: red; text-align: center; font-weight: bold;'>{error_msg}</div></div>", unsafe_allow_html=True)
                
        if submit:
            login_placeholder.empty()
            password_entered()
            if st.session_state.get("password_correct", False):
                return True
            st.rerun()
            
        return False
    else:
        return True

