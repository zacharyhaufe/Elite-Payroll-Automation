"""Streamlit web UI for the commission calculator."""

import io
import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from commission import load_employees, process_jobs, save_report

st.set_page_config(page_title="Elite Payroll — Commission Calculator", layout="centered")

st.title("Commission Calculator")
st.caption("Upload your files below to generate a commission report.")

# ── File uploaders ────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    employees_file = st.file_uploader("Employees (JSON)", type=["json"])

with col2:
    jobs_file = st.file_uploader("Jobs (CSV)", type=["csv"])

# ── Run ───────────────────────────────────────────────────────────────────────
if st.button("Calculate Commissions", type="primary", disabled=not (employees_file and jobs_file)):
    try:
        # Write uploads to temp files so existing functions can read them
        with tempfile.TemporaryDirectory() as tmpdir:
            emp_path = Path(tmpdir) / "employees.json"
            jobs_path = Path(tmpdir) / "jobs.csv"

            emp_path.write_bytes(employees_file.getvalue())
            jobs_path.write_bytes(jobs_file.getvalue())

            employees = load_employees(emp_path)
            rows = process_jobs(employees, jobs_path)

        if not rows:
            st.warning("No commission rows were produced. Check that employee names/IDs in the jobs file match the employees file.")
        else:
            df = pd.DataFrame(rows)

            # ── Summary table per employee ────────────────────────────────────
            st.subheader("Summary by Employee")
            summary = (
                df.groupby("employee_name")
                .agg(jobs=("job_id", "count"), total_earned=("earned", "sum"))
                .rename(columns={"jobs": "Jobs", "total_earned": "Total Earned ($)"})
                .sort_values("Total Earned ($)", ascending=False)
            )
            summary["Total Earned ($)"] = summary["Total Earned ($)"].map("${:,.2f}".format)
            st.dataframe(summary, use_container_width=True)

            # ── Detailed breakdown ────────────────────────────────────────────
            st.subheader("Job-by-Job Breakdown")
            display_df = df[["job_id", "employee_name", "subtotal", "commission_rate", "earned", "split_type"]].copy()
            display_df.columns = ["Job", "Employee", "Subtotal ($)", "Rate", "Earned ($)", "Type"]
            display_df["Subtotal ($)"] = display_df["Subtotal ($)"].map("${:,.2f}".format)
            display_df["Rate"] = display_df["Rate"].map("{:.0%}".format)
            display_df["Earned ($)"] = display_df["Earned ($)"].map("${:,.2f}".format)
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            # ── Download ──────────────────────────────────────────────────────
            csv_buf = io.StringIO()
            df.to_csv(csv_buf, index=False)
            st.download_button(
                label="Download Full Report (CSV)",
                data=csv_buf.getvalue(),
                file_name="commission_report.csv",
                mime="text/csv",
            )

    except FileNotFoundError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        raise
