import streamlit as st
from groq import Groq
from PIL import Image
from google import genai
import requests
import time
import PyPDF2
import firebase_admin
import json
import pyrebase

from firebase_admin import credentials
from firebase_admin import firestore

# =========================================
# PAGE CONFIG
# =========================================

st.set_page_config(
    page_title="🎓 HSC Dual AI Tutor",
    page_icon="🎓",
    layout="centered"
)

# =========================================
# CLEAN UI
# =========================================

st.markdown("""
<style>

/* App background */
.stApp {
    background-color: var(--background-color);
}

/* Chat box */
[data-testid="stChatMessage"] {
    border-radius: 18px;
    padding: 14px;
    margin-bottom: 12px;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128,128,128,0.15);
}

/* Buttons */
.stButton > button {
    border-radius: 12px;
    width: 100%;
}

/* Chat Input */
.stChatInputContainer {
    border-top: 1px solid rgba(128,128,128,0.15);
}

/* Login box */
.stTextInput input {
    border-radius: 12px;
}

</style>
""", unsafe_allow_html=True)

# =========================================
# HEADER
# =========================================

st.title("🎓 HSC Dual AI Tutor")

st.subheader("Gemini + Llama3 দিয়ে HSC প্রস্তুতি")

st.write("প্রশ্ন করো, ছবি বা PDF আপলোড করো, MCQ তৈরি করো!")

st.caption("🚀 Created by ALhaz")

# =========================================
# LOAD SECRETS
# =========================================

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")

# =========================================
# FIREBASE WEB CONFIG
# =========================================

firebase_config = {
    "apiKey": st.secrets["FIREBASE_API_KEY"],
    "authDomain": st.secrets["FIREBASE_AUTH_DOMAIN"],
    "projectId": st.secrets["FIREBASE_PROJECT_ID"],
    "storageBucket": st.secrets["FIREBASE_STORAGE_BUCKET"],
    "messagingSenderId": st.secrets["FIREBASE_MESSAGING_SENDER_ID"],
    "appId": st.secrets["FIREBASE_APP_ID"],
    "databaseURL": ""
}

firebase = pyrebase.initialize_app(firebase_config)

auth = firebase.auth()

# =========================================
# FIREBASE ADMIN
# =========================================

if not firebase_admin._apps:

    firebase_json = json.loads(
        st.secrets["FIREBASE_CREDENTIALS"]
    )

    cred = credentials.Certificate(firebase_json)

    firebase_admin.initialize_app(cred)

db = firestore.client()

# =========================================
# LOGIN SYSTEM
# =========================================

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:

    st.title("🔐 Login Required")

    auth_mode = st.selectbox(
        "Choose Option",
        ["Login", "Sign Up"]
    )

    email = st.text_input("📧 Email")

    password = st.text_input(
        "🔑 Password",
        type="password"
    )

    # SIGN UP
    if auth_mode == "Sign Up":

        if st.button("Create Account"):

            try:

                auth.create_user_with_email_and_password(
                    email,
                    password
                )

                st.success("✅ Account created successfully")

                st.info("👉 এখন Login অপশন থেকে login করো")

            except Exception as e:

                st.error(f"❌ {str(e)}")

    # LOGIN
    else:

        if st.button("Login"):

            try:

                user = auth.sign_in_with_email_and_password(
                    email,
                    password
                )

                user["email"] = email

                st.session_state.user = user

                st.success("✅ Login successful")

                st.rerun()

            except Exception as e:

                st.error(f"❌ {str(e)}")

    st.stop()

# =========================================
# USER ID
# =========================================

def get_unique_user_id():

    try:

        email = st.session_state.user["email"]

        safe_email = email.replace("@", "_").replace(".", "_")

        return safe_email

    except:

        return "unknown_user"

USER_ID = get_unique_user_id()

# =========================================
# SAVE CHAT
# =========================================

