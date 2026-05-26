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

from firebase_admin import credentials
from firebase_admin import firestore

from streamlit_cookies_manager import EncryptedCookieManager

# ======================================================
# PAGE CONFIG
# ======================================================

st.set_page_config(
    page_title="🎓 HSC Dual AI Tutor",
    page_icon="🎓",
    layout="wide"
)

# ======================================================
# CUSTOM CSS
# ======================================================

st.markdown("""
<style>

.stApp {
    background-color: var(--background-color);
}

[data-testid="stChatMessage"] {
    border-radius: 18px;
    padding: 14px;
    margin-bottom: 12px;
}

.stButton > button {
    width: 100%;
    border-radius: 12px;
}

.stTextInput input {
    border-radius: 12px;
}

.stChatInputContainer {
    border-top: 1px solid rgba(128,128,128,0.15);
}

section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128,128,128,0.15);
}

</style>
""", unsafe_allow_html=True)

# ======================================================
# HEADER
# ======================================================

st.title("🎓 HSC Dual AI Tutor")

st.subheader("Llama3 এবং Gemini-র সমন্বয়ে HSC প্রস্তুতি")

st.write("তোমার HSC পরীক্ষার যেকোনো বিষয়ের প্রশ্ন এখানে জিজ্ঞেস করো!")

st.caption("🚀 Created by ALhaz")

# ======================================================
# SECRETS
# ======================================================

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

FIREBASE_API_KEY = st.secrets.get("FIREBASE_API_KEY")

# ======================================================
# COOKIES
# ======================================================

cookies = EncryptedCookieManager(
    prefix="hsc_ai_",
    password="ALhaz_secure_password"
)

if not cookies.ready():
    st.stop()

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

defaults = {

    "logged_in": False,

    "user_email": "",

    "messages": [],

    "current_chat_id": None
}

for key, value in defaults.items():

    if key not in st.session_state:

        st.session_state[key] = value

# ======================================================
# AUTO LOGIN
# ======================================================

if cookies.get("logged_in") == "true":

    st.session_state.logged_in = True

    st.session_state.user_email = cookies.get("user_email")

# ======================================================
# USER ID
# ======================================================

def get_user_id():

    return hashlib.md5(
        st.session_state.user_email.encode()
    ).hexdigest()

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

# ======================================================
# LOGOUT
# ======================================================

def logout():

    cookies["logged_in"] = ""

    cookies["user_email"] = ""

    cookies.save()

    st.session_state.logged_in = False

    st.session_state.user_email = ""

    st.session_state.messages = []

    st.session_state.current_chat_id = None

# ======================================================
# CHAT DATABASE
# ======================================================

def create_new_chat():

    chat_id = str(uuid.uuid4())

    db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .document(chat_id) \
        .set({

            "title": "New Chat",

            "created_at": time.time()
        })

    st.session_state.current_chat_id = chat_id

    st.session_state.messages = []

def save_message(role, content):

    if not st.session_state.current_chat_id:
        create_new_chat()

    db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .document(st.session_state.current_chat_id) \
        .collection("messages") \
        .add({

            "role": role,

            "content": content,

            "created_at": time.time()
        })

def load_messages(chat_id):

    chats = db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .document(chat_id) \
        .collection("messages") \
        .stream()

    temp = []

    for chat in chats:

        data = chat.to_dict()

        temp.append({

            "role": data.get("role"),

            "content": data.get("content"),

            "created_at": data.get("created_at", 0)
        })

    temp.sort(key=lambda x: x["created_at"])

    final = []

    for item in temp:

        final.append({

            "role": item["role"],

            "content": item["content"]
        })

    return final

def get_chat_list():

    chats = db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .stream()

    temp = []

    for chat in chats:

        data = chat.to_dict()

        temp.append({

            "chat_id": chat.id,

            "title": data.get("title", "Chat"),

            "created_at": data.get("created_at", 0)
        })

    temp.sort(
        key=lambda x: x["created_at"],
        reverse=True
    )

    return temp

