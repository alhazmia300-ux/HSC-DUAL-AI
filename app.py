import streamlit as st
from groq import Groq
from google import genai
from PIL import Image
import requests
import time
import PyPDF2
import firebase_admin
import json
import hashlib
import uuid
import os

from firebase_admin import credentials, firestore
from streamlit_cookies_manager import EncryptedCookieManager

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(page_title="HSC Dual AI Tutor", layout="wide")

# ======================================================
# COOKIES
# ======================================================
cookies = EncryptedCookieManager(
    prefix="hsc_ai_",
    password="secure_password_123"
)

if not cookies.ready():
    st.stop()

# ======================================================
# FIREBASE INIT
# ======================================================
@st.cache_resource
def init_db():
    if not firebase_admin._apps:
        cred = credentials.Certificate(
            json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        )
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_db()

# ======================================================
# SESSION STATE
# ======================================================
for k, v in {
    "logged_in": False,
    "email": "",
    "name": "",
    "chat_id": None,
    "messages": []
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ======================================================
# AUTO LOGIN
# ======================================================
if cookies.get("logged_in") == "true":
    st.session_state.logged_in = True
    st.session_state.email = cookies.get("email")
    st.session_state.name = cookies.get("name")

# ======================================================
# USER ID
# ======================================================
def uid():
    return hashlib.md5(st.session_state.email.encode()).hexdigest()

# ======================================================
# AUTH (Firebase REST)
# ======================================================
FIREBASE_API_KEY = st.secrets["FIREBASE_API_KEY"]

def signup(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    return requests.post(url, json={
        "email": email,
        "password": password,
        "returnSecureToken": True
    }).json()

def login(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    return requests.post(url, json={
        "email": email,
        "password": password,
        "returnSecureToken": True
    }).json()

# ======================================================
# CHAT SYSTEM
# ======================================================
def new_chat(title="New Chat"):
    cid = str(uuid.uuid4())

    db.collection("users").document(uid()).collection("chats").document(cid).set({
        "title": title,
        "created_at": time.time()
    })

    st.session_state.chat_id = cid
    st.session_state.messages = []

def save(role, content):
    if not st.session_state.chat_id:
        return

    db.collection("users").document(uid())\
      .collection("chats").document(st.session_state.chat_id)\
      .collection("messages").add({
        "role": role,
        "content": content,
        "created_at": time.time()
      })

def load_chat(cid):
    msgs = db.collection("users").document(uid())\
        .collection("chats").document(cid)\
        .collection("messages").stream()

    data = []
    for m in msgs:
        d = m.to_dict()
        data.append({"role": d["role"], "content": d["content"]})

    return data

def chat_list():
    chats = db.collection("users").document(uid()).collection("chats").stream()

    return sorted(
        [
            {"id": c.id, **c.to_dict()}
            for c in chats
        ],
        key=lambda x: x.get("created_at", 0),
        reverse=True
    )

# ======================================================
# LOGOUT
# ======================================================
def logout():
    cookies["logged_in"] = ""
    cookies.save()

    st.session_state.clear()
    st.rerun()

# ======================================================
# LOGIN PAGE
# ======================================================
if not st.session_state.logged_in:
    st.title("🎓 Welcome My Friend")
    st.caption("This platform is created by ALhaz")

    name = st.text_input("Enter your name")
    email = st.text_input("Enter email / phone number")
    password = st.text_input("Password", type="password")

    mode = st.selectbox("Choose", ["Login", "Sign Up"])

    if st.button("Continue"):
        if not name:
            st.error("Name required")
            st.stop()

        if mode == "Sign Up":
            res = signup(email, password)
        else:
            res = login(email, password)

        if "email" in res:
            st.session_state.logged_in = True
            st.session_state.email = email
            st.session_state.name = name

            cookies["logged_in"] = "true"
            cookies["email"] = email
            cookies["name"] = name
            cookies.save()

            new_chat("New Chat")
            st.rerun()
        else:
            st.error(res.get("error", {}).get("message", "Error"))

    st.stop()

# ======================================================
# SIDEBAR UI (compact)
# ======================================================
st.sidebar.markdown("## ⚙️ Settings")

st.sidebar.markdown(f"👤 **{st.session_state.name}**")
st.sidebar.markdown(f"📧 {st.session_state.email}")

model = st.sidebar.radio("AI Model", ["Gemini", "Llama3"])
subject = st.sidebar.selectbox("Subject", ["Physics","Chemistry","Math","ICT"])

if st.sidebar.button("➕ New Chat"):
    new_chat("New Chat")
    st.rerun()

search = st.sidebar.text_input("🔍 Search chat")

# chat list
for c in chat_list():
    if search.lower() in c["title"].lower():

        if st.sidebar.button(c["title"][:25]):
            st.session_state.chat_id = c["id"]
            st.session_state.messages = load_chat(c["id"])
            st.rerun()

st.sidebar.button("🚪 Logout", on_click=logout)

# ======================================================
# MAIN HEADER (minimal)
# ======================================================
st.markdown(
    f"""
### Hi {st.session_state.name} 👋
Ask anything about your studies
"""
)

# top-right new chat
col1, col2 = st.columns([8,1])
with col2:
    if st.button("➕"):
        new_chat("New Chat")
        st.rerun()

# ======================================================
# LOAD CURRENT CHAT
# ======================================================
if st.session_state.chat_id and not st.session_state.messages:
    st.session_state.messages = load_chat(st.session_state.chat_id)

# ======================================================
# SHOW CHAT
# ======================================================
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ======================================================
# GEMINI
# ======================================================
def gemini(prompt):
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        r = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return r.text
    except:
        return "Gemini busy. Try again later."

# ======================================================
# INPUT
# ======================================================
msg = st.chat_input("Ask something...")

if msg:

    st.chat_message("user").markdown(msg)

    st.session_state.messages.append({"role":"user","content":msg})
    save("user", msg)

    with st.chat_message("assistant"):
        reply = gemini(msg) if model=="Gemini" else "Llama3 response here"
        st.markdown(reply)

    st.session_state.messages.append({"role":"assistant","content":reply})
    save("assistant", reply)