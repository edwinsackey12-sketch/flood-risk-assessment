import csv
import re
from datetime import datetime, timezone

import streamlit as st

st.set_page_config(
    page_title="Flood Risk Assessment",
    layout="centered",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button,
.stApp h1, .stApp h2, .stApp h3, .stApp div[data-testid="stMarkdownContainer"] {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
               "Helvetica Neue", Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"] {
  visibility: hidden; height: 0;
}
.stApp { background: #ffffff; color: #1d1d1f; }
.block-container { max-width: 640px; padding: 4.5rem 1.5rem 6rem; }

.eyebrow { font-size: 14px; color: #6e6e73; margin: 0 0 14px; letter-spacing: 0.01em; }
.title   { font-size: 52px; line-height: 1.07; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 18px; color: #1d1d1f; }
.lead    { font-size: 21px; line-height: 1.38; color: #6e6e73; margin: 0 0 32px; }
.q       { font-size: 34px; line-height: 1.12; font-weight: 600; letter-spacing: -0.015em; margin: 0 0 28px; color: #1d1d1f; }
.h3      { font-size: 28px; line-height: 1.14; font-weight: 600; letter-spacing: -0.01em; margin: 0 0 10px; color: #1d1d1f; }
.body    { font-size: 17px; line-height: 1.47; color: #6e6e73; margin: 0 0 20px; }
.rule    { border: 0; border-top: 1px solid #d2d2d7; margin: 48px 0 40px; }
.fix     { font-size: 17px; line-height: 1.47; color: #1d1d1f; padding: 16px 0; border-top: 1px solid #d2d2d7; }
.fine    { font-size: 12px; line-height: 1.4; color: #86868b; margin-top: 56px; }

.scale { display: flex; gap: 6px; margin: 32px 0 12px; }
.seg   { flex: 1; border-top: 4px solid #d2d2d7; padding-top: 8px; font-size: 14px; color: #86868b; }
.seg.on { border-top-color: #1d1d1f; color: #1d1d1f; font-weight: 600; }

div[role="radiogroup"] { gap: 0; }
div[role="radiogroup"] > label { padding: 16px 0; border-bottom: 1px solid #d2d2d7; margin: 0; }
div[role="radiogroup"] > label p { font-size: 19px; color: #1d1d1f; }

.stButton > button, .stFormSubmitButton > button {
  border-radius: 980px; padding: 0.55rem 1.5rem; font-size: 17px; font-weight: 400;
  border: none; box-shadow: none;
}
button[kind="primary"], button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
  background: #0071e3; color: #ffffff;
}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover { background: #0077ed; color: #ffffff; }
button[kind="primary"]:disabled, button[data-testid="stBaseButton-primary"]:disabled {
  background: #d2d2d7; color: #ffffff;
}
button[kind="secondary"], button[data-testid="stBaseButton-secondary"] {
  background: transparent; color: #0066cc;
}
button[kind="secondary"]:hover, button[data-testid="stBaseButton-secondary"]:hover {
  background: transparent; color: #0066cc; text-decoration: underline;
}

.stTextInput input {
  border-radius: 12px; border: 1px solid #d2d2d7; background: #ffffff; color: #1d1d1f;
  font-size: 17px; padding: 14px 16px;
}
.stTextInput input:focus { border-color: #0071e3; box-shadow: 0 0 0 3px rgba(0,113,227,0.2); }
[data-testid="stForm"] { border: 0; padding: 0; }

@media (max-width: 640px) {
  .block-container { padding-top: 2.5rem; }
  .title { font-size: 40px; }
  .q { font-size: 28px; }
  .lead { font-size: 19px; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# key -> (question, {answer: points}, design fix shown when the answer scores above 0)
QUESTIONS = {
    "pooling": (
        "After heavy rain, does water collect on your street?",
        {"Never": 0, "Sometimes": 1, "Every time": 3},
        "Slope the ground around the house away from the walls, and report the spot to the Assembly so the road drain can be cleared or extended.",
    ),
    "drain": (
        "What is the nearest drain like?",
        {"Open and flowing": 0, "Blocked or full of waste": 2, "No drain nearby": 3},
        "Add gutters and a channel that carries roof water to a drain, and clear the drain of waste before the rains.",
    ),
    "floor": (
        "How high is your floor above the street?",
        {"60 cm or more": 0, "30 to 60 cm": 1, "Level with the street": 2, "Below the street": 3},
        "Raise the floor when building or rebuilding. Compact the soil, add a gravel layer under the slab, and include a damp-proof membrane.",
    ),
    "history": (
        "Has your home flooded before?",
        {"No": 0, "Once": 2, "More than once": 3},
        "Past flooding is the strongest warning sign. Keep valuables raised off the floor and plan for water to return.",
    ),
    "channel": (
        "How far is the nearest stream or drainage channel?",
        {"Over 500 m": 0, "100 to 500 m": 1, "Under 100 m": 3, "Not sure": 1},
        "Keep new building back from the channel, keep its banks clear, and plan a dry route out of the house.",
    ),
}
KEYS = list(QUESTIONS)
N = len(KEYS)
MAX_SCORE = sum(max(opts.values()) for _, opts, _ in QUESTIONS.values())

LEVELS = ["Low", "Moderate", "High", "Critical"]
LEVEL_NOTE = {
    "Low": "Your answers show few warning signs. Keep nearby drains clear.",
    "Moderate": "Your answers show some warning signs. A few changes can lower the risk.",
    "High": "Your answers show several warning signs. Heavy rain is a real threat to your home.",
    "Critical": "Your answers show serious warning signs. Heavy rain puts your home at significant risk.",
}


def level_index(total):
    if total <= 3:
        return 0
    if total <= 7:
        return 1
    if total <= 11:
        return 2
    return 3


def scale_html(active):
    segs = "".join(
        f'<div class="seg{" on" if i == active else ""}">{name}</div>'
        for i, name in enumerate(LEVELS)
    )
    return f'<div class="scale">{segs}</div>'


def valid_contact(text):
    text = text.strip()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text):
        return True
    digits = re.sub(r"[\s\-()]", "", text)
    return bool(re.fullmatch(r"\+?\d{9,15}", digits))


def save_signup(contact, level):
    try:
        with open("signups.csv", "a", newline="") as f:
            csv.writer(f).writerow(
                [datetime.now(timezone.utc).isoformat(), contact.strip(), level]
            )
    except OSError:
        pass


ss = st.session_state
ss.setdefault("step", 0)
ss.setdefault("answers", {})
ss.setdefault("signed_up", False)
step = ss.step

# ---------- Intro ----------
if step == 0:
    st.markdown('<p class="eyebrow">Kasoa, Ghana</p>', unsafe_allow_html=True)
    st.markdown('<h1 class="title">Flood Risk Assessment</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="lead">Five questions about your street and your home. '
        "Find out how likely your home is to flood, and what to change.</p>",
        unsafe_allow_html=True,
    )
    if st.button("Start", type="primary"):
        ss.step = 1
        st.rerun()

# ---------- Questions ----------
elif 1 <= step <= N:
    key = KEYS[step - 1]
    label, opts, _ = QUESTIONS[key]
    options = list(opts)
    saved = ss.answers.get(key)

    st.markdown(f'<p class="eyebrow">Question {step} of {N}</p>', unsafe_allow_html=True)
    st.markdown(f'<h2 class="q">{label}</h2>', unsafe_allow_html=True)

    choice = st.radio(
        label,
        options,
        index=options.index(saved) if saved in options else None,
        key=f"radio_{key}",
        label_visibility="collapsed",
    )

    st.write("")
    back_col, next_col = st.columns(2)
    with back_col:
        if st.button("Back", key=f"back_{key}"):
            ss.step -= 1
            st.rerun()
    with next_col:
        last = step == N
        if st.button(
            "See my result" if last else "Continue",
            type="primary",
            disabled=choice is None,
            key=f"next_{key}",
        ):
            ss.answers[key] = choice
            ss.step += 1
            st.rerun()

# ---------- Result ----------
else:
    points = {k: QUESTIONS[k][1][ss.answers[k]] for k in KEYS}
    total = sum(points.values())
    idx = level_index(total)
    level = LEVELS[idx]

    st.markdown('<p class="eyebrow">Your result</p>', unsafe_allow_html=True)
    st.markdown(
        f'<h1 class="title">{level} flood risk.</h1>', unsafe_allow_html=True
    )
    st.markdown(f'<p class="lead">{LEVEL_NOTE[level]}</p>', unsafe_allow_html=True)
    st.markdown(scale_html(idx), unsafe_allow_html=True)

    risky = sorted((k for k in KEYS if points[k] > 0), key=lambda k: -points[k])
    if risky:
        st.markdown('<hr class="rule">', unsafe_allow_html=True)
        st.markdown('<h3 class="h3">What to change</h3>', unsafe_allow_html=True)
        st.markdown(
            '<p class="body">Listed by how much each answer raised your risk.</p>',
            unsafe_allow_html=True,
        )
        for k in risky:
            st.markdown(f'<div class="fix">{QUESTIONS[k][2]}</div>', unsafe_allow_html=True)

    st.markdown('<hr class="rule">', unsafe_allow_html=True)
    st.markdown('<h3 class="h3">Get flood alerts</h3>', unsafe_allow_html=True)
    st.markdown(
        '<p class="body">Alerts are in pilot. Leave a phone number or email '
        "to be included when they start.</p>",
        unsafe_allow_html=True,
    )

    if ss.signed_up:
        st.markdown(
            '<p class="body">Thank you. You are on the list for flood alerts.</p>',
            unsafe_allow_html=True,
        )
    else:
        with st.form("alerts", border=False):
            contact = st.text_input(
                "Phone number or email",
                placeholder="Phone number or email",
                label_visibility="collapsed",
            )
            consent = st.checkbox("I agree to receive flood alerts at this contact.")
            send = st.form_submit_button("Notify me", type="primary")
        if send:
            if not valid_contact(contact):
                st.error("Enter a valid phone number or email address.")
            elif not consent:
                st.error("Please tick the box to agree.")
            else:
                save_signup(contact, level)
                ss.signed_up = True
                st.rerun()

    st.write("")
    if st.button("Start over"):
        ss.step = 0
        ss.answers = {}
        ss.signed_up = False
        for k in KEYS:
            ss.pop(f"radio_{k}", None)
        st.rerun()

st.markdown(
    '<p class="fine">Scores come from simple rules and have not yet been validated '
    "against flood records. This tool is not engineering advice.</p>",
    unsafe_allow_html=True,
)
