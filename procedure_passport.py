import streamlit as st
import pandas as pd
import os
import uuid
import datetime
import io
from openpyxl.styles import PatternFill



# --- Session State Init ---
if "page" not in st.session_state: 
    st.session_state["page"] = "login"

if "resident" not in st.session_state: 
    st.session_state["resident"] = None

if "resident_name" not in st.session_state: 
    st.session_state["resident_name"] = ""

# -----------------------------
# CONFIG
# -----------------------------
ADMINS = ["pjenkins9@gmail.com"]

RATING_OPTIONS = ["Not Done", "Not Yet", "Steer", "Prompt", "Back up", "Auto"]
RATING_TO_NUM = {"Not Done": 0, "Not Yet": 1, "Steer": 2, "Prompt": 3, "Back up": 4, "Auto": 5}
RATING_COLOR = {
    "Not Done": "background-color:#bfbfbf; color:black;",   # gray
    "Not Yet": "background-color:#ff4d4d; color:white;",
    "Steer":   "background-color:#ff944d;",
    "Prompt":  "background-color:#ffd633;",
    "Back up": "background-color:#99e699;",
    "Auto":    "background-color:#33cc33; color:white;",
}

# -----------------------------
# FILES
# -----------------------------
SPECIALTIES_CSV = "specialties.csv"
PROCEDURES_CSV  = "procedures.csv"
STEPS_CSV       = "steps.csv"
ATTENDINGS_CSV  = "attendings.csv"
RESIDENTS_CSV   = "residents.csv"
CASES_CSV       = "cases.csv"
SCORES_CSV      = "scores.csv"

def bootstrap_reference_data():
    if not os.path.exists(SPECIALTIES_CSV):
        pd.DataFrame([
            {"specialty_id":"GS","specialty_name":"General Surgery"},
            {"specialty_id":"OB","specialty_name":"OB/GYN"},
            {"specialty_id":"URO","specialty_name":"Urology"},
        ]).to_csv(SPECIALTIES_CSV,index=False)

    if not os.path.exists(PROCEDURES_CSV):
        pd.DataFrame([
            {"procedure_id":"LAPAPP","procedure_name":"Laparoscopic Appendectomy","specialty_id":"GS"},
            {"procedure_id":"HYST","procedure_name":"Hysterectomy (BS vs BSO)","specialty_id":"OB"},
            {"procedure_id":"NEPH","procedure_name":"Nephrectomy","specialty_id":"URO"},
        ]).to_csv(PROCEDURES_CSV,index=False)

    if not os.path.exists(STEPS_CSV):
        pd.DataFrame([
            # Appendectomy steps
            {"step_id":"S_LAP_01","procedure_id":"LAPAPP","step_order":1,"step_name":"Establish pneumoperitoneum"},
            {"step_id":"S_LAP_02","procedure_id":"LAPAPP","step_order":2,"step_name":"Place ports"},
            {"step_id":"S_LAP_03","procedure_id":"LAPAPP","step_order":3,"step_name":"Control mesoappendix"},
            {"step_id":"S_LAP_04","procedure_id":"LAPAPP","step_order":4,"step_name":"Divide appendix base"},

            # Hysterectomy steps
            {"step_id":"S_HYST_01","procedure_id":"HYST","step_order":1,"step_name":"Exposure of the uterus/tubes/ovaries"},
            {"step_id":"S_HYST_02","procedure_id":"HYST","step_order":2,"step_name":"Identification of the ureters (transperitoneal vs retroperitoneal)"},
            {"step_id":"S_HYST_03","procedure_id":"HYST","step_order":3,"step_name":"Bilateral Salpingectomy"},
            {"step_id":"S_HYST_04","procedure_id":"HYST","step_order":4,"step_name":"Uterine ovarian ligament cauterization/transection"},
            {"step_id":"S_HYST_05","procedure_id":"HYST","step_order":5,"step_name":"Skeletonization IP ligaments"},
            {"step_id":"S_HYST_06","procedure_id":"HYST","step_order":6,"step_name":"Ligation IP ligaments"},
            {"step_id":"S_HYST_07","procedure_id":"HYST","step_order":7,"step_name":"Ligation/transection round ligaments"},
            {"step_id":"S_HYST_08","procedure_id":"HYST","step_order":8,"step_name":"Dissection posterior and anterior leaflets of broad ligament"},
            {"step_id":"S_HYST_09","procedure_id":"HYST","step_order":9,"step_name":"Bladder flap creation"},
            {"step_id":"S_HYST_10","procedure_id":"HYST","step_order":10,"step_name":"Skeletonization uterine vessels"},
            {"step_id":"S_HYST_11","procedure_id":"HYST","step_order":11,"step_name":"Uterine vessel ligation and transection"},
            {"step_id":"S_HYST_12","procedure_id":"HYST","step_order":12,"step_name":"Colpotomy"},
            {"step_id":"S_HYST_13","procedure_id":"HYST","step_order":13,"step_name":"Removal of uterus and fallopian tubes"},
            {"step_id":"S_HYST_14","procedure_id":"HYST","step_order":14,"step_name":"Cuff closure"},

            # Nephrectomy steps
            {"step_id":"S_NEPH_01","procedure_id":"NEPH","step_order":1,"step_name":"Mobilize kidney"},
            {"step_id":"S_NEPH_02","procedure_id":"NEPH","step_order":2,"step_name":"Control renal vessels"},
            {"step_id":"S_NEPH_03","procedure_id":"NEPH","step_order":3,"step_name":"Remove specimen"},
        ]).to_csv(STEPS_CSV,index=False)

    if not os.path.exists(ATTENDINGS_CSV):
        pd.DataFrame([
            {"attending_id":"A_GS_SMITH","attending_name":"Dr. Alex Smith","specialty_id":"GS"},
            {"attending_id":"A_OB_JONES","attending_name":"Dr. Robin Jones","specialty_id":"OB"},
            {"attending_id":"A_URO_LEE","attending_name":"Dr. Casey Lee","specialty_id":"URO"},
        ]).to_csv(ATTENDINGS_CSV,index=False)

    if not os.path.exists(RESIDENTS_CSV):
        pd.DataFrame(columns=["email","name","created_at"]).to_csv(RESIDENTS_CSV,index=False)

    if not os.path.exists(CASES_CSV):
        pd.DataFrame(columns=["case_id","resident_email","date","specialty_id","procedure_id","attending_id","notes"]).to_csv(CASES_CSV,index=False)

    if not os.path.exists(SCORES_CSV):
        pd.DataFrame(columns=[
            "case_id",
            "step_id",
            "rating",
            "rating_num",
            "case_complexity",
            "overall_performance"
        ]).to_csv(SCORES_CSV, index=False)

