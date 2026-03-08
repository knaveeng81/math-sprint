import streamlit as st
import time
import random
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- 1. GLOBAL CONFIGURATION ---
NUM_PROBLEMS = 2
SHEET_NAME = "Math Sprint Progress"

st.set_page_config(page_title="Math Sprint Mastery", layout="wide")

# --- 2. GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def get_gsheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(creds)
    return client

def get_or_create_worksheet(client, spreadsheet_id):
    sh = client.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet("Progress")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="Progress", rows=1000, cols=5)
        ws.append_row(["Timestamp", "Student", "Mode", "Time_Seconds", "Score"])
    return ws

def log_result(student_name, mode, elapsed, score):
    try:
        client = get_gsheet()
        spreadsheet_id = st.secrets["spreadsheet_id"]
        ws = get_or_create_worksheet(client, spreadsheet_id)
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            student_name,
            mode,
            elapsed,
            score
        ])
        return True
    except Exception as e:
        st.warning(f"Could not save to Google Sheets: {e}")
        return False

@st.cache_data(ttl=30)
def load_leaderboard(spreadsheet_id):
    try:
        client = get_gsheet()
        ws = get_or_create_worksheet(client, spreadsheet_id)
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["Time_Seconds"] = pd.to_numeric(df["Time_Seconds"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

# --- 3. PROBLEM GENERATORS ---
def generate_problems(mode, count):
    problems = []
    for i in range(count):
        current_mode = mode
        if mode == "Mixed Review":
            current_mode = random.choice(["Addition (Vertical)", "Subtraction (Borrowing)", "Multiplication (Tables)"])

        if current_mode == "Addition (Vertical)":
            a, b = random.randint(11, 99), random.randint(11, 99)
            problems.append({"a": a, "b": b, "ans": a + b, "op": "+", "style": "vertical", "mode": "Addition"})

        elif current_mode == "Subtraction (Borrowing)":
            a = random.randint(51, 99)
            a_units = a % 10
            b_units = random.randint(a_units + 1, 9) if a_units < 9 else 9
            b_tens = random.randint(1, (a // 10) - 1)
            b = (b_tens * 10) + b_units
            problems.append({"a": a, "b": b, "ans": a - b, "op": "-", "style": "vertical", "mode": "Subtraction"})

        elif current_mode == "Multiplication (Tables)":
            a, b = random.randint(2, 12), random.randint(2, 12)
            problems.append({"a": a, "b": b, "ans": a * b, "op": "×", "style": "horizontal", "mode": "Multiplication"})

        else:
            a, b = random.randint(10, 50), random.randint(10, 50)
            problems.append({"a": a, "b": b, "ans": a + b, "op": "+", "style": "horizontal", "mode": "Simple"})
    return problems

# --- 4. SESSION STATE ---
for key, default in [
    ("problems", None),
    ("start_time", None),
    ("sprint_id", 0),
    ("last_result", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# --- 5. SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("⚙️ Practice Settings")

    student_name = st.text_input("👤 Your Name", placeholder="Enter your name...")

    practice_mode = st.selectbox("Choose Problem Type:",
                        ["Addition (Vertical)", "Subtraction (Borrowing)", "Multiplication (Tables)", "Mixed Review"])

    start_disabled = not student_name.strip()
    if st.button("🏁 START NEW SPRINT", disabled=start_disabled):
        st.session_state.problems = generate_problems(practice_mode, NUM_PROBLEMS)
        st.session_state.start_time = time.time()
        st.session_state.sprint_id += 1
        st.session_state.last_result = None
        st.rerun()

    if start_disabled:
        st.caption("⬆️ Enter your name to start!")

    st.divider()

    # --- LEADERBOARD IN SIDEBAR ---
    st.subheader("🏆 Leaderboard")
    try:
        spreadsheet_id = st.secrets["spreadsheet_id"]
        lb_df = load_leaderboard(spreadsheet_id)
        if not lb_df.empty and "Student" in lb_df.columns:
            # Best time per student for the selected mode
            mode_label = practice_mode.split(" (")[0] if "(" in practice_mode else practice_mode
            filtered = lb_df[lb_df["Score"] == NUM_PROBLEMS]
            if not filtered.empty:
                best = (
                    filtered[filtered["Mode"].str.contains(mode_label, na=False)]
                    .groupby("Student")["Time_Seconds"]
                    .min()
                    .sort_values()
                    .reset_index()
                    .head(10)
                )
                best.columns = ["Student", "Best Time (s)"]
                best.index = best.index + 1
                st.dataframe(best, use_container_width=True)
            else:
                st.caption("No perfect scores yet — be the first! 🌟")
        else:
            st.caption("No data yet.")
    except Exception:
        st.caption("Connect Google Sheets to see leaderboard.")

# --- 6. MAIN WORKSHEET UI ---
st.title(f"⚡ {practice_mode} Sprint")

if st.session_state.last_result:
    r = st.session_state.last_result
    if r["perfect"]:
        st.success(f"🏆 PERFECT SCORE, {r['name']}! Time: {r['elapsed']}s — saved to leaderboard!")
    else:
        st.error(f"❌ Score: {r['score']}/{NUM_PROBLEMS}. Finish all correctly to save your time!")

if st.session_state.problems:
    with st.form(f"worksheet_{st.session_state.sprint_id}"):
        cols = st.columns(5)
        user_answers = []

        for i, prob in enumerate(st.session_state.problems):
            with cols[i % 5]:
                st.markdown(f"**Q{i+1}**")

                if prob["style"] == "vertical":
                    st.markdown(f"""
                    <div style="font-family: monospace; font-size: 32px; text-align: right;
                                border: 2px solid #f0f2f6; padding: 15px; border-radius: 10px;
                                background-color: white; margin-bottom: 10px; color: #1f1f1f;">
                        <div style="color: #ccc; font-size: 16px; text-align: left; margin-bottom: -15px;">[ ]</div>
                        {prob['a']}<br>
                        <span style="border-bottom: 3px solid #1f1f1f; display: block;">{prob['op']} {prob['b']}</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"<h2 style='text-align: center;'>{prob['a']} {prob['op']} {prob['b']} = </h2>", unsafe_allow_html=True)

                ans = st.number_input(f"Ans_{i}", label_visibility="collapsed", step=1, value=None,
                                      key=f"input_{st.session_state.sprint_id}_{i}")
                user_answers.append(ans)
                st.write("---")

        submit = st.form_submit_button(f"🚀 SUBMIT {NUM_PROBLEMS} ANSWERS", use_container_width=True)

    # --- 7. SCORING & GOOGLE SHEETS SAVE ---
    if submit:
        elapsed = round(time.time() - st.session_state.start_time, 2)
        correct_count = sum(1 for i, p in enumerate(st.session_state.problems) if user_answers[i] == p["ans"])
        is_perfect = correct_count == NUM_PROBLEMS
        name = student_name.strip() or "Anonymous"

        if is_perfect:
            st.balloons()
            log_result(name, practice_mode, elapsed, correct_count)
            load_leaderboard.clear()  # Bust cache so leaderboard refreshes

        st.session_state.last_result = {
            "perfect": is_perfect,
            "name": name,
            "elapsed": elapsed,
            "score": correct_count,
        }
        st.rerun()

else:
    st.info("👈 Enter your name and press **START NEW SPRINT** to begin!")

# --- 8. PROGRESS CHART ---
try:
    spreadsheet_id = st.secrets["spreadsheet_id"]
    history = load_leaderboard(spreadsheet_id)
    name = student_name.strip() if student_name.strip() else None
    if not history.empty and name:
        student_history = history[
            (history["Student"] == name) &
            (history["Mode"] == practice_mode) &
            (history["Score"] == NUM_PROBLEMS)
        ]
        if not student_history.empty:
            st.divider()
            st.subheader(f"📈 Your {practice_mode} Progress, {name}")
            st.line_chart(student_history.set_index("Timestamp")["Time_Seconds"])
except Exception:
    pass
