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
.stApp {
    background-color: var(--background-color);
}

/* Chat Box */
[data-testid="stChatMessage"] {
    border-radius: 16px;
    padding: 14px;
    margin-bottom: 12px;
}

/* Buttons */
.stButton > button {
    width: 100%;
    border-radius: 12px;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128,128,128,0.15);
}

/* Input */
.stTextInput input {
    border-radius: 12px;
}

/* Chat Input */
.stChatInputContainer {
    border-top: 1px solid rgba(128,128,128,0.15);
}

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

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

FIREBASE_API_KEY = st.secrets["FIREBASE_API_KEY"]

TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")

# ======================================================
# FIREBASE ADMIN
# ======================================================

if not firebase_admin._apps:

    firebase_json = json.loads(
        st.secrets["FIREBASE_CREDENTIALS"]
    )

    cred = credentials.Certificate(firebase_json)

    firebase_admin.initialize_app(cred)

db = firestore.client()

# ======================================================
# SESSION
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

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    r = requests.post(url, json=payload)

    return r.json()

def login(email, password):

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    r = requests.post(url, json=payload)

    return r.json()

def logout():

    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.messages = []

# ======================================================
# USER ID
# ======================================================

def get_user_id():

    email = st.session_state.user_email

    return hashlib.md5(email.encode()).hexdigest()

# ======================================================
# SAVE CHAT
# ======================================================

def save_message(role, content):

    try:

        db.collection("chat_history").add({
            "user_id": get_user_id(),
            "role": role,
            "content": content,
            "timestamp": firestore.SERVER_TIMESTAMP
        })

    except Exception as e:

        st.error(f"❌ Save Error: {str(e)}")

# ======================================================
# LOAD CHAT
# ======================================================

def load_chat_history():

    try:

        chats = db.collection("chat_history") \
            .where("user_id", "==", get_user_id()) \
            .stream()

        messages = []

        for chat in chats:

            data = chat.to_dict()

            messages.append({
                "role": data["role"],
                "content": data["content"]
            })

        return messages

    except:

        return []

# ======================================================
# LOGIN PAGE
# ======================================================

if not st.session_state.logged_in:

    st.subheader("🔐 Login Required")

    option = st.selectbox(
        "Choose Option",
        ["Login", "Sign Up"]
    )

    email = st.text_input("📧 Email")

    password = st.text_input(
        "🔑 Password",
        type="password"
    )

    # ==================================================
    # SIGNUP
    # ==================================================

    if option == "Sign Up":

        if st.button("Create Account"):

            result = signup(email, password)

            if "email" in result:

                st.success("✅ Account Created Successfully!")

                st.info("👉 এখন Login করো")

            else:

                st.error(result)

    # ==================================================
    # LOGIN
    # ==================================================

    else:

        if st.button("Login"):

            result = login(email, password)

            if "email" in result:

                st.session_state.logged_in = True

                st.session_state.user_email = result["email"]

                st.session_state.messages = load_chat_history()

                st.success("✅ Login Successful")

                time.sleep(1)

                st.rerun()

            else:

                st.error("❌ Invalid email or password")

    st.stop()

# ======================================================
# SIDEBAR
# ======================================================

st.sidebar.success(
    f"👤 {st.session_state.user_email}"
)

if st.sidebar.button("🚪 Logout"):

    logout()

    st.rerun()

if st.sidebar.button("🗑️ Clear Chat"):

    st.session_state.messages = []

# ======================================================
# MODEL
# ======================================================

model_choice = st.sidebar.radio(
    "🤖 AI Model",
    [
        "Gemini (Multimodal)",
        "Llama3 (Text Only)"
    ]
)

# ======================================================
# SUBJECTS
# ======================================================

subject = st.sidebar.selectbox(
    "📚 বিষয় নির্বাচন করো",
    [

        # Science
        "Physics",
        "Chemistry",
        "Biology",
        "Higher Math",

        # Arts
        "History",
        "Economics",
        "Sociology",
        "Geography",

        # Commerce
        "Accounting",
        "Finance",
        "Management",

        # Compulsory
        "Bangla",
        "English",
        "ICT",

        # Optional
        "Statistics",
        "Agriculture",
        "Psychology",
        "Islamic Studies"
    ]
)