# ======================================================
# LOGIN PAGE
# ======================================================

if not st.session_state.logged_in:

    st.subheader("🔐 Login / Sign Up")

    option = st.selectbox(
        "Choose Option",
        ["Login", "Sign Up"]
    )

    with st.form("auth"):

        email = st.text_input("📧 Email")

        password = st.text_input(
            "🔑 Password",
            type="password"
        )

        submit = st.form_submit_button("Continue")

    if submit:

        if option == "Sign Up":

            result = signup(email, password)

            if "email" in result:

                st.success("✅ Account Created")

            else:

                st.error(
                    result.get("error", {})
                    .get("message")
                )

        else:

            result = login(email, password)

            if "email" in result:

                st.session_state.logged_in = True

                st.session_state.user_email = result["email"]

                cookies["logged_in"] = "true"

                cookies["user_email"] = result["email"]

                cookies.save()

                st.rerun()

            else:

                st.error(
                    result.get("error", {})
                    .get("message")
                )

    st.stop()

# ======================================================
# SIDEBAR
# ======================================================

st.sidebar.success(st.session_state.user_email)

# ======================================================
# NEW CHAT
# ======================================================
if st.sidebar.button("➕ New Chat", use_container_width=True):
    create_new_chat()
    st.rerun()

# ======================================================
# CHAT HISTORY (ড্রপডাউন মেনু দিয়ে রিডিজাইন করা)
# ======================================================
st.sidebar.markdown("## 💬 Chats History")

chat_list = get_chat_list()

if chat_list:
    # পুরনো চ্যাটগুলোর টাইটেল ও আইডির একটি ডিকশনারি তৈরি
    chat_options = {chat["title"]: chat["chat_id"] for chat in chat_list}
    
    # বর্তমান চ্যাটটি ড্রপডাউনে ডিফল্ট সিলেক্ট রাখার লজিক
    default_index = 0
    if st.session_state.current_chat_id:
        for i, chat in enumerate(chat_list):
            if chat["chat_id"] == st.session_state.current_chat_id:
                default_index = i
                break
                
    # শত শত বাটনের বদলে একটি সুন্দর ড্রপডাউন মেনু
    selected_chat_title = st.sidebar.selectbox(
        "Select past chat",
        options=list(chat_options.keys()),
        index=default_index,
        label_visibility="collapsed"
    )
    
    # ইউজার ড্রপডাউন থেকে অন্য চ্যাট সিলেক্ট করলে সেটি লোড হবে
    selected_chat_id = chat_options[selected_chat_title]
    if selected_chat_id != st.session_state.current_chat_id:
        st.session_state.current_chat_id = selected_chat_id
        st.session_state.messages = load_messages(selected_chat_id)
        st.rerun()
else:
    st.sidebar.caption("No past chats found.")

st.sidebar.markdown("---")

# ======================================================
# LOGOUT
# ======================================================
if st.sidebar.button("🚪 Logout", use_container_width=True):
    logout()
    st.rerun()

# ======================================================
# AUTO CREATE CHAT
# ======================================================
if not st.session_state.current_chat_id:
    create_new_chat()

# ======================================================
# MODEL SELECT
# ======================================================
model_choice = st.sidebar.radio(
    "🤖 AI Model",
    ["Gemini", "Llama3"]
)

# ======================================================
# SUBJECT SELECT
# ======================================================
subject = st.sidebar.selectbox(
    "📚 Subject",
    [
        "Physics", "Chemistry", "Biology", "Higher Math",
        "Bangla", "English", "ICT", "Economics", 
        "Accounting", "History", "Sociology", "Finance", "Management"
    ]
)

# ======================================================
# GEMINI FUNCTION
# ======================================================

