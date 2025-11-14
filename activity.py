# app.py — Complete Week 10: CloudMart Tagging Cost Governance Simulator (fixed)
import streamlit as st
import pandas as pd
import plotly.express as px
from io import StringIO

st.set_page_config(page_title="CloudMart Tagging Cost Governance", layout="wide")
st.title("☁️ CloudMart — Resource Tagging & Cost Governance Simulator")

# ------------------------- Load & Clean CSV -------------------------
@st.cache_data
def load_data(path="cloudmart_multi_account.csv"):
    # Read raw file contents (handles rows quoted as a whole)
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Normalize: remove stray double-quotes that wrap rows/fields
    cleaned = raw.replace('"', "").strip()

    # Parse cleaned CSV into DataFrame
    df = pd.read_csv(StringIO(cleaned))

    # Normalize column names
    df.columns = df.columns.str.strip()

    # Standardize Cost column
    if "MonthlyCostUSD" in df.columns:
        df["Cost"] = pd.to_numeric(df["MonthlyCostUSD"], errors="coerce").fillna(0)
    else:
        if "Cost" in df.columns:
            df["Cost"] = pd.to_numeric(df["Cost"], errors="coerce").fillna(0)
        else:
            raise ValueError("CSV missing MonthlyCostUSD or Cost column")

    # Normalize text columns -> replace empty strings with NaN for easier detection
    for c in df.select_dtypes(include=["object"]).columns:
        df[c] = df[c].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})

    # Ensure key fields exist (create if not present)
    for req in ["AccountID", "Service", "Region", "Environment", "Tagged", "ResourceID", "Project", "Department", "Owner", "CostCenter", "CreatedBy"]:
        if req not in df.columns:
            df[req] = pd.NA

    # Make AccountID string
    df["AccountID"] = df["AccountID"].astype(str)

    return df

# load
try:
    df = load_data()
    st.success("✅ Dataset loaded successfully.")
except Exception as e:
    st.error(f"❌ Could not load dataset: {e}")
    st.stop()

# keep original copy for deliverable
original_df = df.copy(deep=True)

# ------------------------- Task Set 1 — Data Exploration -------------------------
st.header("1️⃣ Task Set 1 — Data Exploration")

st.subheader("First 5 rows")
st.dataframe(df.head(5))

st.subheader("Missing values per column")
missing = df.isna().sum().sort_values(ascending=False)
st.dataframe(missing)

st.subheader("Tagged counts and % untagged")
tag_counts = df["Tagged"].fillna("No").value_counts()
total = len(df)
untag_count = int(tag_counts.get("No", 0))
untag_pct = (untag_count / total) * 100 if total else 0
st.metric("Total resources", total)
st.metric("Tagged", int(tag_counts.get("Yes", 0)))
st.metric("Untagged", untag_count, delta=f"{untag_pct:.2f}% untagged")

# ------------------------- Task Set 2 — Cost Visibility -------------------------
st.header("2️⃣ Task Set 2 — Cost Visibility")

# Create explicit Tagged_filled for safe grouping/plots
df["Tagged_filled"] = df["Tagged"].fillna("No")

# 2.1 total cost tagged vs untagged
tag_cost = df.groupby("Tagged_filled", dropna=False)["Cost"].sum().reset_index()
fig_tag_cost = px.pie(tag_cost, names="Tagged_filled", values="Cost", title="Cost: Tagged vs Untagged")
st.plotly_chart(fig_tag_cost, use_container_width=True)

total_cost = df["Cost"].sum()
untagged_cost = float(df.loc[df["Tagged_filled"] == "No", "Cost"].sum())
untagged_cost_pct = (untagged_cost / total_cost * 100) if total_cost else 0
st.metric("Total cost (USD)", f"${total_cost:,.2f}")
st.metric("Total untagged cost (USD)", f"${untagged_cost:,.2f}", delta=f"{untagged_cost_pct:.2f}% of total")

# 2.3 department with most untagged cost
dept_untagged = df[df["Tagged_filled"] == "No"].groupby("Department", dropna=False)["Cost"].sum().sort_values(ascending=False)
st.subheader("Departments with highest untagged cost")
st.dataframe(dept_untagged.reset_index().rename(columns={"Cost": "UntaggedCost"}).head(10))

# 2.4 project consumes most cost
proj_cost = df.groupby("Project", dropna=False)["Cost"].sum().sort_values(ascending=False)
st.subheader("Top projects by total cost")
st.dataframe(proj_cost.reset_index().head(10))

