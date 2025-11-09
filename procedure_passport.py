import streamlit as st
import time
import pandas as pd
import uuid
import datetime
import io
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials
from streamlit.components.v1 import html

st.set_page_config(
    page_title="Procedure Passport",
    layout="wide"
)

# --- Session State Init ---
# -----------------------------
# SESSION STATE
# -----------------------------
if "page" not in st.session_state:
    st.session_state["page"] = "login"
if "resident" not in st.session_state:
    st.session_state["resident"] = None
if "resident_name" not in st.session_state:
    st.session_state["resident_name"] = ""
if "scores" not in st.session_state:
    st.session_state["scores"] = {}
if "date" not in st.session_state:
    st.session_state["date"] = datetime.date.today()
if "notes" not in st.session_state:
    st.session_state["notes"] = ""
if "current_case_id" not in st.session_state:
    st.session_state["current_case_id"] = None
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
# GOOGLE SHEET TAB NAMES
# -----------------------------
SHEET_RESIDENTS  = "residents"
SHEET_ATTENDINGS = "attendings"
SHEET_PROCEDURES = "procedures"
SHEET_STEPS      = "steps"
SHEET_CASES      = "cases"
SHEET_SCORES     = "scores"


@st.cache_data(ttl=60, show_spinner=False)
def load_refs():
    """Load reference data from Google Sheets into DataFrames (cached 60s)."""
    try:
        spec_df = read_sheet_df("specialties", expected_cols=["specialty_id", "specialty_name"])
    except Exception:
        spec_df = pd.DataFrame(columns=["specialty_id", "specialty_name"])

    try:
        proc_df = read_sheet_df("procedures", expected_cols=["procedure_id", "procedure_name", "specialty_id"])
    except Exception:
        proc_df = pd.DataFrame(columns=["procedure_id", "procedure_name", "specialty_id"])

    try:
        steps_df = read_sheet_df("steps", expected_cols=["step_id", "procedure_id", "step_order", "step_name"])
    except Exception:
        steps_df = pd.DataFrame(columns=["step_id", "procedure_id", "step_order", "step_name"])

    try:
        atnd_df = read_sheet_df("attendings", expected_cols=["attending_id", "attending_name", "specialty_id", "email"])
    except Exception:
        atnd_df = pd.DataFrame(columns=["attending_id", "attending_name", "specialty_id", "email"])

    return spec_df, proc_df, steps_df, atnd_df

