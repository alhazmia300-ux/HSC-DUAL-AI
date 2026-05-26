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
import os

from firebase_admin import credentials
from firebase_admin import firestore

# ======================================================
# PAGE CONFIG
# ======================================================
st.set_page_config(
    page_title="🎓 HSC Dual AI Tutor",
    page_icon="🎓",
    layout="centered"
)

# ======================================================
# CUSTOM CSS
# ======================================================
st.markdown("""
<style>
/* Main */
.stApp { background-color: var(--background-color); }
/* Chat Box */
[data-testid="stChatMessage"] { border-radius: 16px; padding: 14px; margin-bottom: 12px; }
/* Buttons */
.stButton > button { width: 100%; border-radius: 12px; }
/* Sidebar */
section[data-testid="stSidebar"] { border-right: 1px solid rgba(128,128,128,0.15); }
/* Input */
.stTextInput input { border-radius: 12px; }
/* Chat Input */
.stChatInputContainer { border-top: 1px solid rgba(128,128,128,0.15); }
</style>
""", unsafe_allow_html=True)

# ======================================================
# HEADER
# ======================================================
st.title("🎓 HSC Dual AI Tutor")
st.subheader("Gemini + Llama3 দিয়ে HSC প্রস্তুতি")
st.write("প্রশ্ন করো, ছবি/PDF আপলোড করো, MCQ তৈরি করো!")
st.caption("🚀 Created by ALhaz")

# ======================================================
# SECRETS
# ======================================================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
FIREBASE_API_KEY = st.secrets.get("FIREBASE_API_KEY")
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")

# ======================================================
# FIREBASE ADMIN (Safe Wrapper)
# ======================================================
@st.cache_resource
def init_firestore():
    if not firebase_admin._apps:
        try:
            firebase_json = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
            cred = credentials.Certificate(firebase_json)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Firebase Configuration Error: {e}")
    return firestore.client()

db = init_firestore()

# ======================================================
# SESSION STATE INITIALIZATION
# ======================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