def load_refs():
    """Load reference data from CSVs into DataFrames."""
    return (
        pd.read_csv(SPECIALTIES_CSV),
        pd.read_csv(PROCEDURES_CSV),
        pd.read_csv(STEPS_CSV),
        pd.read_csv(ATTENDINGS_CSV),
    )

def ensure_resident(email, name=""):
    """Add a resident to residents.csv if not already present."""
    res = pd.read_csv(RESIDENTS_CSV)
    if not (res["email"] == email).any():
        res.loc[len(res)] = {
            "email": email,
            "name": name,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        res.to_csv(RESIDENTS_CSV, index=False)

def save_case(
    resident_email,
    date,
    specialty_id,
    procedure_id,
    attending_id,
    scores_dict,
    notes="",
    case_complexity=None,
    overall_performance=None
):
    case_id = uuid.uuid4().hex[:12]
    cases = pd.read_csv(CASES_CSV)

    # Ensure new columns exist
    if "case_complexity" not in cases.columns:
        cases["case_complexity"] = None
    if "overall_performance" not in cases.columns:
        cases["overall_performance"] = None

    cases.loc[len(cases)] = {
        "case_id": case_id,
        "resident_email": resident_email,
        "date": str(date),
        "specialty_id": specialty_id,
        "procedure_id": procedure_id,
        "attending_id": attending_id,
        "notes": notes,
        "case_complexity": case_complexity,
        "overall_performance": overall_performance,
    }
    cases.to_csv(CASES_CSV, index=False)

    # Save scores (include complexity + performance with each row)
    scores = pd.read_csv(SCORES_CSV)
    for step_id, rating in scores_dict.items():
        scores.loc[len(scores)] = {
            "case_id": case_id,
            "step_id": step_id,
            "rating": rating,
            "rating_num": RATING_TO_NUM.get(rating, None),
            "case_complexity": case_complexity,
            "overall_performance": overall_performance,
        }
    scores.to_csv(SCORES_CSV, index=False)

    return case_id

    

def style_df(df, col):
    """Apply color styling to a dataframe column based on rating."""
    return df.style.applymap(lambda v: RATING_COLOR.get(v, ""), subset=[col])
    

# -----------------------------
# NAV HELPERS
# -----------------------------
def go_next(page):
    st.session_state["page"] = page
    st.rerun()

def go_back(page):
    st.session_state["page"] = page
    st.rerun()

# -----------------------------
# SESSION STATE
# -----------------------------
bootstrap_reference_data()
if "page" not in st.session_state: st.session_state["page"] = "login"
if "user_email" not in st.session_state: st.session_state["user_email"] = None
if "user_name" not in st.session_state: st.session_state["user_name"] = ""
if "scores" not in st.session_state: st.session_state["scores"] = {}
if "date" not in st.session_state: st.session_state["date"] = datetime.date.today()
if "notes" not in st.session_state: st.session_state["notes"] = ""
if "current_case_id" not in st.session_state: st.session_state["current_case_id"] = None

# -----------------------------
# SIDEBAR
# -----------------------------
if st.session_state["user_email"] in ADMINS:
    if st.sidebar.button("Admin Panel"):
        go_next("admin")

# -----------------------------
# -------------------
# PAGE: LOGIN
# -------------------
if st.session_state["page"] == "login":
    st.title("🔑 Procedure Passport Login")

    email = st.text_input("Enter your email")

    if st.button("Login"):
        if not email:
            st.error("Please enter an email.")
        else:
            try:
                residents = pd.read_csv(RESIDENTS_CSV)
            except FileNotFoundError:
                residents = pd.DataFrame(columns=["email","name","created_at"])

            # 🔹 Only allow login if email exists
            if email in residents["email"].values or email in ADMINS:
                st.session_state["resident"] = email
                st.session_state["resident_name"] = (
                    residents.loc[residents["email"]==email,"name"].values[0]
                    if email in residents["email"].values else "Admin"
                )
                # Route admin → admin page, resident → home
                if email in ADMINS:
                    st.session_state["page"] = "admin"
                else:
                    st.session_state["page"] = "home"
                st.rerun()
            else:
                st.error("❌ Email not recognized. Contact an admin to be added.")

# -------------------
# PAGE: ADMIN PANEL
# -------------------
elif st.session_state["page"] == "admin":
    st.title("⚙️ Admin Panel")

    st.subheader("Residents")
    residents = pd.read_csv(RESIDENTS_CSV)
    st.dataframe(residents)

    new_res_email = st.text_input("New resident email")
    new_res_name = st.text_input("Resident name")
    if st.button("Add resident"):
        if new_res_email:
            ensure_resident(new_res_email, new_res_name)
            st.success(f"Added {new_res_email}")
            st.rerun()

    if not residents.empty:
        del_res_email = st.selectbox("Select resident to delete", residents["email"])
        if st.button("Delete selected resident"):
            residents = residents[residents["email"] != del_res_email]
            residents.to_csv(RESIDENTS_CSV,index=False)
            st.success(f"Deleted {del_res_email}")
            st.rerun()

    st.subheader("Attendings")
    attendings = pd.read_csv(ATTENDINGS_CSV)
    st.dataframe(attendings)

    spec_df, _, _, _ = load_refs()
    new_att_name = st.text_input("New attending name")
    new_att_spec = st.selectbox("Specialty for new attending", spec_df["specialty_name"])
    if st.button("Add attending"):
        spec_id = spec_df.loc[spec_df["specialty_name"]==new_att_spec,"specialty_id"].values[0]
        new_att_id = "A_" + spec_id + "_" + new_att_name.replace(" ","_").upper()
        attendings.loc[len(attendings)] = {"attending_id":new_att_id,"attending_name":new_att_name,"specialty_id":spec_id}
        attendings.to_csv(ATTENDINGS_CSV,index=False)
        st.success(f"Added {new_att_name}")
        st.rerun()

    if not attendings.empty:
        del_att = st.selectbox("Select attending to delete", attendings["attending_name"])
        if st.button("Delete selected attending"):
            attendings = attendings[attendings["attending_name"] != del_att]
            attendings.to_csv(ATTENDINGS_CSV,index=False)
            st.success(f"Deleted {del_att}")
            st.rerun()

    st.subheader("Add New Procedure")
    new_proc_id = st.text_input("Procedure ID (short code, e.g., CSEC)").upper()
    new_proc_name = st.text_input("Procedure Name (e.g., Cesarean Section)")
    new_proc_spec = st.selectbox("Specialty for new procedure", spec_df["specialty_name"])

    steps_input = st.text_area("Steps (one per line)")
    new_proc_steps = [s.strip() for s in steps_input.split("\n") if s.strip()]

    if st.button("Add Procedure"):
        if new_proc_id and new_proc_name and new_proc_steps:
            proc_df = pd.read_csv(PROCEDURES_CSV)
            steps_df = pd.read_csv(STEPS_CSV)
            spec_id = spec_df.loc[spec_df["specialty_name"]==new_proc_spec,"specialty_id"].values[0]

            # Add procedure
            if new_proc_id not in proc_df["procedure_id"].values:
                new_proc = pd.DataFrame([{
                    "procedure_id": new_proc_id,
                    "procedure_name": new_proc_name,
                    "specialty_id": spec_id
                }])
                proc_df = pd.concat([proc_df, new_proc], ignore_index=True)
                proc_df.to_csv(PROCEDURES_CSV, index=False)

            # Add steps
            if not (steps_df["procedure_id"] == new_proc_id).any():
                new_steps = pd.DataFrame([
                    {"step_id": f"S_{new_proc_id}_{i+1:02d}", "procedure_id": new_proc_id, "step_order": i+1, "step_name": step}
                    for i, step in enumerate(new_proc_steps)
                ])
                steps_df = pd.concat([steps_df, new_steps], ignore_index=True)
                steps_df.to_csv(STEPS_CSV, index=False)

            st.success(f"✅ Added procedure {new_proc_name} ({new_proc_id})")
            st.rerun()
        else:
            st.error("Please fill in all fields and steps")

    if st.button("⬅️ Back to Login"):
        go_back("login")
          

    # -------------------
    # Navigation
    # -------------------
    if st.button("← Back to Start"):
        go_back("start")
    
# -------------------
# PAGE: HOME (Resident landing page)
# -------------------
elif st.session_state["page"] == "home":
    st.title("🏠 Resident Home")

    st.markdown(f"**Logged in as:** {st.session_state['resident_name']} ({st.session_state['resident']})")

    st.write("Welcome to your Procedure Passport. Choose what you’d like to do:")

    if st.button("➕ Start New Assessment"):
        go_next("start")

    if st.button("📊 View My Cumulative Dashboard"):
        go_next("cumulative")

    if st.button("🚪 Logout"):
        st.session_state["resident"] = None
        st.session_state["resident_name"] = ""
        st.session_state["page"] = "login"
        st.rerun()
# -----------------------------
# PAGE: START CASE
# -----------------------------
elif st.session_state["page"] == "start":
    st.title("Start Assessment")
    spec_df, proc_df, steps_df, atnd_df = load_refs()

    spec_map = dict(zip(spec_df["specialty_name"], spec_df["specialty_id"]))
    specialty = st.selectbox("Specialty", list(spec_map.keys()))
    st.session_state["specialty_id"] = spec_map[specialty]

    procs = proc_df[proc_df["specialty_id"]==st.session_state["specialty_id"]]
    proc_map = dict(zip(procs["procedure_name"], procs["procedure_id"]))
    procedure = st.selectbox("Procedure", list(proc_map.keys()))
    st.session_state["procedure_id"] = proc_map[procedure]

    atnds = atnd_df[atnd_df["specialty_id"]==st.session_state["specialty_id"]]
    atnd_map = dict(zip(atnds["attending_name"], atnds["attending_id"]))
    attending = st.selectbox("Attending", list(atnd_map.keys()))
    st.session_state["attending_id"] = atnd_map[attending]

    st.session_state["date"] = st.date_input("Date", st.session_state["date"])

    if st.button("← Back to Login"):
        go_back("login")

    if st.button("Start Assessment →"):
        st.session_state["scores"] = {}
        st.session_state["notes"] = ""
        go_next("assessment")

# -----------------------------
# PAGE: ASSESSMENT
# -----------------------------
elif st.session_state["page"] == "assessment":
    _, _, steps_df, _ = load_refs()
    steps = steps_df[steps_df["procedure_id"]==st.session_state["procedure_id"]].sort_values("step_order")

    st.title("Assessment")

    # Step ratings
    for _, row in steps.iterrows():
        step_id = row["step_id"]
        step_name = row["step_name"]
        st.session_state["scores"][step_id] = st.radio(
            step_name,
            RATING_OPTIONS,
            horizontal=True,
            key=f"score_{step_id}"
        )

    # Case Complexity dropdown
    st.session_state["case_complexity"] = st.selectbox(
        "Case Complexity",
        ["Straight Forward", "Moderate", "Complex"],
        index=["Straight Forward", "Moderate", "Complex"].index(st.session_state.get("case_complexity","Straight Forward"))
    )

    # Overall Performance O-Score
    st.session_state["overall_performance"] = st.radio(
        "Overall Performance (O-Score)",
        ["1 - Not Yet", "2 - Steer", "3 - Prompt", "4 - Backup", "5 - Auto"],
        horizontal=True,
        index=["1 - Not Yet", "2 - Steer", "3 - Prompt", "4 - Backup", "5 - Auto"].index(st.session_state.get("overall_performance","3 - Prompt"))
    )

    # Comments section
    st.session_state["notes"] = st.text_area("Comments / Feedback")

    if st.button("← Back to Start"):
        go_back("start")

    if st.button("Finish →"):
        st.session_state["current_case_id"] = save_case(
            st.session_state["resident"],
            st.session_state["date"],
            st.session_state["specialty_id"],
            st.session_state["procedure_id"],
            st.session_state["attending_id"],
            st.session_state["scores"],
            case_complexity=st.session_state["case_complexity"],
            overall_performance=st.session_state["overall_performance"],
            notes=st.session_state.get("notes","")
        )
        go_next("dashboard")

# -----------------------------
# PAGE: CASE DASHBOARD
# -----------------------------
elif st.session_state["page"] == "dashboard":
    _, _, steps_df, _ = load_refs()
    steps = steps_df[steps_df["procedure_id"]==st.session_state["procedure_id"]].sort_values("step_order")

    st.title("Case Dashboard")
    data = []
    for _, row in steps.iterrows():
        step_id = row["step_id"]
        step_name = row["step_name"]
        rating = st.session_state["scores"].get(step_id, "")
        data.append({"Step": step_name, "Rating": rating})
    df = pd.DataFrame(data)
    st.dataframe(style_df(df,"Rating"))

    if st.session_state.get("notes",""):
        st.write("**Comments:**")
        st.info(st.session_state["notes"])

    if st.button("← Back to Assessment"):
        go_back("assessment")

    if st.button("View My Cumulative Dashboard →"):
        go_next("cumulative")

# -------------------
# Page: Cumulative Dashboard
# -------------------
elif st.session_state["page"] == "cumulative":
    st.title("📊 Cumulative Dashboard")

    resident = st.session_state.get("resident")
    if not resident:
        st.error("⚠️ No resident logged in. Please log in first.")
        if st.button("⬅️ Back to Home"):
            st.session_state["page"] = "home"
            st.rerun()
    else:
        # Load data
        cases_df = pd.read_csv(CASES_CSV)
        scores_df = pd.read_csv(SCORES_CSV)
        steps_df = pd.read_csv(STEPS_CSV)
        procs_df = pd.read_csv(PROCEDURES_CSV)
        atnds_df = pd.read_csv(ATTENDINGS_CSV)

        # Ensure new columns exist (for older CSVs created before the update)
        for col in ["case_complexity", "overall_performance"]:
            if col not in scores_df.columns:
                scores_df[col] = pd.NA
        # Filter cases for this resident
        res_cases = cases_df[cases_df["resident_email"] == resident]
        if res_cases.empty:
            st.info("No cases logged yet.")
            if st.button("⬅️ Back to Home"):
                st.session_state["page"] = "home"
                st.rerun()
        else:
            # --- Prepare small, clearly named slices to avoid column collisions ---
            res_cases_small = res_cases[["case_id", "date", "procedure_id", "attending_id"]].rename(
                columns={"procedure_id": "case_procedure_id"}
            )
            steps_small = steps_df[["step_id", "procedure_id", "step_name", "step_order"]].rename(
                columns={"procedure_id": "step_procedure_id"}
            )
            atnds_small = atnds_df[["attending_id", "attending_name"]]
            procs_map = procs_df.set_index("procedure_id")["procedure_name"].to_dict()

            # --- Safe merges (keep complexity + performance) ---
            merged = (
                scores_df[["case_id", "step_id", "rating", "rating_num", "case_complexity", "overall_performance"]]
                .merge(res_cases_small, on="case_id", how="inner")
                .merge(steps_small, on="step_id", how="left")
                .merge(atnds_small, on="attending_id", how="left")
            )

            if merged.empty:
                st.info("No assessment items yet.")
                if st.button("⬅️ Back to Home"):
                    st.session_state["page"] = "home"
                    st.rerun()
            else:
                # --- Choose which procedure's cumulative view to show ---
                proc_ids = merged["case_procedure_id"].dropna().unique()
                selected_proc = st.selectbox(
                    "Select a procedure to view",
                    options=list(proc_ids),
                    format_func=lambda x: procs_map.get(x, x)
                )

                # Filter to selected procedure
                proc_data = merged[merged["case_procedure_id"] == selected_proc]

                # Respect the defined step order for that procedure
                ordered_steps = (
                    steps_df[steps_df["procedure_id"] == selected_proc]
                    .sort_values("step_order")["step_name"]
                    .tolist()
                )

                # Pivot: each case per row, steps as columns + complexity/performance
                pivot = proc_data.pivot_table(
                    index=["date", "attending_name", "case_id", "case_complexity", "overall_performance"],
                    columns="step_name",
                    values="rating",
                    aggfunc="first"
                ).reset_index()

                # Reorder the columns to match step order
                cols = ["date", "attending_name", "case_id", "case_complexity", "overall_performance"] + ordered_steps
                for c in ordered_steps:
                    if c not in pivot.columns:
                        pivot[c] = pd.NA
                pivot = pivot[cols]

                # Color map for on-screen heatmap (steps only)
                def color_map(val):
                    if val == "Not Done":
                        return "background-color: lightgray; color: black"
                    elif val == "Not Yet":
                        return "background-color: red; color: white"
                    elif val == "Steer":
                        return "background-color: orange; color: black"
                    elif val == "Prompt":
                        return "background-color: gold; color: black"
                    elif val == "Back up":
                        return "background-color: lightgreen; color: black"
                    elif val == "Auto":
                        return "background-color: green; color: white"
                    return ""

                st.dataframe(pivot.style.applymap(color_map, subset=ordered_steps), use_container_width=True)

                # --- Export to Excel with colors ---
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    pivot.to_excel(writer, index=False, sheet_name="Cumulative")
                    ws = writer.sheets["Cumulative"]

                    from openpyxl.styles import PatternFill, Font
                    fill_map = {
                        "Not Done": PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid"),
                        "Not Yet": PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid"),
                        "Steer": PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid"),
                        "Prompt": PatternFill(start_color="FFD700", end_color="FFD700", fill_type="solid"),
                        "Back up": PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid"),
                        "Auto": PatternFill(start_color="008000", end_color="008000", fill_type="solid"),
                    }

                    # Only color step columns, not metadata columns
                    start_col = 6  # Excel columns A=1, so metadata=5 cols → steps start at col 6
                    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=start_col, max_col=5+len(ordered_steps)):
                        for cell in row:
                            if cell.value in fill_map:
                                cell.fill = fill_map[cell.value]
                                cell.font = Font(color="FFFFFF") if cell.value in ["Not Yet", "Auto"] else Font(color="000000")

                excel_data = output.getvalue()
                st.download_button(
                    label=f"📥 Download {procs_map.get(selected_proc, selected_proc)} Cumulative Excel",
                    data=excel_data,
                    file_name=f"{resident}_{selected_proc}_cumulative.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                if st.button("⬅️ Back to Home"):
                    st.session_state["page"] = "home"
                    st.rerun()
              

                   
           
