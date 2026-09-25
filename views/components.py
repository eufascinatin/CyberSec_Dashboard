import streamlit as st

def render_table_headers(col_widths, headers):
    html = "<div style='display: flex; gap: 1rem; background-color: #2b2b3b; padding: 10px 15px; border-radius: 6px; align-items: center; margin-bottom: 15px;'>"
    total = sum(col_widths)
    for width, header in zip(col_widths, headers):
        # Streamlit's st.columns roughly uses flex: {width} 1 0%
        html += f"<div style='flex: {width} 1 0%; font-size: 14px; font-weight: bold; color: #ffffff;'>{header}</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def render_pagination_controls(table_key, total_items):
    page_size_key = f"{table_key}_page_size"
    page_num_key = f"{table_key}_page_num"
    
    if page_size_key not in st.session_state:
        st.session_state[page_size_key] = 10
    if page_num_key not in st.session_state:
        st.session_state[page_num_key] = 1
        
    current_size = st.session_state[page_size_key]
    options = [10, 20, 50, 100]
    
    col_sel, _, col_prev, col_info, col_next = st.columns([2, 5, 1, 2, 1])
    with col_sel:
        new_size = st.selectbox("Items per page", options, index=options.index(current_size), key=f"{table_key}_sel")
        if new_size != current_size:
            st.session_state[page_size_key] = new_size
            st.session_state[page_num_key] = 1
            st.rerun()
            
    total_pages = max(1, (total_items + st.session_state[page_size_key] - 1) // st.session_state[page_size_key])
    
    if st.session_state[page_num_key] > total_pages:
        st.session_state[page_num_key] = total_pages
        
    with col_prev:
        if st.button("Previous", key=f"{table_key}_prev", disabled=st.session_state[page_num_key] <= 1):
            st.session_state[page_num_key] -= 1
            st.rerun()
            
    with col_info:
        st.markdown(f"<div style='text-align: center; padding-top: 10px;'>Page <b>{st.session_state[page_num_key]}</b> of <b>{total_pages}</b></div>", unsafe_allow_html=True)
        
    with col_next:
        if st.button("Next", key=f"{table_key}_next", disabled=st.session_state[page_num_key] >= total_pages):
            st.session_state[page_num_key] += 1
            st.rerun()
            
    start_idx = (st.session_state[page_num_key] - 1) * st.session_state[page_size_key]
    end_idx = start_idx + st.session_state[page_size_key]
    st.divider()
    return start_idx, end_idx
