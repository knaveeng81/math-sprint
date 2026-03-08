import streamlit as st
import time
import random
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- 1. GLOBAL CONFIGURATION ---
NUM_PROBLEMS = 2

st.set_page_config(page_title="Math Sprint Mastery", layout="wide")

# --- 2. SUPABASE CONNECTION ---
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    return create_client(url, key)

def log_result(student_name, mode, elapsed, score):
    """Insert one row into the progress table. Returns (success, error)."""
    try:
        sb = get_supabase()
        sb.table("math_progress").insert({
            "timestamp": datetime.now().isoformat(),
            "student":   student_name,
            "mode":      mode,
            "time_seconds": elapsed,
            "score":     score,
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)

@st.cache_data(ttl=30)
def load_leaderboard():
    try:
        sb = get_supabase()
        resp = sb.table("math_progress").select("*").execute()
        if not resp.data:
            return pd.DataFrame()
        df = pd.DataFrame(resp.data)
        df["time_seconds"] = pd.to_numeric(df["time_seconds"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

# --- 3. CONNECTION DEBUG PANEL ---
with st.expander("🔧 Supabase Connection Check (hide once working)", expanded=False):
    if st.button("Run connection test"):
        steps = []
        all_ok = True

        # Step 1: secrets present?
        try:
            _ = st.secrets["supabase_url"]
            _ = st.secrets["supabase_key"]
            steps.append(("✅", "Secrets found: supabase_url and supabase_key"))
        except KeyError as e:
            steps.append(("❌", f"Missing secret: {e}"))
            all_ok = False

        # Step 2: can we connect?
        if all_ok:
            try:
                sb = get_supabase()
                steps.append(("✅", "Supabase client created successfully"))
            except Exception as e:
                steps.append(("❌", f"Connection failed: {e}"))
                all_ok = False

        # Step 3: can we read the table?
        if all_ok:
            try:
                sb = get_supabase()
                resp = sb.table("math_progress").select("*").limit(1).execute()
                steps.append(("✅", "Table 'math_progress' found and readable"))
            except Exception as e:
                steps.append(("❌", f"Table read failed (did you create the table?): {e}"))
                all_ok = False

        # Step 4: can we write a test row?
        if all_ok:
            try:
                sb = get_supabase()
                sb.table("math_progress").insert({
                    "timestamp":    datetime.now().isoformat(),
                    "student":      "CONNECTION_TEST",
                    "mode":         "Test",
                    "time_seconds": 0,
                    "score":        0,
                }).execute()
                steps.append(("✅", "Test row written successfully!"))
            except Exception as e:
                steps.append(("❌", f"Write failed: {e}"))
                all_ok = False

        for icon, msg in steps:
            st.write(f"{icon} {msg}")

        if all_ok:
            st.success("All checks passed! You can now hide this panel.")
            st.caption("💡 Delete the CONNECTION_TEST row from your Supabase dashboard.")

# --- 4. PROBLEM GENERATORS ---
def generate_problems(mode, count):
    problems = []
    for _ in range(count):
        current_mode = mode
        if mode == "Mixed Review":
            current_mode = random.choice([
                "Addition (Vertical)", "Subtraction (Borrowing)", "Multiplication (Tables)"
            ])

        if current_mode == "Addition (Vertical)":
            a, b = random.randint(11, 99), random.randint(11, 99)
            problems.append({"a": a, "b": b, "ans": a + b, "op": "+", "style": "vertical"})

        elif current_mode == "Subtraction (Borrowing)":
            a = random.randint(51, 99)
            a_units = a % 10
            b_units = random.randint(a_units + 1, 9) if a_units < 9 else 9
            b_tens  = random.randint(1, (a // 10) - 1)
            b = (b_tens * 10) + b_units
            problems.append({"a": a, "b": b, "ans": a - b, "op": "-", "style": "vertical"})

        elif current_mode == "Multiplication (Tables)":
            a, b = random.randint(2, 12), random.randint(2, 12)
            problems.append({"a": a, "b": b, "ans": a * b, "op": "×", "style": "horizontal"})

        else:
            a, b = random.randint(10, 50), random.randint(10, 50)
            problems.append({"a": a, "b": b, "ans": a + b, "op": "+", "style": "horizontal"})

    return problems

# --- 5. SESSION STATE ---
for key, default in [
    ("problems",    None),
    ("start_time",  None),
    ("sprint_id",   0),
    ("last_result", None),
    ("pending_log", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# --- 6. FLUSH PENDING LOG (top of every rerun, before any UI) ---
if st.session_state.pending_log:
    payload = st.session_state.pending_log
    st.session_state.pending_log = None
    success, err = log_result(
        payload["name"], payload["mode"], payload["elapsed"], payload["score"]
    )
    if success:
        load_leaderboard.clear()
    elif st.session_state.last_result:
        st.session_state.last_result["log_error"] = err

# --- 7. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Practice Settings")

    student_name = st.text_input("👤 Your Name", placeholder="Enter your name...")

    practice_mode = st.selectbox("Choose Problem Type:", [
        "Addition (Vertical)", "Subtraction (Borrowing)",
        "Multiplication (Tables)", "Mixed Review"
    ])

    start_disabled = not student_name.strip()
    if st.button("🏁 START NEW SPRINT", disabled=start_disabled):
        st.session_state.problems   = generate_problems(practice_mode, NUM_PROBLEMS)
        st.session_state.start_time = time.time()
        st.session_state.sprint_id += 1
        st.session_state.last_result = None
        st.rerun()

    if start_disabled:
        st.caption("⬆️ Enter your name to start!")

    st.divider()
    st.subheader("🏆 Leaderboard")

    try:
        lb_df = load_leaderboard()
        if not lb_df.empty and "student" in lb_df.columns:
            mode_label   = practice_mode.split(" (")[0]
            perfect_runs = lb_df[lb_df["score"] == NUM_PROBLEMS]
            mode_runs    = perfect_runs[perfect_runs["mode"].str.contains(mode_label, na=False)]
            if not mode_runs.empty:
                best = (
                    mode_runs.groupby("student")["time_seconds"]
                    .min()
                    .sort_values()
                    .reset_index()
                    .head(10)
                )
                best.columns = ["Student", "Best Time (s)"]
                best.index  += 1
                st.dataframe(best, use_container_width=True)
            else:
                st.caption("No perfect scores yet — be the first! 🌟")
        else:
            st.caption("No data yet.")
    except Exception:
        st.caption("Run the connection test above to diagnose.")

# --- 8. MAIN WORKSHEET UI ---
st.title(f"⚡ {practice_mode} Sprint")

if st.session_state.last_result:
    r = st.session_state.last_result
    if r["perfect"]:
        if r.get("log_error"):
            st.warning(f"🏆 PERFECT! But saving failed: {r['log_error']}")
        else:
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
                    st.markdown(
                        f"<h2 style='text-align: center;'>{prob['a']} {prob['op']} {prob['b']} = </h2>",
                        unsafe_allow_html=True
                    )
                ans = st.number_input(
                    f"Ans_{i}", label_visibility="collapsed", step=1, value=None,
                    key=f"input_{st.session_state.sprint_id}_{i}"
                )
                user_answers.append(ans)
                st.write("---")

        submit = st.form_submit_button(f"🚀 SUBMIT {NUM_PROBLEMS} ANSWERS", use_container_width=True)

    if submit:
        elapsed       = round(time.time() - st.session_state.start_time, 2)
        correct_count = sum(1 for i, p in enumerate(st.session_state.problems) if user_answers[i] == p["ans"])
        is_perfect    = correct_count == NUM_PROBLEMS
        name          = student_name.strip() or "Anonymous"

        st.session_state.last_result = {
            "perfect": is_perfect,
            "name":    name,
            "elapsed": elapsed,
            "score":   correct_count,
        }

        if is_perfect:
            st.balloons()
            st.session_state.pending_log = {
                "name":    name,
                "mode":    practice_mode,
                "elapsed": elapsed,
                "score":   correct_count,
            }

        st.rerun()

else:
    st.info("👈 Enter your name and press **START NEW SPRINT** to begin!")

# --- 9. PERSONAL PROGRESS CHART ---
try:
    history = load_leaderboard()
    name    = student_name.strip() or None
    if not history.empty and name:
        mine = history[
            (history["student"] == name) &
            (history["mode"]    == practice_mode) &
            (history["score"]   == NUM_PROBLEMS)
        ].copy()
        if not mine.empty:
            st.divider()
            st.subheader(f"📈 Your {practice_mode} Progress, {name}")
            st.line_chart(mine.set_index("timestamp")["time_seconds"])
except Exception:
    pass
