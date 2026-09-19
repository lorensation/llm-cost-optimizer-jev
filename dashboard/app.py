import os
import sqlite3

import pandas as pd
import streamlit as st

path = os.getenv("AUTOPILOT_DATABASE_URL", "sqlite:///data/autopilot.db").removeprefix("sqlite:///")
st.title("LLM Cost Autopilot")
st.caption("Cost, quality gates and audit coverage. Fixture data is labelled synthetic.")
try:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    requests = pd.read_sql_query("SELECT id,contract_id,policy_id,status,cost_microusd,cost_status,created_at FROM requests ORDER BY created_at DESC", conn)
    calls = pd.read_sql_query("SELECT request_id,kind,attempt,requested_model,resolved_model,status,cost_microusd,latency_ms,error_code FROM calls", conn)
    st.metric("Requests", len(requests))
    st.dataframe(requests, use_container_width=True)
    st.subheader("Calls")
    st.dataframe(calls, use_container_width=True)
except Exception as exc:
    st.info(f"No readable database yet: {exc}")