# ======================================================
# FIREBASE AUTH FUNCTIONS
# ======================================================
def signup(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": {"message": str(e)}}

def login(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": {"message": str(e)}}

def logout():
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.messages = []

# ======================================================
# USER ID GENERATOR
# ======================================================
def get_user_id():
    email = st.session_state.user_email if st.session_state.user_email else "guest"
    return hashlib.md5(email.encode()).hexdigest()

# ======================================================
# FIRESTORE CORE FUNCTIONS
# ======================================================
def save_message(role, content):
    if db and content:
        try:
            db.collection("chat_history").add({
                "user_id": get_user_id(),
                "role": role,
                "content": content,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
        except:
            pass

def load_chat_history():
    if not db:
        return []
    try:
        # ইনডেক্সিং টাইমস্ট্যাম্প সেফ ফিল্টার
        chats = db.collection("chat_history") \
            .where("user_id", "==", get_user_id()) \
            .order_by("timestamp", direction=firestore.Query.ASCENDING) \
            .stream()
        
        messages = []
        for chat in chats:
            data = chat.to_dict()
            messages.append({
                "role": data.get("role", "user"),
                "content": data.get("content", "")
            })
        return messages
    except:
        # ইনডেক্সিং না থাকলে এরর এড়াতে সাধারণ নো-অর্ডার রিকোয়েস্ট ব্যাকআপ
        try:
            chats = db.collection("chat_history").where("user_id", "==", get_user_id()).stream()
            return [{"role": c.to_dict().get("role", "user"), "content": c.to_dict().get("content", "")} for c in chats]
        except:
            return []

def clear_chat_history():
    if db:
        try:
            chats = db.collection("chat_history").where("user_id", "==", get_user_id()).stream()
            for chat in chats:
                chat.reference.delete()
        except:
            pass

# ======================================================
# LOGIN / SIGNUP SCREEN
# ======================================================
if not st.session_state.logged_in:
    st.subheader("🔐 Login / Sign Up Required")
    option = st.selectbox("Choose Option", ["Login", "Sign Up"])
    email_input = st.text_input("📧 Email")
    password_input = st.text_input("🔑 Password", type="password")

    if option == "Sign Up":
        if st.button("Create Account"):
            if email_input and password_input:
                result = signup(email_input, password_input)
                if "email" in result:
                    st.success("✅ Account Created Successfully! এখন Login সিলেক্ট করে প্রবেশ করো।")
                else:
                    err_msg = result.get("error", {}).get("message", "Registration Failed")
                    st.error(f"❌ Error: {err_msg}")
            else:
                st.warning("⚠️ ইমেইল এবং পাসওয়ার্ড দুটিই পূরণ করো।")
    else:
        if st.button("Login"):
            if email_input and password_input:
                result = login(email_input, password_input)
                if "email" in result:
                    st.session_state.logged_in = True
                    st.session_state.user_email = result["email"]
                    st.session_state.messages = load_chat_history()
                    st.success("✅ Login Successful")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    err_msg = result.get("error", {}).get("message", "Invalid Credentials")
                    st.error(f"❌ Error: {err_msg}")
            else:
                st.warning("⚠️ ইমেইল এবং পাসওয়ার্ড সাবমিট করো।")
    st.stop()

# ======================================================
# SIDEBAR CONTROLS
# ======================================================
st.sidebar.success(f"👤 {st.session_state.user_email}")

if st.sidebar.button("🚪 Logout", use_container_width=True):
    logout()
    st.rerun()

if st.sidebar.button("🗑️ Clear Chat History", use_container_width=True):
    clear_chat_history()
    st.session_state.messages = []
    st.rerun()

model_choice = st.sidebar.radio("🤖 AI Model নির্বাচন করো", ["Gemini (Multimodal)", "Llama3 (Text Only)"])

subject = st.sidebar.selectbox("📚 বিষয় নির্বাচন করো", [
    "Physics", "Chemistry", "Biology", "Higher Math",
    "History", "Economics", "Sociology", "Geography",
    "Accounting", "Finance", "Management",
    "Bangla", "English", "ICT", "Statistics", "Agriculture", "Psychology", "Islamic Studies"
])

# ======================================================
# GEMINI ENGINE CONFIG (Safe Call)
# ======================================================
def call_gemini(prompt_text, image_obj=None):
    try:
        # Pydantic ভ্যালিডেশন এরর এড়াতে এনভায়রনমেন্ট মেথডে ক্লায়েন্ট কল
        os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
        client = genai.Client()
        
        if image_obj:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt_text, image_obj]
            )
        else:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_text
            )
        return response.text
    except Exception as e:
        return f"❌ Gemini Error:\n{str(e)}"

# ======================================================
# MCQ GENERATOR BUTTON WORKER
# ======================================================
if st.sidebar.button("📝 Generate MCQ", use_container_width=True):
    mcq_prompt = f"তুমি একজন বিশেষজ্ঞ শিক্ষক। {subject} বিষয়ের HSC স্তরের ১০টি গুরুত্বপূর্ণ MCQ প্রশ্ন তৈরি করো এবং নিচে তার সঠিক উত্তর ব্যাখ্যাসহ বাংলায় দাও।"
    with st.spinner("MCQ তৈরি হচ্ছে..."):
        mcq_response = call_gemini(mcq_prompt)
    st.markdown("---")
    st.markdown(mcq_response)

# ======================================================
# TELEGRAM LOGGING
# ======================================================
def send_telegram(message_text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not message_text:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": f"👤 User: {USER_ID}\n📝 Prompt: {message_text[:200]}"}, timeout=5)
    except:
        pass

# ======================================================
# SHOW HISTORIC MESSAGES
# ======================================================
USER_ID = get_user_id()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ======================================================
# CHAT INPUT SYSTEM
# ======================================================
prompt = st.chat_input("প্রশ্ন লেখো অথবা ছবি/PDF আপলোড করো...", accept_file=True, file_type=["jpg", "jpeg", "png", "pdf"])

if prompt:
    raw_user_text = prompt.text if prompt.text else ""
    uploaded_files = prompt.files
    image_to_send = None
    pdf_text = ""

    # ফাইল এক্সট্রাকশন
    if uploaded_files and len(uploaded_files) > 0:
        uploaded_file = uploaded_files[0]
        file_name = uploaded_file.name.lower()

        if file_name.endswith((".jpg", ".jpeg", ".png")):
            image_to_send = Image.open(uploaded_file)
        elif file_name.endswith(".pdf"):
            try:
                reader = PyPDF2.PdfReader(uploaded_file)
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt:
                        pdf_text += txt
                st.success("✅ PDF সফলভাবে আপলোড হয়েছে")
            except Exception as e:
                st.error(f"PDF Read Error: {e}")

    # ব্যাকগ্রাউন্ড এআই প্রম্পট প্রিপারেশন
    user_prompt = f"তুমি একজন {subject} বিষয়ের HSC স্তরের শিক্ষক। সহজ সাবলীল বাংলায় উত্তর দাও।\n\nপ্রশ্ন:\n{raw_user_text}"
    if pdf_text:
        user_prompt += f"\n\n[সংযুক্ত PDF-এর টেক্সট তথ্য]:\n{pdf_text[:3000]}"

    # UI-তে মেসেজ পাঠানো
    with st.chat_message("user"):
        if image_to_send:
            st.image(image_to_send, width=250)
        st.markdown(raw_user_text if raw_user_text else "[📎 ফাইল সংযুক্তি]")

    # ফায়ারবেস বা সেশনে খালি বা ইনভ্যালিড টেক্সট সাবমিশন রোধ
    display_text = raw_user_text if raw_user_text else "[📸 ফাইল সংযুক্তি]"
    st.session_state.messages.append({"role": "user", "content": display_text})
    save_message("user", display_text)
    send_telegram(display_text)

    # রেসপন্স প্রসেসিং
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""

        try:
            if model_choice == "Gemini (Multimodal)":
                full_response = call_gemini(user_prompt, image_to_send)
            else:
                if image_to_send:
                    full_response = "⚠️ Llama3 ছবি বুঝতে পারে না। ছবির জন্য সাইডবার থেকে Gemini সিলেক্ট করো।"
                elif not GROQ_API_KEY:
                    full_response = "⚠️ Groq API Key সেট করা নেই।"
                else:
                    client = Groq(api_key=GROQ_API_KEY)
                    
                    # Groq বা Llama3 এর জন্য চ্যাট হিস্ট্রি প্রসেস করা
                    groq_messages = [{"role": "system", "content": f"You are an expert HSC teacher teaching {subject} in Bengali."}]
                    for m in st.session_state.messages[:-1]:
                        groq_messages.append({"role": m["role"], "content": m["content"]})
                    groq_messages.append({"role": "user", "content": user_prompt})

                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=groq_messages
                    )
                    full_response = completion.choices[0].message.content
        except Exception as e:
            full_response = f"❌ Error:\n{str(e)}"

        # টাইপিং ইফেক্ট স্ট্রিমিং
        typed = ""
        for char in full_response:
            typed += char
            response_placeholder.markdown(typed)
            time.sleep(0.005)

        # সেশন এবং ক্লাউডে রেসপন্স সেভ করা
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        save_message("assistant", full_response)
