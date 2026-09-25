import streamlit as st
import logging
from streamlit_cookies_controller import CookieController
from core.style import apply_custom_css
from core.db import init_sqlite
from views.login import check_password
from views.global_header import render_global_header
from views.dashboard import render_dashboard_view
from views.settings.settings_main import render_settings_view

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)

st.set_page_config(page_title='CyberSec Dashboard', page_icon='🛡️', layout='wide')

cookie_controller = CookieController()

if 'current_view' not in st.session_state:
    st.session_state.current_view = 'dashboard'
if 'auto_refresh_rate' not in st.session_state:
    st.session_state.auto_refresh_rate = 5

apply_custom_css()
init_sqlite()

if check_password(cookie_controller):
    render_global_header(cookie_controller)
    perms = st.session_state.get('permissions', [])
    if st.session_state.current_view == 'dashboard' and 'read_dashboard' not in perms:
        has_settings = any(p in perms for p in ["manage_dashboard", "manage_sensor", "read_sensor", "manage_user", "read_user", "manage_server", "read_server", "manage_role", "read_role", "manage_permission", "read_permission", "audit_trails"])
        if has_settings:
            st.session_state.current_view = 'settings'
            st.rerun()

    if st.session_state.current_view == 'dashboard':
        if 'read_dashboard' not in perms:
            st.error('Access Denied: You do not have permission to view the dashboard.')
        else:
            render_dashboard_view()
    elif st.session_state.current_view == 'settings':
        render_settings_view()
