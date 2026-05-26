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

/* Main App */
.stApp {
    background-color: var(--background-color);
}

/* Chat Bubble */
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

/* Input Box */
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
# LOAD SECRETS
# ======================================================

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

FIREBASE_API_KEY = st.secrets.get("FIREBASE_API_KEY")

TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")

# ======================================================
# FIREBASE INIT
# ======================================================

@st.cache_resource
def init_firestore():

    if not firebase_admin._apps:

        firebase_json = json.loads(
            st.secrets["FIREBASE_CREDENTIALS"]
        )

        cred = credentials.Certificate(firebase_json)

        firebase_admin.initialize_app(cred)

    return firestore.client()

db = init_firestore()

# ======================================================
# SESSION STATE
# ======================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_email" not in st.session_state:
    st.session_state.user_email = ""

if "messages" not in st.session_state:
    st.session_state.messages = []

# ======================================================
# FIREBASE AUTH
# ======================================================

def signup(email, password):

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    try:

        r = requests.post(
            url,
            json=payload,
            timeout=10
        )

        return r.json()

    except Exception as e:

        return {
            "error": {
                "message": str(e)
            }
        }

def login(email, password):

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    try:

        r = requests.post(
            url,
            json=payload,
            timeout=10
        )

        return r.json()

    except Exception as e:

        return {
            "error": {
                "message": str(e)
            }
        }

def logout():

    st.session_state.logged_in = False

    st.session_state.user_email = ""

    st.session_state.messages = []

# ======================================================
# USER ID
# ======================================================

def get_user_id():

    email = st.session_state.user_email

    return hashlib.md5(
        email.encode()
    ).hexdigest()

# ======================================================
# SAVE MESSAGE
# ======================================================

def save_message(role, content):

    try:

        if not content:
            return

        db.collection("chat_history").add({

            "user_id": get_user_id(),

            "role": role,

            "content": content,

            "timestamp": firestore.SERVER_TIMESTAMP
        })

    except:
        pass

# ======================================================
# LOAD CHAT HISTORY
# ======================================================

def load_chat_history():

    try:

        chats = db.collection("chat_history") \
            .where("user_id", "==", get_user_id()) \
            .order_by("timestamp") \
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

        return []

# ======================================================
# CLEAR CHAT
# ======================================================

def clear_chat_history():

    try:

        chats = db.collection("chat_history") \
            .where("user_id", "==", get_user_id()) \
            .stream()

        for chat in chats:

            chat.reference.delete()

    except:
        pass

# ======================================================
# LOGIN / SIGNUP PAGE
# ======================================================

if not st.session_state.logged_in:

    st.subheader("🔐 Login / Sign Up")

    option = st.selectbox(
        "Choose Option",
        ["Login", "Sign Up"]
    )

    # ==================================================
    # FORM FIX
    # ==================================================

    with st.form("auth_form"):

        email = st.text_input("📧 Email")

        password = st.text_input(
            "🔑 Password",
            type="password"
        )

        submit = st.form_submit_button(
            "Continue"
        )

    # ==================================================
    # PROCESS
    # ==================================================

    if submit:

        clean_email = email.strip()

        clean_password = password.strip()

        if clean_email == "" or clean_password == "":

            st.warning(
                "⚠️ Email এবং Password লিখো"
            )

            st.stop()

        # ==================================================
        # SIGNUP
        # ==================================================

        if option == "Sign Up":

            with st.spinner("Creating Account..."):

                result = signup(
                    clean_email,
                    clean_password
                )

            if "email" in result:

                st.success(
                    "✅ Account Created Successfully!"
                )

                st.info(
                    "👉 এখন Login করো"
                )

            else:

                err = result.get(
                    "error",
                    {}
                ).get(
                    "message",
                    "Signup Failed"
                )

                st.error(f"❌ {err}")

        # ==================================================
        # LOGIN
        # ==================================================

        else:

            with st.spinner("Logging in..."):

                result = login(
                    clean_email,
                    clean_password
                )

            if "email" in result:

                st.session_state.logged_in = True

                st.session_state.user_email = result["email"]

                st.session_state.messages = load_chat_history()

                st.success("✅ Login Successful")

                time.sleep(1)

                st.rerun()

            else:

                err = result.get(
                    "error",
                    {}
                ).get(
                    "message",
                    "Invalid Credentials"
                )

                st.error(f"❌ {err}")

    st.stop()

# ======================================================
# SIDEBAR
# ======================================================

st.sidebar.success(
    f"👤 {st.session_state.user_email}"
)

if st.sidebar.button(
    "🚪 Logout",
    use_container_width=True
):

    logout()

    st.rerun()

if st.sidebar.button(
    "🗑️ Clear Chat",
    use_container_width=True
):

    clear_chat_history()

    st.session_state.messages = []

    st.rerun()

