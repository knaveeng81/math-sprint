import streamlit as st
import streamlit.components.v1 as components
import time
import random
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- 1. GLOBAL CONFIGURATION ---
NUM_PROBLEMS = 10

st.set_page_config(page_title="Math Sprint Mastery", layout="wide")

# --- CUSTOM CSS FOR 3RD GRADE WORKSHEET LAYOUT ---
st.markdown("""
<style>
div[data-baseweb="input"] input {
    text-align: center !important;
    font-size: 1.4rem !important;
    font-weight: bold !important;
    padding: 0.2rem !important;
}
input[aria-label^="carry"] {
    font-size: 0.9rem !important;
    height: 1.8rem !important;
    color: #d9534f !important;
    background-color: #ffeaea !important;
}
input[aria-label^="ans"] {
    background-color: #f0fdf4 !important;
}
h3 {
    text-align: center;
    margin-top: 0px !important;
    margin-bottom: 0px !important;
    padding-bottom: 0px !important;
}
.wrong-box {
    border: 3px solid #d9534f;
    border-radius: 8px;
    padding: 10px;
    background-color: #fff5f5;
    margin-bottom: 15px;
}
[data-testid="column"] {
    margin-bottom: -10px;
}
</style>
""", unsafe_allow_html=True)

# --- 2. SUPABASE CONNECTION ---
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    return create_client(url, key)

def log_result(student_name, mode, elapsed, score):
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

