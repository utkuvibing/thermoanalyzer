"""Analysis pipeline history tracker.

Logs each processing step (data load, smoothing, baseline, peak detection, etc.)
into ``st.session_state.analysis_history`` and renders a timeline in the sidebar
or within a page expander.
"""

from datetime import datetime
import streamlit as st


def _log_event(action: str, details: str = "", page: str = ""):
    """Append an analysis event to the session-state history list.

    Parameters
    ----------
    action : str
        Short verb phrase, e.g. "Data Loaded", "Smoothing Applied".
    details : str
        One-line description with specifics (file name, method, etc.).
    page : str
        Page that triggered the event (e.g. "DSC Analysis").
    """
    history = st.session_state.setdefault("analysis_history", [])
    step_number = len(history) + 1
    history.append({
        "step_number": step_number,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "action": action,
        "details": details,
        "page": page,
    })


def render_history_sidebar():
    """Render a compact numbered timeline inside the sidebar."""
    history = st.session_state.get("analysis_history", [])
    if not history:
        st.caption("No analysis steps recorded yet.")
        return

    for entry in history:
        st.markdown(
            f"**{entry['step_number']}.** {entry['action']}  \n"
            f"<span style='font-size:0.75rem;color:#7B8BA3'>"
            f"{entry['timestamp']} · {entry['page']}</span>",
            unsafe_allow_html=True,
        )
        if entry.get("details"):
            st.caption(f"  {entry['details']}")


def render_history_expander():
    """Render the full history as a table inside an expander on the current page."""
    history = st.session_state.get("analysis_history", [])
    if not history:
        return

    with st.expander(f"Analysis History ({len(history)} steps)", expanded=False):
        import pandas as pd
        df = pd.DataFrame(history)
        df.columns = ["#", "Time", "Action", "Details", "Page"]
        st.dataframe(df, use_container_width=True, hide_index=True)
