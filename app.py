import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import google.generativeai as genai
import os, json, tempfile
import speech_recognition as sr
import pandas as pd
import plotly.express as px
from PyPDF2 import PdfReader
from pydub import AudioSegment

# ===============================
# GEMINI CONFIGURATION
# ===============================

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def get_available_model():
    """
    Select ONLY free-tier safe models.
    Avoid gemini-3-pro automatically.
    """
    try:
        models = genai.list_models()

        supported = [
            m.name for m in models
            if "generateContent" in m.supported_generation_methods
        ]

        # Prefer FLASH models (free tier safe)
        for model in supported:
            if "flash" in model.lower():
                return model

        # Fallback to older gemini-pro (if available)
        for model in supported:
            if "gemini-pro" in model.lower() and "vision" not in model.lower():
                return model

        return None

    except Exception:
        return None


MODEL_NAME = get_available_model()

if MODEL_NAME:
    MODEL = genai.GenerativeModel(MODEL_NAME)
else:
    MODEL = None


# ===============================
# PAGE CONFIG
# ===============================

st.set_page_config(page_title="AI Study Buddy", layout="wide")

# ===============================
# THEME
# ===============================

st.markdown("""
<style>
.stApp{
background: radial-gradient(circle at top,#2b0057,#0a0014);
color:white;
}
.metric-card{
background:#140028;
padding:20px;
border-radius:12px;
border:1px solid #7a00ff;
text-align:center;
}
.chat-user{
background:#5f00ff;
padding:10px;
border-radius:10px;
margin:10px;
text-align:right;
}
.chat-ai{
background:#1a0033;
padding:10px;
border-radius:10px;
margin:10px;
}
button{
background:linear-gradient(90deg,#7a00ff,#b300ff) !important;
color:white !important;
border-radius:25px !important;
}
</style>
""", unsafe_allow_html=True)

# ===============================
# FILES
# ===============================

USER_FILE = "users.json"
STATS_FILE = "stats.json"

if not os.path.exists(USER_FILE):
    json.dump({}, open(USER_FILE, "w"))

if not os.path.exists(STATS_FILE):
    json.dump({
        "notes": 0,
        "flashcards": 0,
        "voice": 0,
        "quiz": 0
    }, open(STATS_FILE, "w"))

# ===============================
# SAFE AI FUNCTION
# ===============================

def ask_ai(prompt):
    try:
        if not MODEL:
            return "⚠ No free Gemini model available. Enable billing or create a new API key."

        full_prompt = f"You are a helpful study assistant.\n\n{prompt}"
        response = MODEL.generate_content(full_prompt)

        return response.text if response.text else "No response generated."

    except Exception as e:
        if "429" in str(e):
            return "⚠ Free-tier quota exceeded. Please wait or enable billing."
        return f"AI Error: {str(e)}"

# ===============================
# SESSION STATE
# ===============================

if "login" not in st.session_state:
    st.session_state.login = False

if "chat" not in st.session_state:
    st.session_state.chat = []

# ===============================
# LOGIN PAGE
# ===============================

if not st.session_state.login:

    users = json.load(open(USER_FILE))

    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.markdown("""
        <div style="height:650px;padding:60px;border-radius:20px;
        background:linear-gradient(135deg,#6a00ff,#1b0038);">
        <h1>WELCOME BACK</h1>
        <p>Login to your AI Study Buddy</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:

        tab = st.radio("Account", ["Login", "Register"], label_visibility="collapsed")

        if tab == "Login":

            email = st.text_input("Email")
            pwd = st.text_input("Password", type="password")

            if st.button("Login", use_container_width=True):

                if email in users and users[email]["pwd"] == pwd:
                    st.session_state.login = True
                    st.session_state.name = users[email]["name"]
                    st.rerun()
                else:
                    st.error("Invalid login")

        else:

            name = st.text_input("Name")
            email = st.text_input("Email")
            pwd = st.text_input("Password", type="password")

            if st.button("Register", use_container_width=True):

                users[email] = {"name": name, "pwd": pwd}
                json.dump(users, open(USER_FILE, "w"))
                st.success("Account created")

# ===============================
# MAIN APP
# ===============================

else:

    st.sidebar.title("Welcome " + st.session_state.name)
    st.sidebar.write(f"Model: {MODEL_NAME if MODEL_NAME else 'None'}")

    menu = st.sidebar.radio("Menu", [
        "Dashboard",
        "Study Material",
        "Voice & Audio",
        "Quiz",
        "AI Chat"
    ])

# ===============================
# DASHBOARD
# ===============================

    if menu == "Dashboard":

        stats = json.load(open(STATS_FILE))

        col1, col2, col3, col4 = st.columns(4)

        col1.markdown(f"<div class='metric-card'><h3>Notes</h3><h2>{stats['notes']}</h2></div>", unsafe_allow_html=True)
        col2.markdown(f"<div class='metric-card'><h3>Flashcards</h3><h2>{stats['flashcards']}</h2></div>", unsafe_allow_html=True)
        col3.markdown(f"<div class='metric-card'><h3>Voice</h3><h2>{stats['voice']}</h2></div>", unsafe_allow_html=True)
        col4.markdown(f"<div class='metric-card'><h3>Quiz</h3><h2>{stats['quiz']}</h2></div>", unsafe_allow_html=True)

        df = pd.DataFrame({
            "Feature": ["Notes", "Flashcards", "Voice", "Quiz"],
            "Usage": [stats["notes"], stats["flashcards"], stats["voice"], stats["quiz"]]
        })

        fig = px.bar(df, x="Feature", y="Usage")
        st.plotly_chart(fig, use_container_width=True)

# ===============================
# STUDY MATERIAL
# ===============================

    if menu == "Study Material":

        text = st.text_area("Paste study text")
        file = st.file_uploader("Upload PDF", type=["pdf"])

        if file:
            pdf = PdfReader(file)
            for p in pdf.pages:
                extracted = p.extract_text()
                if extracted:
                    text += extracted

        if st.button("Generate Notes + Flashcards"):
            prompt = f"""
Create structured study notes.

TEXT:
{text}

OUTPUT:
Summary
Key Points
Flashcards (Q/A)
"""
            st.write(ask_ai(prompt))

# ===============================
# QUIZ
# ===============================

    if menu == "Quiz":

        topic = st.text_input("Quiz Topic")

        if st.button("Generate Quiz"):
            st.write(ask_ai(f"Create 5 MCQ questions about {topic}"))

# ===============================
# CHAT
# ===============================

    if menu == "AI Chat":

        msg = st.chat_input("Ask AI")

        if msg:
            reply = ask_ai(msg)
            st.session_state.chat.append(("user", msg))
            st.session_state.chat.append(("ai", reply))

        for role, m in st.session_state.chat:
            if role == "user":
                st.markdown(f"<div class='chat-user'>{m}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='chat-ai'>{m}</div>", unsafe_allow_html=True)

    if st.sidebar.button("Logout"):
        st.session_state.login = False
        st.rerun()