def save_message(role, content):

    db.collection("chat_history").add({
        "user_id": USER_ID,
        "role": role,
        "content": content,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

# =========================================
# LOAD CHAT HISTORY
# =========================================

def load_chat_history():

    chats = db.collection("chat_history") \
        .where("user_id", "==", USER_ID) \
        .order_by("timestamp") \
        .stream()

    messages = []

    for chat in chats:

        data = chat.to_dict()

        messages.append({
            "role": data["role"],
            "content": data["content"]
        })

    return messages

# =========================================
# CLEAR CHAT
# =========================================

def clear_chat_history():

    chats = db.collection("chat_history") \
        .where("user_id", "==", USER_ID) \
        .stream()

    for chat in chats:

        chat.reference.delete()

# =========================================
# SIDEBAR
# =========================================

st.sidebar.title("⚙️ Settings")

st.sidebar.success(
    f"👤 {st.session_state.user['email']}"
)

if st.sidebar.button("🚪 Logout"):

    st.session_state.user = None

    st.rerun()

if st.sidebar.button("🗑️ Clear Chat"):

    clear_chat_history()

    st.session_state.messages = []

    st.rerun()

model_choice = st.sidebar.radio(
    "🤖 AI Model",
    [
        "Gemini (Multimodal)",
        "Llama3 (Groq - Text Only)"
    ]
)

subject = st.sidebar.selectbox(
    "📚 বিষয় নির্বাচন করো",
    [

        # SCIENCE
        "Physics",
        "Chemistry",
        "Biology",
        "Higher Math",

        # HUMANITIES
        "History",
        "Economics",
        "Sociology",
        "Civics",
        "Geography",

        # BUSINESS
        "Accounting",
        "Finance",
        "Management",

        # COMPULSORY
        "Bangla",
        "English",
        "ICT",

        # OPTIONAL
        "Statistics",
        "Agriculture",
        "Psychology",
        "Islamic Studies"
    ]
)

# =========================================
# TELEGRAM NOTIFICATION
# =========================================

def send_telegram(user_id, q_text, model_name):

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    msg = f"""
🔔 নতুন প্রশ্ন!

👤 User: {user_id}
🤖 Model: {model_name}

❓ Question:
{q_text}
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:

        requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": msg
            },
            timeout=10
        )

    except:
        pass

# =========================================
# GEMINI
# =========================================

def call_gemini(api_key, text_prompt, image_pil=None):

    try:

        client = genai.Client(api_key=api_key)

        if image_pil:

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    text_prompt,
                    image_pil
                ]
            )

        else:

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=text_prompt
            )

        return response.text

    except Exception as e:

        error_text = str(e)

        # GROQ FALLBACK
        if "429" in error_text:

            try:

                client = Groq(api_key=GROQ_API_KEY)

                completion = client.chat.completions.create(

                    model="llama-3.3-70b-versatile",

                    messages=[
                        {
                            "role": "user",
                            "content": text_prompt
                        }
                    ]
                )

                return (
                    "⚠️ Gemini quota শেষ হয়েছে।\n\n"
                    + completion.choices[0].message.content
                )

            except Exception as groq_error:

                return f"❌ Fallback failed:\n{str(groq_error)}"

        return f"❌ Gemini Error:\n{error_text}"

# =========================================
# MCQ GENERATOR
# =========================================

if st.sidebar.button("📝 Generate MCQ"):

    mcq_prompt = f"""
    {subject} বিষয়ের HSC level এর
    10টি MCQ তৈরি করো।

    প্রতিটির সঠিক উত্তর দাও।
    """

    with st.spinner("MCQ তৈরি হচ্ছে..."):

        mcq_response = call_gemini(
            GEMINI_API_KEY,
            mcq_prompt
        )

    st.write(mcq_response)

# =========================================
# LOAD HISTORY
# =========================================

if "messages" not in st.session_state:

    st.session_state.messages = load_chat_history()

# =========================================
# SHOW HISTORY
# =========================================

for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):

        st.markdown(msg["content"])

st.markdown("---")

# =========================================
# CHAT INPUT
# =========================================

prompt = st.chat_input(
    "প্রশ্ন লেখো অথবা ছবি / PDF আপলোড করো...",
    accept_file=True,
    file_type=["jpg", "jpeg", "png", "pdf"]
)

# =========================================
# MAIN CHAT
# =========================================

if prompt:

    user_text = prompt.text

    uploaded_files = prompt.files

    image_to_send = None

    pdf_text = ""

    # SUBJECT MODE
    user_text = f"""
তুমি একজন {subject} বিষয়ের HSC শিক্ষক।

সহজ ভাষায় উত্তর দাও।

প্রশ্ন:
{user_text}
"""

    # FILE PROCESS
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

                extracted = page.extract_text()

                if extracted:
                    pdf_text += extracted

            st.success("✅ PDF Uploaded")

    # PDF TEXT
    if pdf_text:

        user_text += f"\n\nPDF Content:\n{pdf_text[:4000]}"

    # SHOW USER MESSAGE
    with st.chat_message("user"):

        if image_to_send:

            st.image(
                image_to_send,
                caption="Uploaded Image",
                width=250
            )

        if pdf_text:

            st.info("📄 PDF Uploaded")

        st.markdown(
            prompt.text if prompt.text
            else "[File Uploaded]"
        )

    # SAVE USER
    st.session_state.messages.append({
        "role": "user",
        "content": user_text
    })

    save_message("user", user_text)

    # TELEGRAM
    send_telegram(
        USER_ID,
        user_text,
        model_choice
    )

    # ASSISTANT
    with st.chat_message("assistant"):

        response_placeholder = st.empty()

        full_response = ""

        try:

            # GEMINI
            if model_choice == "Gemini (Multimodal)":

                full_response = call_gemini(
                    GEMINI_API_KEY,
                    user_text,
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

                    client = Groq(api_key=GROQ_API_KEY)

                    completion = client.chat.completions.create(

                        model="llama-3.3-70b-versatile",

                        messages=st.session_state.messages + [
                            {
                                "role": "user",
                                "content": user_text
                            }
                        ]
                    )

                    full_response = completion.choices[0].message.content

        except Exception as e:

            full_response = f"❌ Error:\n{str(e)}"

        # TYPING EFFECT
        typed_text = ""

        for char in full_response:

            typed_text += char

            response_placeholder.markdown(typed_text)

            time.sleep(0.01)

        # SAVE RESPONSE
        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response
        })

        save_message("assistant", full_response)