# 2.5 Prod vs Dev comparison
env_tag_cost = df.groupby(["Environment", "Tagged_filled"], dropna=False)["Cost"].sum().reset_index()
fig_env_tag = px.bar(env_tag_cost, x="Environment", y="Cost", color="Tagged_filled", barmode="group", title="Cost by Environment and Tagging")
st.plotly_chart(fig_env_tag, use_container_width=True)

# ------------------------- Task Set 3 — Tagging Compliance -------------------------
st.header("3️⃣ Task Set 3 — Tagging Compliance")

TAG_FIELDS = ["Department", "Project", "Environment", "Owner", "CostCenter", "CreatedBy"]

# 3.1 Tag completeness score
def completeness_score(row):
    return sum(0 if pd.isna(row.get(f)) else 1 for f in TAG_FIELDS)

df["TagCompleteness"] = df.apply(completeness_score, axis=1)
st.subheader("Tag completeness distribution")
st.dataframe(df["TagCompleteness"].value_counts().sort_index())

# 3.2 Top 5 lowest completeness
st.subheader("Top 5 resources with lowest Tag Completeness")
st.dataframe(df.sort_values("TagCompleteness").head(5)[["ResourceID", "Service", "TagCompleteness", "Cost", "Tagged_filled"]])

# 3.3 most frequently missing tag fields
missing_tag_fields = df[TAG_FIELDS].isna().sum().sort_values(ascending=False)
st.subheader("Most frequently missing tag fields")
st.dataframe(missing_tag_fields)

# 3.4 list all untagged resources and costs
untagged_df = df[df["Tagged_filled"] == "No"].copy()
st.subheader("List of untagged resources")
st.dataframe(untagged_df[["AccountID","ResourceID","Service","Region","Department","Project","Environment","Owner","Cost"]])

# 3.5 export untagged
csv_untagged = untagged_df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download untagged_resources.csv", csv_untagged, "untagged_resources.csv")

# ------------------------- Task Set 4 — Visualization Dashboard -------------------------
st.header("4️⃣ Task Set 4 — Visualization Dashboard & Filters")

with st.expander("Filters (Service, Region, Department)"):
    sel_service = st.multiselect("Service", options=sorted(df["Service"].dropna().unique()), help="Filter by service")
    sel_region = st.multiselect("Region", options=sorted(df["Region"].dropna().unique()), help="Filter by region")
    sel_department = st.multiselect("Department", options=sorted(df["Department"].dropna().unique()), help="Filter by department")

filtered = df.copy()
if sel_service:
    filtered = filtered[filtered["Service"].isin(sel_service)]
if sel_region:
    filtered = filtered[filtered["Region"].isin(sel_region)]
if sel_department:
    filtered = filtered[filtered["Department"].isin(sel_department)]

# 4.1 pie tagged vs untagged (counts or cost by choice)
df_pie = filtered.groupby("Tagged_filled", dropna=False)["Cost"].sum().reset_index()
fig_pie = px.pie(df_pie, names="Tagged_filled", values="Cost", title="Tagged vs Untagged (filtered - cost)")
st.plotly_chart(fig_pie, use_container_width=True)

# 4.2 bar chart cost per department by tagging status
dept_tag = filtered.assign(Tagged_filled=filtered["Tagged_filled"]).groupby(["Department", "Tagged_filled"], dropna=False)["Cost"].sum().reset_index()
fig_dept = px.bar(dept_tag, x="Department", y="Cost", color="Tagged_filled", barmode="group", title="Cost per Department by Tagging Status")
st.plotly_chart(fig_dept, use_container_width=True)

# 4.3 horizontal bar chart total cost per service
service_cost = filtered.groupby("Service", dropna=False)["Cost"].sum().sort_values(ascending=True).reset_index()
fig_service = px.bar(service_cost, x="Cost", y="Service", orientation="h", title="Total Cost per Service")
st.plotly_chart(fig_service, use_container_width=True)

# 4.4 cost by environment
env_cost = filtered.groupby("Environment", dropna=False)["Cost"].sum().reset_index()
fig_env = px.pie(env_cost, names="Environment", values="Cost", title="Cost by Environment")
st.plotly_chart(fig_env, use_container_width=True)

# ------------------------- Task Set 5 — Tag Remediation Workflow -------------------------
st.header("5️⃣ Task Set 5 — Tag Remediation Workflow")

st.write("Edit missing tags directly below (Department/Project/Owner etc.). After editing, press **Apply Remediation** to recalculate metrics and generate the remediated file.")

# show editable table (start with only untagged to focus)
editable_df = st.data_editor(untagged_df.drop(columns=["TagCompleteness"], errors='ignore'), num_rows="dynamic", use_container_width=True, key="editor1")