# --- 3. PROBLEM GENERATORS ---
def generate_problems(mode, count):
    problems = []
    for _ in range(count):
        current_mode = mode
        if mode == "Mixed Review":
            current_mode = random.choice([
                "Addition (Vertical)", "Subtraction (Borrowing)", 
                "Multiplication (2-Digit)", "Long Division"
            ])

        if current_mode == "Addition (Vertical)":
            a, b = random.randint(11, 99), random.randint(11, 99)
            problems.append({"a": a, "b": b, "ans": a + b, "op": "+", "style": "addition"})

        elif current_mode == "Subtraction (Borrowing)":
            a = random.randint(51, 99)
            a_units = a % 10
            b_units = random.randint(a_units + 1, 9) if a_units < 9 else 9
            b_tens  = random.randint(1, (a // 10) - 1)
            b = (b_tens * 10) + b_units
            problems.append({"a": a, "b": b, "ans": a - b, "op": "-", "style": "subtraction"})

        elif current_mode == "Multiplication (2-Digit)":
            a, b = random.randint(11, 45), random.randint(11, 45)
            problems.append({"a": a, "b": b, "ans": a * b, "op": "×", "style": "multiplication"})
            
        elif current_mode == "Long Division":
            a = random.randint(11, 99) # Dividend (2-digit)
            b = random.randint(2, 9)   # Divisor (1-digit)
            q = a // b
            rem = a % b
            problems.append({"a": a, "b": b, "ans": q, "rem": rem, "op": "÷", "style": "division"})

    return problems

# --- 4. SESSION STATE ---
for key, default in [
    ("problems",    None),
    ("start_time",  None),
    ("sprint_id",   0),
    ("last_result", None),
    ("pending_log", None),
    ("submitted_answers", None)
]:
    if key not in st.session_state:
        st.session_state[key] = default

# --- 5. FLUSH PENDING LOG ---
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

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Practice Settings")
    student_name = st.text_input("👤 Your Name", placeholder="Enter your name...")
    practice_mode = st.selectbox("Choose Problem Type:", [
        "Addition (Vertical)", "Subtraction (Borrowing)",
        "Multiplication (2-Digit)", "Long Division", "Mixed Review"
    ])

    start_disabled = not student_name.strip()
    if st.button("🏁 START NEW SPRINT", disabled=start_disabled):
        st.session_state.problems   = generate_problems(practice_mode, NUM_PROBLEMS)
        st.session_state.start_time = time.time()
        st.session_state.sprint_id += 1 
        st.session_state.last_result = None
        st.session_state.submitted_answers = None
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
                best = mode_runs.groupby("student")["time_seconds"].min().sort_values().reset_index().head(10)
                best.columns = ["Student", "Best Time (s)"]
                best.index  += 1
                st.dataframe(best, use_container_width=True)
            else:
                st.caption("No perfect scores yet — be the first! 🌟")
    except Exception:
        pass

# --- 7. WORKSHEET RENDERING HELPERS ---
def get_digit(num, pos):
    s = str(num)
    return s[-(pos+1)] if pos < len(s) else ""

def render_addition(prob, p_idx, s_id):
    c0, c1, c2, c3, c4 = st.columns([0.5, 1, 1, 1, 2])
    with c2: st.text_input("carry", key=f"c_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c3: st.text_input("carry", key=f"c_o_{s_id}_{p_idx}", label_visibility="collapsed")
    
    c0, c1, c2, c3, c4 = st.columns([0.5, 1, 1, 1, 2])
    with c2: st.markdown(f"<h3>{get_digit(prob['a'], 1)}</h3>", unsafe_allow_html=True)
    with c3: st.markdown(f"<h3>{get_digit(prob['a'], 0)}</h3>", unsafe_allow_html=True)
    
    c0, c1, c2, c3, c4 = st.columns([0.5, 1, 1, 1, 2])
    with c0: st.markdown("<h3>+</h3>", unsafe_allow_html=True)
    with c2: st.markdown(f"<h3>{get_digit(prob['b'], 1)}</h3>", unsafe_allow_html=True)
    with c3: st.markdown(f"<h3>{get_digit(prob['b'], 0)}</h3>", unsafe_allow_html=True)
    
    st.markdown("<hr style='margin: 5px 0; border-top: 2px solid black;'>", unsafe_allow_html=True)
    
    c0, c1, c2, c3, c4 = st.columns([0.5, 1, 1, 1, 2])
    with c1: st.text_input("ans_h", key=f"ans_h_{s_id}_{p_idx}", label_visibility="collapsed")
    with c2: st.text_input("ans_t", key=f"ans_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c3: st.text_input("ans_o", key=f"ans_o_{s_id}_{p_idx}", label_visibility="collapsed")

def render_subtraction(prob, p_idx, s_id):
    c0, c1, c2, c3, c4 = st.columns([0.5, 1, 1, 1, 2])
    with c2: st.text_input("carry", key=f"c_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c3: st.text_input("carry", key=f"c_o_{s_id}_{p_idx}", label_visibility="collapsed")
    
    c0, c1, c2, c3, c4 = st.columns([0.5, 1, 1, 1, 2])
    with c2: st.markdown(f"<h3>{get_digit(prob['a'], 1)}</h3>", unsafe_allow_html=True)
    with c3: st.markdown(f"<h3>{get_digit(prob['a'], 0)}</h3>", unsafe_allow_html=True)
    
    c0, c1, c2, c3, c4 = st.columns([0.5, 1, 1, 1, 2])
    with c0: st.markdown("<h3>-</h3>", unsafe_allow_html=True)
    with c2: st.markdown(f"<h3>{get_digit(prob['b'], 1)}</h3>", unsafe_allow_html=True)
    with c3: st.markdown(f"<h3>{get_digit(prob['b'], 0)}</h3>", unsafe_allow_html=True)
    
    st.markdown("<hr style='margin: 5px 0; border-top: 2px solid black;'>", unsafe_allow_html=True)
    
    c0, c1, c2, c3, c4 = st.columns([0.5, 1, 1, 1, 2])
    with c2: st.text_input("ans_t", key=f"ans_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c3: st.text_input("ans_o", key=f"ans_o_{s_id}_{p_idx}", label_visibility="collapsed")

def render_multiplication(prob, p_idx, s_id):
    c_op, c_th, c_h, c_t, c_o, c_sp = st.columns([0.5, 1, 1, 1, 1, 1.5])
    with c_h: st.text_input("carry", key=f"c_h_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_t: st.text_input("carry", key=f"c_t_{s_id}_{p_idx}", label_visibility="collapsed")
    
    c_op, c_th, c_h, c_t, c_o, c_sp = st.columns([0.5, 1, 1, 1, 1, 1.5])
    with c_t: st.markdown(f"<h3>{get_digit(prob['a'], 1)}</h3>", unsafe_allow_html=True)
    with c_o: st.markdown(f"<h3>{get_digit(prob['a'], 0)}</h3>", unsafe_allow_html=True)
    
    c_op, c_th, c_h, c_t, c_o, c_sp = st.columns([0.5, 1, 1, 1, 1, 1.5])
    with c_op: st.markdown("<h3>×</h3>", unsafe_allow_html=True)
    with c_t: st.markdown(f"<h3>{get_digit(prob['b'], 1)}</h3>", unsafe_allow_html=True)
    with c_o: st.markdown(f"<h3>{get_digit(prob['b'], 0)}</h3>", unsafe_allow_html=True)
    
    st.markdown("<hr style='margin: 5px 0; border-top: 2px solid black;'>", unsafe_allow_html=True)
    
    c_op, c_th, c_h, c_t, c_o, c_sp = st.columns([0.5, 1, 1, 1, 1, 1.5])
    with c_h: st.text_input("p1_h", key=f"p1_h_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_t: st.text_input("p1_t", key=f"p1_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_o: st.text_input("p1_o", key=f"p1_o_{s_id}_{p_idx}", label_visibility="collapsed")
    
    c_op, c_th, c_h, c_t, c_o, c_sp = st.columns([0.5, 1, 1, 1, 1, 1.5])
    with c_th: st.text_input("p2_th", key=f"p2_th_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_h: st.text_input("p2_h", key=f"p2_h_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_t: st.text_input("p2_t", key=f"p2_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_o: st.markdown("<h3 style='color:#ccc;'>0</h3>", unsafe_allow_html=True)
    
    st.markdown("<hr style='margin: 5px 0; border-top: 2px solid black;'>", unsafe_allow_html=True)
    
    c_op, c_th, c_h, c_t, c_o, c_sp = st.columns([0.5, 1, 1, 1, 1, 1.5])
    with c_th: st.text_input("ans_th", key=f"ans_th_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_h: st.text_input("ans_h", key=f"ans_h_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_t: st.text_input("ans_t", key=f"ans_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_o: st.text_input("ans_o", key=f"ans_o_{s_id}_{p_idx}", label_visibility="collapsed")

def render_division(prob, p_idx, s_id):
    D_str = str(prob['a']).zfill(2)
    
    c_div, c_br, c_t, c_o, c_sp = st.columns([0.8, 0.4, 1, 1, 1.5])
    with c_t: st.text_input("ans_t", key=f"ans_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_o: st.text_input("ans_o", key=f"ans_o_{s_id}_{p_idx}", label_visibility="collapsed")
    
    c_div, c_br, c_t, c_o, c_sp = st.columns([0.8, 0.4, 1, 1, 1.5])
    with c_div: st.markdown(f"<h3 style='text-align:right'>{prob['b']}</h3>", unsafe_allow_html=True)
    with c_br: st.markdown("<h3 style='text-align:center'>)</h3>", unsafe_allow_html=True)
    with c_t: st.markdown(f"<h3><u style='text-decoration-thickness: 2px;'>{D_str[0]}</u></h3>", unsafe_allow_html=True)
    with c_o: st.markdown(f"<h3><u style='text-decoration-thickness: 2px;'>{D_str[1]}</u></h3>", unsafe_allow_html=True)
    
    c_div, c_br, c_t, c_o, c_sp = st.columns([0.8, 0.4, 1, 1, 1.5])
    with c_br: st.markdown("<h3 style='text-align:right'>-</h3>", unsafe_allow_html=True)
    with c_t: st.text_input("s1_t", key=f"s1_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_o: st.text_input("s1_o", key=f"s1_o_{s_id}_{p_idx}", label_visibility="collapsed")
    
    st.markdown("<hr style='margin: 5px 0; border-top: 2px solid black;'>", unsafe_allow_html=True)
    
    c_div, c_br, c_t, c_o, c_sp = st.columns([0.8, 0.4, 1, 1, 1.5])
    with c_t: st.text_input("r1_t", key=f"r1_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_o: st.text_input("r1_o", key=f"r1_o_{s_id}_{p_idx}", label_visibility="collapsed")
    
    c_div, c_br, c_t, c_o, c_sp = st.columns([0.8, 0.4, 1, 1, 1.5])
    with c_br: st.markdown("<h3 style='text-align:right'>-</h3>", unsafe_allow_html=True)
    with c_t: st.text_input("s2_t", key=f"s2_t_{s_id}_{p_idx}", label_visibility="collapsed")
    with c_o: st.text_input("s2_o", key=f"s2_o_{s_id}_{p_idx}", label_visibility="collapsed")
    
    st.markdown("<hr style='margin: 5px 0; border-top: 2px solid black;'>", unsafe_allow_html=True)
    
    c_div, c_br, c_t, c_o, c_sp = st.columns([0.8, 0.4, 1, 1, 1.5])
    with c_o: st.text_input("r2_o", key=f"r2_o_{s_id}_{p_idx}", label_visibility="collapsed")

# --- 8. LIVE TIMER COMPONENT ---
def display_live_timer(start_time_seconds):
    components.html(f"""
        <div id="stopwatch" style="font-family: Arial, sans-serif; font-size: 28px; font-weight: bold; color: #333; text-align: center; padding: 15px; border: 3px solid #ddd; border-radius: 12px; background-color: #f9f9f9; width: 160px; margin: 0 auto;">
            ⏱️ 00:00
        </div>
        <script>
            var startTime = {start_time_seconds * 1000};
            var timerEl = document.getElementById('stopwatch');
            setInterval(function() {{
                var now = Date.now();
                var elapsed = Math.floor((now - startTime) / 1000);
                var mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
                var secs = (elapsed % 60).toString().padStart(2, '0');
                timerEl.innerHTML = '⏱️ ' + mins + ':' + secs;
            }}, 1000);
        </script>
    """, height=90)

# --- 9. MAIN UI ---
st.title(f"⚡ {practice_mode} Sprint")

if st.session_state.last_result:
    r = st.session_state.last_result
    if r["perfect"]:
        st.success(f"🏆 PERFECT SCORE, {r['name']}! Time: {r['elapsed']}s — saved to leaderboard!")
    else:
        st.error(f"❌ Score: {r['score']}/{NUM_PROBLEMS}. Review the red boxes and try again!")

#if st.session_state.problems:
#    display_live_timer(st.session_state.start_time)

    with st.form(f"worksheet_{st.session_state.sprint_id}"):
        cols = st.columns(2) 
        
        for i, prob in enumerate(st.session_state.problems):
            is_wrong = False
            if st.session_state.submitted_answers:
                u_ans = st.session_state.submitted_answers[i]
                if prob["style"] == "division":
                    is_wrong = not (u_ans["ans"] == prob["ans"] and u_ans["rem"] == prob.get("rem", 0))
                else:
                    is_wrong = u_ans["ans"] != prob["ans"]

            with cols[i % 2]:
                if is_wrong:
                    st.markdown('<div class="wrong-box">', unsafe_allow_html=True)
                    st.markdown("**❌ Incorrect - Review Your Steps**")
                else:
                    st.markdown('<div>', unsafe_allow_html=True) 
                
                st.markdown(f"**Q{i+1}**")
                
                s_id = st.session_state.sprint_id
                if prob["style"] == "addition":
                    render_addition(prob, i, s_id)
                elif prob["style"] == "subtraction":
                    render_subtraction(prob, i, s_id)
                elif prob["style"] == "multiplication":
                    render_multiplication(prob, i, s_id)
                elif prob["style"] == "division":
                    render_division(prob, i, s_id)
                
                st.markdown('</div><br><br>', unsafe_allow_html=True)

        submit = st.form_submit_button(f"🚀 SUBMIT {NUM_PROBLEMS} ANSWERS", use_container_width=True)

    if submit:
        user_answers = []
        for i, prob in enumerate(st.session_state.problems):
            # 1. Grab Main Answer
            ans_str = ""
            for place in ["th", "h", "t", "o"]:
                key = f"ans_{place}_{st.session_state.sprint_id}_{i}"
                if key in st.session_state and st.session_state[key]:
                    ans_str += str(st.session_state[key]).strip()
            
            try:
                main_ans = int(ans_str) if ans_str else -1
            except ValueError:
                main_ans = -1
                
            # 2. Grab Remainder (Only for Division)
            rem_ans = 0
            if prob["style"] == "division":
                # Check if the student used the first or second step
                r1_str = str(st.session_state.get(f"r1_t_{st.session_state.sprint_id}_{i}", "")).strip() + \
                         str(st.session_state.get(f"r1_o_{st.session_state.sprint_id}_{i}", "")).strip()
                
                s2_str = str(st.session_state.get(f"s2_t_{st.session_state.sprint_id}_{i}", "")).strip() + \
                         str(st.session_state.get(f"s2_o_{st.session_state.sprint_id}_{i}", "")).strip()
                         
                r2_str = str(st.session_state.get(f"r2_o_{st.session_state.sprint_id}_{i}", "")).strip()
                
                if s2_str: 
                    # If they used the second subtraction step, the final answer must be at the very bottom
                    rem_str = r2_str
                else:
                    # If they didn't use the second step (one-step problem), accept the remainder from the first block
                    rem_str = r2_str if r2_str else r1_str
                    
                try:
                    rem_ans = int(rem_str) if rem_str else 0
                except ValueError:
                    rem_ans = -1
                    
            user_answers.append({"ans": main_ans, "rem": rem_ans})
                
        st.session_state.submitted_answers = user_answers
        
        # Grading Check
        correct_count = 0
        for i, p in enumerate(st.session_state.problems):
            u_ans = user_answers[i]
            if p["style"] == "division":
                if u_ans["ans"] == p["ans"] and u_ans["rem"] == p.get("rem", 0):
                    correct_count += 1
            else:
                if u_ans["ans"] == p["ans"]:
                    correct_count += 1
                    
        elapsed       = round(time.time() - st.session_state.start_time, 2)
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