# ======================================================
# MODEL SELECT
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

        # Mandatory
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

if st.sidebar.button(
    "📝 Generate MCQ",
    use_container_width=True
):

    mcq_prompt = f"""
তুমি একজন {subject} বিষয়ের HSC শিক্ষক।

১০টি গুরুত্বপূর্ণ MCQ তৈরি করো।

প্রতিটির সঠিক উত্তর ও ব্যাখ্যা দাও।
"""

    with st.spinner("Generating MCQ..."):

        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=mcq_prompt
        )

        st.markdown("---")

        st.markdown(response.text)

# ======================================================
# TELEGRAM LOGGER
# ======================================================

def send_telegram(message):

    if not TELEGRAM_BOT_TOKEN:
        return

    if not TELEGRAM_CHAT_ID:
        return

    try:

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        requests.post(

            url,

            json={

                "chat_id": TELEGRAM_CHAT_ID,

                "text": message[:1000]
            },

            timeout=5
        )

    except:
        pass

# ======================================================
# GEMINI FUNCTION
# ======================================================

def call_gemini(prompt_text, image_obj=None):

    try:

        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        if image_obj:

            response = client.models.generate_content(

                model="gemini-2.5-flash",

                contents=[
                    prompt_text,
                    image_obj
                ]
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
# SHOW CHAT HISTORY
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

    file_type=[
        "jpg",
        "jpeg",
        "png",
        "pdf"
    ]
)

# ======================================================
# MAIN CHAT SYSTEM
# ======================================================

if prompt:

    user_text = prompt.text if prompt.text else ""

    uploaded_files = prompt.files

    image_to_send = None

    pdf_text = ""

    # ==================================================
    # FILE HANDLING
    # ==================================================

    if uploaded_files and len(uploaded_files) > 0:

        uploaded_file = uploaded_files[0]

        # FILE SIZE LIMIT
        if uploaded_file.size > 5 * 1024 * 1024:

            st.error("❌ ফাইল খুব বড়")

            st.stop()

        file_name = uploaded_file.name.lower()

        # IMAGE
        if file_name.endswith((
            ".jpg",
            ".jpeg",
            ".png"
        )):

            image_to_send = Image.open(
                uploaded_file
            )

        # PDF
        elif file_name.endswith(".pdf"):

            try:

                reader = PyPDF2.PdfReader(
                    uploaded_file
                )

                for page in reader.pages:

                    text = page.extract_text()

                    if text:

                        pdf_text += text

                st.success(
                    "✅ PDF Uploaded"
                )

            except Exception as e:

                st.error(
                    f"PDF Error: {str(e)}"
                )

    # ==================================================
    # PROMPT
    # ==================================================

    user_prompt = f"""
তুমি একজন {subject} বিষয়ের HSC শিক্ষক।

সহজ বাংলায় উত্তর দাও।

প্রশ্ন:
{user_text}
"""

    if pdf_text:

        user_prompt += f"""

PDF CONTENT:
{pdf_text[:12000]}
"""

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
            user_text
            if user_text
            else "[📎 File Uploaded]"
        )

    display_text = (
        user_text
        if user_text
        else "[📎 File Uploaded]"
    )

    st.session_state.messages.append({

        "role": "user",

        "content": display_text
    })

    save_message(
        "user",
        display_text
    )

    send_telegram(display_text)

    # ==================================================
    # ASSISTANT RESPONSE
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

            # LLAMA3
            else:

                if image_to_send:

                    full_response = (
                        "⚠️ Llama3 ছবি বুঝতে পারে না। "
                        "Gemini ব্যবহার করো।"
                    )

                elif not GROQ_API_KEY:

                    full_response = (
                        "⚠️ GROQ API KEY নেই"
                    )

                else:

                    client = Groq(
                        api_key=GROQ_API_KEY
                    )

                    recent_messages = st.session_state.messages[-10:]

                    groq_messages = [

                        {
                            "role": "system",
                            "content":
                            f"You are an HSC {subject} teacher. Answer in Bengali."
                        }
                    ]

                    for m in recent_messages:

                        groq_messages.append({

                            "role": m["role"],

                            "content": m["content"]
                        })

                    groq_messages.append({

                        "role": "user",

                        "content": user_prompt
                    })

                    completion = client.chat.completions.create(

                        model="llama-3.3-70b-versatile",

                        messages=groq_messages
                    )

                    full_response = completion.choices[0].message.content

        except Exception as e:

            full_response = f"❌ Error:\n{str(e)}"

        # ==================================================
        # TYPING EFFECT
        # ==================================================

        typed = ""

        for char in full_response:

            typed += char

            response_placeholder.markdown(
                typed
            )

            time.sleep(0.003)

        st.session_state.messages.append({

            "role": "assistant",

            "content": full_response
        })

        save_message(
            "assistant",
            full_response
        )