def call_gemini(prompt_text, image_obj=None):

    for attempt in range(3):

        try:

            client = genai.Client(
                api_key=GEMINI_API_KEY
            )

            # IMAGE INPUT
            if image_obj:

                response = client.models.generate_content(

                    model="gemini-2.5-flash",

                    contents=[
                        prompt_text,
                        image_obj
                    ]
                )

            # TEXT INPUT
            else:

                response = client.models.generate_content(

                    model="gemini-2.5-flash",

                    contents=prompt_text
                )

            return response.text

        except Exception as e:

            error_text = str(e)

            # Retry if 503
            if "503" in error_text or "UNAVAILABLE" in error_text:

                time.sleep(3)

                continue

            return f"❌ Gemini Error:\n{error_text}"

    # =====================================================
    # FALLBACK AFTER 3 FAILED ATTEMPTS
    # =====================================================

    # IMAGE থাকলে fallback possible না
    if image_obj:

        return """
⚠️ Gemini server বর্তমানে খুব busy।

ছবি/PDF বিশ্লেষণের জন্য Gemini প্রয়োজন।

⏳ কিছুক্ষণ পরে আবার চেষ্টা করো।
"""

    # TEXT হলে fallback
    try:

        client = Groq(
            api_key=GROQ_API_KEY
        )

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[

                {
                    "role": "system",
                    "content":
                    "You are an expert HSC teacher answering in Bengali."
                },

                {
                    "role": "user",
                    "content": prompt_text
                }
            ]
        )

        return (
            "⚠️ Gemini server busy ছিল, তাই Llama3 দিয়ে উত্তর দেওয়া হলো:\n\n"
            + completion.choices[0].message.content
        )

    except Exception as fallback_error:

        return f"❌ Fallback Error:\n{str(fallback_error)}"

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
    # FILE PROCESSING
    # ==================================================

    if uploaded_files and len(uploaded_files) > 0:

        uploaded_file = uploaded_files[0]

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

            reader = PyPDF2.PdfReader(
                uploaded_file
            )

            for page in reader.pages:

                txt = page.extract_text()

                if txt:
                    pdf_text += txt

    # ==================================================
    # FINAL PROMPT
    # ==================================================

    final_prompt = f"""

তুমি একজন {subject} বিষয়ের HSC শিক্ষক।

সহজ বাংলায় উত্তর দাও।

প্রশ্ন:
{user_text}

"""

    if pdf_text:

        final_prompt += f"""

PDF:
{pdf_text[:12000]}
"""

    # ==================================================
    # SHOW USER MESSAGE
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

    # ==================================================
    # AUTO CHAT TITLE
    # ==================================================

    if len(st.session_state.messages) <= 2:

        short_title = display_text[:35]

        db.collection("users") \
            .document(get_user_id()) \
            .collection("chats") \
            .document(st.session_state.current_chat_id) \
            .update({

                "title": short_title
            })

    # ==================================================
    # ASSISTANT RESPONSE
    # ==================================================

    with st.chat_message("assistant"):

        placeholder = st.empty()

        full_response = ""

        try:

            # GEMINI
            if model_choice == "Gemini":

                full_response = call_gemini(
                    final_prompt,
                    image_to_send
                )

            # LLAMA3
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

                    groq_messages = [

                        {
                            "role": "system",
                            "content":
                            f"You are an HSC {subject} teacher answering in Bengali."
                        }
                    ]

                    for m in st.session_state.messages[-10:]:

                        groq_messages.append({

                            "role": m["role"],

                            "content": m["content"]
                        })

                    groq_messages.append({

                        "role": "user",

                        "content": final_prompt
                    })

                    completion = client.chat.completions.create(

                        model="llama-3.3-70b-versatile",

                        messages=groq_messages
                    )

                    full_response = completion.choices[0].message.content

        except Exception as e:

            full_response = str(e)

        # ==================================================
        # TYPING EFFECT
        # ==================================================

        typed = ""

        for char in full_response:

            typed += char

            placeholder.markdown(typed)

            time.sleep(0.003)

        st.session_state.messages.append({

            "role": "assistant",

            "content": full_response
        })

        save_message(
            "assistant",
            full_response
        )