def ensure_resident(email, name=""):
    """Add a resident to the residents sheet if not already present."""
    cols = ["email","name","created_at"]

    # read current residents from Google Sheets
    df = read_sheet_df("residents", expected_cols=cols)

    # if they're not already in there, append and write back
    if email not in df["email"].values:
        new_row = {
            "email": email,
            "name": name,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        write_sheet_df("residents", df)
def ensure_attending(name, specialty_id, email=""):
    """Add a new attending to the attendings sheet if not already present."""
    cols = ["attending_id", "attending_name", "specialty_id", "email"]
    df = read_sheet_df(SHEET_ATTENDINGS, expected_cols=cols)

    # Prevent duplicates by name
    if name not in df["attending_name"].values:
        att_id = "A_" + specialty_id + "_" + name.replace(" ", "_").upper()
        new_row = {
            "attending_id": att_id,
            "attending_name": name,
            "specialty_id": specialty_id,
            "email": email,
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        write_sheet_df(SHEET_ATTENDINGS, df)


def ensure_procedure(proc_id, proc_name, specialty_id, steps_list):
    """Add a new procedure and its steps to the sheets if not already present."""
    # --- PROCEDURE ---
    proc_cols = ["procedure_id", "procedure_name", "specialty_id"]
    procs_df = read_sheet_df(SHEET_PROCEDURES, expected_cols=proc_cols)

    if proc_id not in procs_df["procedure_id"].values:
        new_proc = pd.DataFrame([{
            "procedure_id": proc_id,
            "procedure_name": proc_name,
            "specialty_id": specialty_id,
        }])
        procs_df = pd.concat([procs_df, new_proc], ignore_index=True)
        write_sheet_df(SHEET_PROCEDURES, procs_df)

    # --- STEPS ---
    step_cols = ["step_id", "procedure_id", "step_order", "step_name"]
    steps_df = read_sheet_df(SHEET_STEPS, expected_cols=step_cols)

    if not (steps_df["procedure_id"] == proc_id).any():
        new_steps = pd.DataFrame([
            {
                "step_id": f"S_{proc_id}_{i+1:02d}",
                "procedure_id": proc_id,
                "step_order": i + 1,
                "step_name": step,
            }
            for i, step in enumerate(steps_list)
        ])
        steps_df = pd.concat([steps_df, new_steps], ignore_index=True)
        write_sheet_df(SHEET_STEPS, steps_df)

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
    """Save a completed case and its step scores to Google Sheets."""
    case_id = uuid.uuid4().hex[:12]

    # --- CASES SHEET ---
    case_cols = [
        "case_id",
        "resident_email",
        "date",
        "specialty_id",
        "procedure_id",
        "attending_id",
        "notes",
        "case_complexity",
        "overall_performance",
    ]
    cases_df = read_sheet_df("cases", expected_cols=case_cols)

    new_case_row = {
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

    cases_df = pd.concat([cases_df, pd.DataFrame([new_case_row])], ignore_index=True)
    write_sheet_df("cases", cases_df)

    # --- SCORES SHEET ---
    score_cols = [
        "case_id",
        "step_id",
        "rating",
        "rating_num",
        "case_complexity",
        "overall_performance",
    ]
    scores_df = read_sheet_df("scores", expected_cols=score_cols)

    new_score_rows = []
    for step_id, rating in scores_dict.items():
        new_score_rows.append({
            "case_id": case_id,
            "step_id": step_id,
            "rating": rating,
            "rating_num": RATING_TO_NUM.get(rating, None),
            "case_complexity": case_complexity,
            "overall_performance": overall_performance,
        })

    scores_df = pd.concat([scores_df, pd.DataFrame(new_score_rows)], ignore_index=True)
    write_sheet_df("scores", scores_df)

    return case_id


def style_df(df, col):
    """Apply color styling to a dataframe column based on rating."""
    return df.style.applymap(lambda v: RATING_COLOR.get(v, ""), subset=[col])
    
# -----------------------------
# GOOGLE SHEETS CONNECTION HELPER
# -----------------------------
import base64, json, gspread
from google.oauth2.service_account import Credentials

def get_gs_client():
    """Return an authorized gspread client using base64-encoded service account."""
    svc_json = json.loads(base64.b64decode(st.secrets["GOOGLE_SVC_B64"]).decode())
    creds = Credentials.from_service_account_info(
        svc_json,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)
def get_sheet(sheet_name: str):
    """Return a gspread worksheet by name, creating if missing."""
    gc = get_gs_client()
    sh = gc.open_by_key(st.secrets["GOOGLE_SHEET_KEY"])
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        # create with 100 rows, 20 cols, empty
        ws = sh.add_worksheet(title=sheet_name, rows="200", cols="20")
    return ws

@st.cache_data(ttl=60, show_spinner=False)
def read_sheet_df(sheet_name: str, expected_cols=None):
    """Cached read from Google Sheets (60s TTL)."""
    ws = get_sheet(sheet_name)
    df = get_as_dataframe(ws, evaluate_formulas=True, header=0)
    df = df.dropna(how="all")

    if df.empty and expected_cols:
        df = pd.DataFrame(columns=expected_cols)
    else:
        if expected_cols:
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = pd.NA
            df = df[expected_cols]
    return df

def write_sheet_df(sheet_name: str, df: pd.DataFrame):
    """Overwrite a worksheet with the dataframe (including headers)."""
    ws = get_sheet(sheet_name)
    ws.clear()
    set_with_dataframe(ws, df, include_index=False, include_column_header=True)
def test_google_sheets_connection():
    """Simple test to confirm connection to Google Sheets."""
    try:
        gc = get_gs_client()
        sh = gc.open_by_key(st.secrets["GOOGLE_SHEET_KEY"])
        st.success(f"✅ Connected to Google Sheet: {sh.title}")
    except Exception as e:
        st.error(f"❌ Could not connect to Google Sheets: {e}")
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
# SIDEBAR
# -----------------------------
st.sidebar.title("Procedure Passport")

if st.session_state.get("resident") in ADMINS:
    if st.sidebar.button("⚙️ Admin Panel"):
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
            # ✅ Load residents directly from Google Sheets
            residents = read_sheet_df("residents", expected_cols=["email","name","created_at"])

            # 🔹 Allow login for admins or registered residents
            if email in ADMINS:
                st.session_state["resident"] = email
                st.session_state["resident_name"] = "Admin"
                st.session_state["page"] = "admin"
                st.rerun()
            elif email in residents["email"].values:
                st.session_state["resident"] = email
                st.session_state["resident_name"] = (
                    residents.loc[residents["email"] == email, "name"].values[0]
                )
                st.session_state["page"] = "home"
                st.rerun()
            else:
                st.error("❌ Email not recognized. Contact an admin to be added.")

# -------------------
# PAGE: ADMIN PANEL
# -------------------
# -------------------
# PAGE: ADMIN PANEL
# -------------------
elif st.session_state["page"] == "admin":
    st.title("⚙️ Admin Panel")

    # Prevent reload loop
    if "reloaded" not in st.session_state:
        st.session_state["reloaded"] = False

    # Reload button (safe version)
    if st.button("🔄 Reload Google Sheet Data"):
        st.cache_data.clear()
        st.session_state["reloaded"] = True
        st.rerun()  # normal rerun

    # Only reset flag *after* reload
    if st.session_state["reloaded"]:
        st.session_state["reloaded"] = False
        st.success("✅ Data refreshed successfully!")

    # Debug marker (helps confirm the panel renders)
    st.write("✅ Admin Panel Loaded")
    # -------------------
    # Specialties Section
    # -------------------
    st.subheader("Specialties")

    specialties = read_sheet_df("specialties", expected_cols=["specialty_id", "specialty_name"])
    st.dataframe(specialties)

    new_spec_id = st.text_input("New specialty ID (short code, e.g., GS)")
    new_spec_name = st.text_input("New specialty name (e.g., General Surgery)")

    if st.button("Add Specialty"):
        if new_spec_id and new_spec_name:
            # prevent duplicates
            if new_spec_id in specialties["specialty_id"].values:
                st.warning("This specialty already exists.")
            else:
                new_row = pd.DataFrame([{
                    "specialty_id": new_spec_id,
                    "specialty_name": new_spec_name
                }])
                specialties = pd.concat([specialties, new_row], ignore_index=True)
                write_sheet_df("specialties", specialties)
                st.success(f"✅ Added specialty {new_spec_name} ({new_spec_id})")
                st.cache_data.clear()      # 🧠 clears the cached Google Sheets reads
                time.sleep(1)              # ⏳ lets Google confirm the write
                st.rerun()
        else:
            st.error("Please enter both an ID and a name for the specialty.")
    # -------------------
    # Residents Section
    # -------------------
    st.subheader("Residents")

    # Load residents from Google Sheets
    residents = read_sheet_df(SHEET_RESIDENTS, expected_cols=["email", "name", "created_at"])
    st.dataframe(residents)

    # Add new resident
    new_res_email = st.text_input("New resident email")
    new_res_name = st.text_input("Resident name")
    if st.button("Add resident"):
        if new_res_email:
            ensure_resident(new_res_email, new_res_name)
            st.success(f"Added {new_res_email}")
            st.cache_data.clear()      # 🧠 clears the cached Google Sheets reads
            time.sleep(1)              # ⏳ lets Google confirm the write
            st.rerun()    # 🔁 clean restart of the app

    # Delete resident
    if not residents.empty:
        del_res_email = st.selectbox("Select resident to delete", residents["email"])
        if st.button("Delete selected resident"):
            updated = residents[residents["email"] != del_res_email].reset_index(drop=True)
            write_sheet_df(SHEET_RESIDENTS, updated)
            st.success(f"Deleted {del_res_email}")
            st.cache_data.clear()      # 🧠 clears the cached Google Sheets reads
            time.sleep(1)              # ⏳ lets Google confirm the write
            st.rerun()    # 🔁 clean restart of the app

    st.markdown("---")

    # -------------------
    # Attendings Section
    # -------------------
    st.subheader("Attendings")

    attendings = read_sheet_df(
        SHEET_ATTENDINGS,
        expected_cols=["attending_id", "attending_name", "specialty_id", "email"]
    )
    st.dataframe(attendings)

    spec_df, _, _, _ = load_refs()
    new_att_name = st.text_input("New attending name")
    new_att_spec = st.selectbox("Specialty for new attending", spec_df["specialty_name"])
    new_att_email = st.text_input("Attending email (optional)")

    if st.button("Add attending"):
        if new_att_name:
            spec_id = spec_df.loc[
                spec_df["specialty_name"] == new_att_spec, "specialty_id"
            ].values[0]
            ensure_attending(new_att_name, spec_id, new_att_email)
            st.success(f"Added {new_att_name}")
            st.cache_data.clear()      # 🧠 clears the cached Google Sheets reads
            time.sleep(1)              # ⏳ lets Google confirm the write
            st.rerun()    # 🔁 clean restart of the app
        else:
            st.error("Please enter an attending name.")

    # Delete attending
    if not attendings.empty:
        del_att = st.selectbox("Select attending to delete", attendings["attending_name"])
        if st.button("Delete selected attending"):
            updated = attendings[attendings["attending_name"] != del_att].reset_index(drop=True)
            write_sheet_df(SHEET_ATTENDINGS, updated)
            st.success(f"Deleted {del_att}")
            st.cache_data.clear()      # 🧠 clears the cached Google Sheets reads
            time.sleep(1)              # ⏳ lets Google confirm the write
            st.rerun()    # 🔁 clean restart of the app

    st.markdown("---")

    # -------------------
    # Add New Procedure Section
    # -------------------
    st.subheader("Add New Procedure")

    new_proc_id = st.text_input("Procedure ID (short code, e.g., CSEC)").upper()
    new_proc_name = st.text_input("Procedure Name (e.g., Cesarean Section)")
    new_proc_spec = st.selectbox("Specialty for new procedure", spec_df["specialty_name"])
    steps_input = st.text_area("Steps (one per line)")
    new_proc_steps = [s.strip() for s in steps_input.split("\n") if s.strip()]

    if st.button("Add Procedure"):
        if new_proc_id and new_proc_name and new_proc_steps:
            spec_id = spec_df.loc[
                spec_df["specialty_name"] == new_proc_spec, "specialty_id"
            ].values[0]
            ensure_procedure(new_proc_id, new_proc_name, spec_id, new_proc_steps)
            st.success(f"✅ Added procedure {new_proc_name} ({new_proc_id})")
            st.cache_data.clear()      # 🧠 clears the cached Google Sheets reads
            time.sleep(1)              # ⏳ lets Google confirm the write
            st.rerun()    # 🔁 clean restart of the app
        else:
            st.error("Please fill in all fields and steps.")

    st.markdown("---")
    # -------------------
    # Edit Existing Procedure Section
    # -------------------
    st.subheader("Edit Existing Procedure")

    procs_df = read_sheet_df(SHEET_PROCEDURES, expected_cols=["procedure_id", "procedure_name", "specialty_id"])
    if procs_df.empty:
        st.info("No procedures found yet.")
    else:
        edit_proc = st.selectbox("Select procedure to edit", procs_df["procedure_name"])
        selected_proc_id = procs_df.loc[procs_df["procedure_name"] == edit_proc, "procedure_id"].values[0]

        new_name = st.text_input("Updated procedure name", value=edit_proc)
        new_steps_input = st.text_area("Updated steps (one per line, leave blank to keep current steps)")
        new_steps = [s.strip() for s in new_steps_input.split("\n") if s.strip()]

        if st.button("Update Procedure"):
            # update name
            procs_df.loc[procs_df["procedure_id"] == selected_proc_id, "procedure_name"] = new_name
            write_sheet_df(SHEET_PROCEDURES, procs_df)

            # optionally update steps
            if new_steps:
                steps_df = read_sheet_df(SHEET_STEPS, expected_cols=["step_id", "procedure_id", "step_order", "step_name"])
                steps_df = steps_df[steps_df["procedure_id"] != selected_proc_id]
                updated_steps = pd.DataFrame([
                    {"step_id": f"S_{selected_proc_id}_{i+1:02d}",
                     "procedure_id": selected_proc_id,
                     "step_order": i + 1,
                     "step_name": s}
                    for i, s in enumerate(new_steps)
                ])
                steps_df = pd.concat([steps_df, updated_steps], ignore_index=True)
                write_sheet_df(SHEET_STEPS, steps_df)

            st.success(f"✅ Procedure '{new_name}' updated successfully!")
            st.cache_data.clear()      # 🧠 clears the cached Google Sheets reads
            time.sleep(1)              # ⏳ lets Google confirm the write
            st.rerun()    # 🔁 clean restart of the app
    # -------------------
    # Navigation Buttons
    # -------------------
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Back to Login"):
            go_back("login")
    with col2:
        if st.button("🏠 Go to Start Page"):
            go_next("start")
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

    if st.button("💬 View My Comments Dashboard"):
        go_next("comments")

    if st.button("🚪 Logout"):
        st.session_state["resident"] = None
        st.session_state["resident_name"] = ""
        st.session_state["page"] = "login"
        st.cache_data.clear()      # 🧠 clears the cached Google Sheets reads
        time.sleep(1)              # ⏳ lets Google confirm the write
        st.rerun()    # 🔁 clean restart of the app
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
# PAGE: COMMENTS DASHBOARD
# -------------------
elif st.session_state["page"] == "comments":
    st.title("💬 Comments Dashboard")

    resident = st.session_state.get("resident")

    if not resident:
        st.error("⚠️ No resident logged in. Please log in first.")
        if st.button("⬅️ Back to Home"):
            st.session_state["page"] = "home"
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()
    else:
        # --- Load relevant sheets ---
        cases_df = read_sheet_df(
            SHEET_CASES,
            expected_cols=[
                "case_id", "resident_email", "date", "specialty_id", "procedure_id",
                "attending_id", "notes", "case_complexity", "overall_performance"
            ]
        )
        procs_df = read_sheet_df(
            SHEET_PROCEDURES,
            expected_cols=["procedure_id", "procedure_name", "specialty_id"]
        )
        atnds_df = read_sheet_df(
            SHEET_ATTENDINGS,
            expected_cols=["attending_id", "attending_name", "specialty_id", "email"]
        )

        # --- Filter to this resident ---
        res_cases = cases_df[cases_df["resident_email"] == resident]
        if res_cases.empty:
            st.info("No comments recorded yet.")
            if st.button("⬅️ Back to Home"):
                go_next("home")
        else:
            # --- Merge in human-readable labels ---
            merged = (
                res_cases.merge(procs_df, on="procedure_id", how="left")
                         .merge(atnds_df, on="attending_id", how="left")
            )

            # --- Clean up columns ---
            merged = merged.rename(columns={
                "date": "Date",
                "procedure_name": "Procedure",
                "attending_name": "Attending",
                "case_complexity": "Case Complexity",
                "overall_performance": "Overall Performance",
                "notes": "Comments"
            })

            merged = merged[[
                "Date", "Procedure", "Attending",
                "Case Complexity", "Overall Performance", "Comments"
            ]].sort_values("Date", ascending=False)

            st.dataframe(merged, use_container_width=True)

            # --- Excel Export ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                merged.to_excel(writer, index=False, sheet_name="Comments")

            excel_data = output.getvalue()
            st.download_button(
                label="📥 Download Comments as Excel",
                data=excel_data,
                file_name=f"{resident}_comments_dashboard.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            if st.button("⬅️ Back to Home"):
                go_next("home")

# -------------------
# PAGE: Cumulative Dashboard (Google Sheets only, screenshot-friendly)
# -------------------
elif st.session_state["page"] == "cumulative":
    st.title("📊 Cumulative Dashboard")

    resident = st.session_state.get("resident")

    # --- If not logged in ---
    if not resident:
        st.error("⚠️ No resident logged in. Please log in first.")
        if st.button("⬅️ Back to Home"):
            st.session_state["page"] = "home"
            st.rerun()

    else:
        # --- Load data from Google Sheets ---
        cases_df = read_sheet_df(
            SHEET_CASES,
            expected_cols=[
                "case_id", "resident_email", "date", "specialty_id", "procedure_id",
                "attending_id", "notes", "case_complexity", "overall_performance"
            ]
        )
        scores_df = read_sheet_df(
            SHEET_SCORES,
            expected_cols=[
                "case_id", "step_id", "rating", "rating_num",
                "case_complexity", "overall_performance"
            ]
        )
        steps_df = read_sheet_df(
            SHEET_STEPS,
            expected_cols=["step_id", "procedure_id", "step_order", "step_name"]
        )
        procs_df = read_sheet_df(
            SHEET_PROCEDURES,
            expected_cols=["procedure_id", "procedure_name", "specialty_id"]
        )
        atnds_df = read_sheet_df(
            SHEET_ATTENDINGS,
            expected_cols=["attending_id", "attending_name", "specialty_id", "email"]
        )

        # --- Ensure expected columns exist ---
        for col in ["case_complexity", "overall_performance"]:
            if col not in scores_df.columns:
                scores_df[col] = pd.NA

        # --- Filter cases for this resident ---
        res_cases = cases_df[cases_df["resident_email"] == resident]
        if res_cases.empty:
            st.info("No cases logged yet.")
            if st.button("⬅️ Back to Home"):
                st.session_state["page"] = "home"
                st.rerun()
        else:
            # --- Prepare smaller tables for merging ---
            res_cases_small = res_cases[
                ["case_id", "date", "procedure_id", "attending_id"]
            ].rename(columns={"procedure_id": "case_procedure_id"})

            steps_small = steps_df[
                ["step_id", "procedure_id", "step_name", "step_order"]
            ].rename(columns={"procedure_id": "step_procedure_id"})

            atnds_small = atnds_df[["attending_id", "attending_name"]]
            procs_map = procs_df.set_index("procedure_id")["procedure_name"].to_dict()

            # --- Merge all relevant data ---
            merged = (
                scores_df[
                    ["case_id", "step_id", "rating", "rating_num",
                     "case_complexity", "overall_performance"]
                ]
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
                # --- Procedure selection dropdown ---
                proc_ids = merged["case_procedure_id"].dropna().unique()
                selected_proc = st.selectbox(
                    "Select a procedure to view",
                    options=list(proc_ids),
                    format_func=lambda x: procs_map.get(x, x)
                )

                # --- Filter to selected procedure ---
                proc_data = merged[merged["case_procedure_id"] == selected_proc]
                if proc_data.empty:
                    st.info("No cases found for this procedure yet.")
                    if st.button("⬅️ Back to Home"):
                        st.session_state["page"] = "home"
                        st.rerun()
                else:
                    # --- Pivot cases as rows, steps as columns ---
                    pivot = proc_data.pivot_table(
                        index=["date", "attending_name", "case_id",
                               "case_complexity", "overall_performance"],
                        columns="step_name",
                        values="rating",
                        aggfunc="first"
                    ).reset_index()

                    if pivot.empty:
                        st.info("No assessment items to show.")
                        if st.button("⬅️ Back to Home"):
                            st.session_state["page"] = "home"
                            st.rerun()
                    else:
                        # Sort by date so columns appear in chronological order
                        pivot = pivot.sort_values("date")

                        # --- Build screenshot-friendly matrix: cases = columns, steps = rows ---

                        # We will display everything *except* case_id.
                        screenshot_df = pivot.drop(columns=["case_id"], errors="ignore")

                        # Meta columns are fixed; everything else is a "step"
                        meta_cols = ["date", "attending_name",
                                     "case_complexity", "overall_performance"]
                        for col in meta_cols:
                            if col not in screenshot_df.columns:
                                screenshot_df[col] = ""

                        # Reorder so meta columns are first
                        all_cols = list(screenshot_df.columns)
                        step_cols = [c for c in all_cols if c not in meta_cols]
                        screenshot_df = screenshot_df[meta_cols + step_cols]

                        # Convert to records (each record = one case / column)
                        case_records = screenshot_df.to_dict("records")

                        # Helpers for CSS classes
                        def slugify_rating(val):
                            if pd.isna(val) or val == "":
                                return ""
                            return str(val).strip().lower().replace(" ", "-")

                        def complexity_class(val):
                            if pd.isna(val) or val == "":
                                return ""
                            slug = str(val).strip().lower().replace(" ", "-")
                            return f"complexity-{slug}"

                        def o_score_class(val):
                            if pd.isna(val) or val == "":
                                return ""
                            # Expect "3 - Prompt" → "3"
                            try:
                                num = int(str(val).split("-")[0].strip())
                                return f"o-{num}"
                            except Exception:
                                return ""

                        # --- Build HTML + CSS table ---
                        css = """
                        <style>
                        .cum-wrapper {
                            overflow-x: auto;
                            padding: 0.5rem;
                        }
                        .cum-table {
                            border-collapse: collapse;
                            font-size: 0.75rem;
                            table-layout: fixed;
                        }
                        .cum-table th, .cum-table td {
                            border: 1px solid #ddd;
                            padding: 4px;
                        }
                        .cum-table thead th {
                            background: #f5f5f5;
                        }
                        .corner-cell {
                            background: #ffffff;
                            border: none;
                            min-width: 180px;
                        }
                        .case-header {
                            min-width: 110px;
                            max-width: 130px;
                            text-align: center;
                            vertical-align: bottom;
                            white-space: normal;
                            word-wrap: break-word;
                        }
                        .case-date {
                            font-weight: 600;
                            font-size: 0.7rem;
                        }
                        .case-attending {
                            font-size: 0.7rem;
                        }
                        .row-header {
                            text-align: left;
                            vertical-align: top;
                            min-width: 220px;
                            max-width: 260px;
                            white-space: normal;
                            word-wrap: break-word;
                            font-size: 0.7rem;
                        }
                        .meta-row-label {
                            font-weight: 600;
                            text-align: left;
                            font-size: 0.7rem;
                        }
                        .meta-cell {
                            text-align: center;
                            height: 18px;
                        }
                        .step-cell {
                            width: 24px;
                            height: 18px;
                        }

                        /* Rating colors (no text needed, just the colored blocks) */
                        .rating-not-done {
                            background-color: #bfbfbf;
                        }
                        .rating-not-yet {
                            background-color: #ff4d4d;
                        }
                        .rating-steer {
                            background-color: #ff944d;
                        }
                        .rating-prompt {
                            background-color: #ffd633;
                        }
                        .rating-back-up {
                            background-color: #99e699;
                        }
                        .rating-auto {
                            background-color: #33cc33;
                        }

                        /* Make the extremes high-contrast */
                        .rating-not-yet,
                        .rating-auto {
                            color: #ffffff;
                        }

                        /* Case complexity colors */
                        .complexity-straight-forward {
                            background-color: #d9ead3;
                        }
                        .complexity-moderate {
                            background-color: #ffe599;
                        }
                        .complexity-complex {
                            background-color: #f4cccc;
                        }

                        /* O-score colors (1–5) */
                        .o-1 { background-color: #ff4d4d; color: #ffffff; }
                        .o-2 { background-color: #ff944d; color: #000000; }
                        .o-3 { background-color: #ffd633; color: #000000; }
                        .o-4 { background-color: #99e699; color: #000000; }
                        .o-5 { background-color: #33cc33; color: #ffffff; }

                        /* Make the whole thing screenshot-friendly */
                        .cum-table td, .cum-table th {
                            padding: 2px;
                        }
                        </style>
                        """

                        table_html = css
                        table_html += '<div class="cum-wrapper">'
                        table_html += '<table class="cum-table">'

                        # --- Header row: blank corner + one column per case (date + attending) ---
                        table_html += "<thead><tr>"
                        table_html += '<th class="corner-cell"></th>'
                        for rec in case_records:
                            date_str = rec.get("date", "")
                            attending_str = rec.get("attending_name", "")
                            table_html += (
                                '<th class="case-header">'
                                f'<div class="case-date">{date_str}</div>'
                                f'<div class="case-attending">{attending_str}</div>'
                                '</th>'
                            )
                        table_html += "</tr></thead>"

                        # --- Body: O-score row, Complexity row, then one row per step ---
                        table_html += "<tbody>"

                        # O-score row (colored blocks only)
                        table_html += "<tr>"
                        table_html += '<th class="row-header meta-row-label">O-Score</th>'
                        for rec in case_records:
                            o_val = rec.get("overall_performance", "")
                            o_class = o_score_class(o_val)
                            table_html += f'<td class="meta-cell {o_class}">&nbsp;</td>'
                        table_html += "</tr>"

                        # Complexity row (colored blocks only)
                        table_html += "<tr>"
                        table_html += '<th class="row-header meta-row-label">Complexity</th>'
                        for rec in case_records:
                            cx_val = rec.get("case_complexity", "")
                            cx_class = complexity_class(cx_val)
                            table_html += f'<td class="meta-cell {cx_class}">&nbsp;</td>'
                        table_html += "</tr>"

                        # Step rows: one row per step, one colored cell per case
                        for step_name in step_cols:
                            safe_step = str(step_name).replace("&", "&amp;")
                            table_html += "<tr>"
                            table_html += f'<th class="row-header">{safe_step}</th>'
                            for rec in case_records:
                                rating = rec.get(step_name, "")
                                if pd.isna(rating):
                                    rating_class = ""
                                else:
                                    slug = slugify_rating(rating)
                                    rating_class = f"rating-{slug}" if slug else ""
                                table_html += f'<td class="step-cell {rating_class}">&nbsp;</td>'
                            table_html += "</tr>"

                        table_html += "</tbody></table></div>"

                        st.markdown(table_html, unsafe_allow_html=True)

                        # --- Optional: Excel export of the underlying pivot ---
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine="openpyxl") as writer:
                            pivot.to_excel(writer, index=False, sheet_name="Cumulative")
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