if st.button("Apply Remediation & Recalculate"):
    # Merge edited changes back into original df copy
    remediated = df.copy()
    # create a map ResourceID -> row from edited
    edited_map = editable_df.set_index("ResourceID").to_dict(orient="index")
    # apply edits
    for rid, changes in edited_map.items():
        for col, val in changes.items():
            remediated.loc[remediated["ResourceID"] == rid, col] = val

    # Recompute TagCompleteness & Tagged (simple heuristic: if Department & Owner present -> Tagged Yes)
    remediated["TagCompleteness"] = remediated.apply(lambda r: sum(0 if pd.isna(r.get(f)) else 1 for f in TAG_FIELDS), axis=1)
    remediated["Tagged_filled"] = remediated.apply(lambda r: "Yes" if (not pd.isna(r.get("Department")) and not pd.isna(r.get("Owner"))) else (r.get("Tagged_filled") if not pd.isna(r.get("Tagged_filled")) else "No"), axis=1)

    # Recalculate untagged cost
    before_untag_cost = untagged_cost
    after_untag_cost = remediated[remediated["Tagged_filled"] == "No"]["Cost"].sum()
    before_untag_count = untag_count
    after_untag_count = int((remediated["Tagged_filled"] == "No").sum())

    col1, col2 = st.columns(2)
    col1.metric("Before — Untagged cost", f"${before_untag_cost:,.2f}", delta=None)
    col2.metric("After — Untagged cost", f"${after_untag_cost:,.2f}", delta=f"${after_untag_cost - before_untag_cost:,.2f}")

    col3, col4 = st.columns(2)
    col3.metric("Before — Untagged resources", before_untag_count)
    col4.metric("After — Untagged resources", after_untag_count, delta=after_untag_count - before_untag_count)

    # Save remediated for download & reporting
    remediated_csv = remediated.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download remediated.csv", remediated_csv, "remediated.csv")

    # Save remediated in session state
    st.session_state["remediated"] = remediated

    # Show changed resources (where Tagged changed)
    changed = remediated.merge(df[["ResourceID", "Tagged_filled"]], on="ResourceID", how="left", suffixes=("_after", "_before"))
    changed = changed[changed["Tagged_filled_after"] != changed["Tagged_filled_before"]][["ResourceID", "Tagged_filled_before", "Tagged_filled_after", "Cost"]]
    if not changed.empty:
        st.subheader("Resources with changed Tagged status (before -> after)")
        st.dataframe(changed)
else:
    st.info("No remediation applied yet. Edit the table and click 'Apply Remediation & Recalculate'.")

# ------------------------- Deliverables: original + report -------------------------
st.header("📁 Deliverables & Short Report")

# Download original.csv (as provided)
orig_csv = original_df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download original.csv", orig_csv, "original.csv")

# If remediated exists, show short report and download
if "remediated" in st.session_state:
    r = st.session_state["remediated"]
    tot = r["Cost"].sum()
    untag_cost_after = r[r["Tagged_filled"] == "No"]["Cost"].sum()
    untag_pct_after = (untag_cost_after / tot * 100) if tot else 0
    dept_missing_after = r[r["Tagged_filled"] == "No"].groupby("Department")["Cost"].sum().sort_values(ascending=False)

    report = f"""# CloudMart Tagging Remediation Report

- Total resources: {len(df)}
- % untagged resources (before): {untag_pct:.2f}%
- Total untagged cost (before): ${untagged_cost:,.2f}
- Total cost (after remediation): ${tot:,.2f}
- Total untagged cost (after remediation): ${untag_cost_after:,.2f}
- % of cost untagged (after): {untag_pct_after:.2f}%

## Departments with highest remaining untagged cost (after remediation)
{dept_missing_after.to_frame(name='UntaggedCost').to_markdown()}

## Recommendations
1. Enforce required tags at provisioning (Department, Project, Owner, CostCenter).
2. Propagate tags via IaC (Terraform/CloudFormation) and use resource tagging policies.
3. Alert on newly created untagged resources and block long-lived untagged Prod resources.
4. Implement monthly remediation sweeps and chargeback using CostCenter.
"""
    st.markdown("### Short report (preview)")
    st.code(report, language="markdown")
    st.download_button("⬇️ Download short_report.md", report.encode("utf-8"), "short_report.md")
else:
    st.info("Apply remediation to generate remediated dataset and short report.")

st.caption("This app implements the Week 10 lab deliverables: EDA, cost visibility, tag compliance, visualizations, remediation, downloads, and a short report.")