# ======================================================
# MCQ GENERATOR
# ======================================================

if st.sidebar.button("📝 Generate MCQ"):

    mcq_prompt = f"""
    {subject} বিষয়ের HSC level এর
    10টি MCQ তৈরি করো।
    প্রতিটির সঠিক উত্তর দাও।
    """

    st.session_state.messages.append({
        "role": "assistant",
        "content": mcq_prompt
    })

# ======================================================
# TELEGRAM
# ======================================================

def send_telegram(message):

    if not TELEGRAM_BOT_TOKEN:
        return

    if not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:

        requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message
            }
        )

    except:
        pass

# ======================================================
# GEMINI
# ======================================================

def call_gemini(prompt, image=None):

    try:

        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        if image:

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt, image]
            )

        else:

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

        return response.text

    except Exception as e:

        return f"❌ Gemini Error:\n{str(e)}"

# ======================================================
# SHOW CHAT
# ======================================================

for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):

        st.markdown(msg["content"])

# ======================================================
# CHAT INPUT
# ======================================================

prompt = st.chat_input(
    "প্রশ্ন লেখো অথবা ছবি/PDF আপলোড করো...",
    accept_file=True,
    file_type=["jpg", "jpeg", "png", "pdf"]
)

# ======================================================
# MAIN CHAT
# ======================================================

if prompt:

    user_text = prompt.text

    uploaded_files = prompt.files

    image_to_send = None

    pdf_text = ""

    user_prompt = f"""
তুমি একজন {subject} বিষয়ের HSC শিক্ষক।

সহজ ভাষায় উত্তর দাও।

প্রশ্ন:
{user_text}
"""

    # ==================================================
    # FILES
    # ==================================================

    if uploaded_files and len(uploaded_files) > 0:

        uploaded_file = uploaded_files[0]

        file_name = uploaded_file.name.lower()

        # IMAGE
        if file_name.endswith((".jpg", ".jpeg", ".png")):

            image_to_send = Image.open(uploaded_file)

        # PDF
        elif file_name.endswith(".pdf"):

            reader = PyPDF2.PdfReader(uploaded_file)

            for page in reader.pages:

                text = page.extract_text()

                if text:
                    pdf_text += text

            st.success("✅ PDF Uploaded")

    if pdf_text:

        user_prompt += f"\n\nPDF:\n{pdf_text[:4000]}"

    # ==================================================
    # SHOW USER
    # ==================================================

    with st.chat_message("user"):

        if image_to_send:

            st.image(
                image_to_send,
                width=250
            )

        st.markdown(
            user_text if user_text
            else "[File Uploaded]"
        )

    st.session_state.messages.append({
        "role": "user",
        "content": user_text
    })

    save_message("user", user_text)

    send_telegram(user_text)

    # ==================================================
    # ASSISTANT
    # ==================================================

    with st.chat_message("assistant"):

        response_placeholder = st.empty()

        full_response = ""

        try:

            # GEMINI
            if model_choice == "Gemini (Multimodal)":

                full_response = call_gemini(
                    user_prompt,
                    image_to_send
                )

            # LLAMA
            else:

                if image_to_send:

                    full_response = (
                        "⚠️ Llama3 ছবি বুঝতে পারে না। "
                        "Gemini ব্যবহার করো।"
                    )

                else:

                    client = Groq(
                        api_key=GROQ_API_KEY
                    )

                    completion = client.chat.completions.create(

                        model="llama-3.3-70b-versatile",

                        messages=[
                            {
                                "role": "user",
                                "content": user_prompt
                            }
                        ]
                    )

                    full_response = completion.choices[0].message.content

        except Exception as e:

            full_response = f"❌ Error:\n{str(e)}"

        # Typing Effect
        typed = ""

        for char in full_response:

            typed += char

            response_placeholder.markdown(typed)

            time.sleep(0.01)

        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response
        })

        save_message("assistant", full_response)