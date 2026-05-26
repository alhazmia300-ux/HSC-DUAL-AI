# ======================================================
# IMPORTS
# ======================================================

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

/* Main */
.stApp {
    background-color: var(--background-color);
}

/* Chat bubble */
[data-testid="stChatMessage"] {
    border-radius: 18px;
    padding: 14px;
    margin-bottom: 10px;
}

/* Buttons */
.stButton > button {
    width: 100%;
    border-radius: 12px;
}

/* Inputs */
.stTextInput input {
    border-radius: 12px;
}

/* Chat input */
.stChatInputContainer {
    border-top: 1px solid rgba(128,128,128,0.15);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128,128,128,0.15);
}

/* Compact sidebar */
section[data-testid="stSidebar"] div.block-container {
    padding-top: 1rem;
    padding-bottom: 0rem;
    gap: 0.3rem;
}

div[data-testid="stVerticalBlock"] > div {
    margin-bottom: 0.2rem;
}

section[data-testid="stSidebar"] .stButton {
    margin-bottom: -8px;
}

section[data-testid="stSidebar"] .stRadio {
    margin-bottom: -10px;
}

section[data-testid="stSidebar"] .stSelectbox {
    margin-bottom: -10px;
}

/* Login page */
.login-box {
    text-align:center;
    padding-top:80px;
    padding-bottom:40px;
}

.login-title {
    font-size:42px;
    font-weight:700;
}

.login-sub {
    font-size:18px;
    opacity:0.8;
}

</style>
""", unsafe_allow_html=True)

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
    "user_name": "",
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

    st.session_state.user_name = cookies.get("user_name")

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

    cookies["user_name"] = ""

    cookies.save()

    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.messages = []
    st.session_state.current_chat_id = None

# ======================================================
# CREATE CHAT
# ======================================================

def create_new_chat():

    chat_id = str(uuid.uuid4())

    db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .document(chat_id) \
        .set({

            "title": "New Chat",

            "created_at": firestore.SERVER_TIMESTAMP
        })

    st.session_state.current_chat_id = chat_id

    st.session_state.messages = []

# ======================================================
# SAVE MESSAGE
# ======================================================

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

            "created_at": firestore.SERVER_TIMESTAMP
        })

# ======================================================
# LOAD MESSAGES
# ======================================================

def load_messages(chat_id):

    chats = db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .document(chat_id) \
        .collection("messages") \
        .order_by(
            "created_at",
            direction=firestore.Query.ASCENDING
        ) \
        .stream()

    temp = []

    for chat in chats:

        data = chat.to_dict()

        temp.append({

            "role": data.get("role"),

            "content": data.get("content")
        })

    return temp

# ======================================================
# CHAT LIST
# ======================================================

def get_chat_list():

    chats = db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .order_by(
            "created_at",
            direction=firestore.Query.DESCENDING
        ) \
        .stream()

    temp = []

    for chat in chats:

        data = chat.to_dict()

        if data.get("title") != "New Chat":

            temp.append({

                "chat_id": chat.id,

                "title": data.get("title")
            })

    return temp

# ======================================================
# DELETE HISTORY
# ======================================================

def delete_all_history():

    chats = db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .stream()

    for chat in chats:

        messages = chat.reference.collection(
            "messages"
        ).stream()

        for msg in messages:

            msg.reference.delete()

        chat.reference.delete()

# ======================================================
# LOGIN PAGE
# ======================================================

if not st.session_state.logged_in:

    st.markdown("""
    <div class="login-box">

    <div class="login-title">
    Welcome my friend
    </div>

    <div class="login-sub">
    This platform is created by ALhaz
    </div>

    </div>
    """, unsafe_allow_html=True)

    option = st.selectbox(
        "Choose Option",
        ["Login", "Sign Up"]
    )

    with st.form("auth_form"):

        name = st.text_input(
            "👤 Enter your name"
        )

        email = st.text_input(
            "📧 Enter email / phone number"
        )

        password = st.text_input(
            "🔑 Enter password",
            type="password"
        )

        submit = st.form_submit_button("Continue")

    if submit:

        if not name or not email or not password:

            st.warning("সব তথ্য পূরণ করো")

            st.stop()

        auth_email = email

        if "@" not in auth_email:

            auth_email = f"{email}@phoneuser.com"

        # ==================================================
        # SIGNUP
        # ==================================================

        if option == "Sign Up":

            result = signup(
                auth_email,
                password
            )

            if "email" in result:

                user_id = hashlib.md5(
                    auth_email.encode()
                ).hexdigest()

                db.collection("profiles") \
                    .document(user_id) \
                    .set({

                        "name": name,

                        "email_or_phone": email
                    })

                st.success(
                    "✅ Account Created"
                )

            else:

                st.error(
                    result.get("error", {})
                    .get("message")
                )

        # ==================================================
        # LOGIN
        # ==================================================

        else:

            result = login(
                auth_email,
                password
            )

            if "email" in result:

                user_id = hashlib.md5(
                    auth_email.encode()
                ).hexdigest()

                profile = db.collection("profiles") \
                    .document(user_id) \
                    .get()

                profile_data = profile.to_dict()

                st.session_state.logged_in = True

                st.session_state.user_email = auth_email

                st.session_state.user_name = profile_data.get(
                    "name",
                    "User"
                )

                cookies["logged_in"] = "true"

                cookies["user_email"] = auth_email

                cookies["user_name"] = st.session_state.user_name

                cookies.save()

                st.rerun()

            else:

                st.error(
                    result.get("error", {})
                    .get("message")
                )

    st.stop()

# ======================================================
# MAIN HEADER
# ======================================================

header_left, header_right = st.columns([12,1])

with header_left:

    st.title("🎓 HSC Dual AI Tutor")

    st.subheader("Llama3 এবং Gemini-র সমন্বয়ে HSC প্রস্তুতি")

    st.write("তোমার HSC পরীক্ষার যেকোনো বিষয়ের প্রশ্ন এখানে জিজ্ঞেস করো!")

    st.caption("🚀 Created by ALhaz")

with header_right:

    st.write("")

    st.write("")

    if st.button("➕", help="New Chat"):

        st.session_state.current_chat_id = None

        st.session_state.messages = []

        st.rerun()

# ======================================================
# SIDEBAR
# ======================================================

st.sidebar.markdown("# ⚙️ Settings")

st.sidebar.markdown("---")

# ======================================================
# PROFILE
# ======================================================

st.sidebar.write(
    f"👤 {st.session_state.user_name}"
)

st.sidebar.write(
    f"📧 {st.session_state.user_email}"
)

profile_pic = st.sidebar.file_uploader(
    "🖼️ Upload Profile Picture",
    type=["jpg", "jpeg", "png"]
)

if profile_pic:

    st.sidebar.image(
        profile_pic,
        width=120
    )

st.sidebar.markdown("---")

# ======================================================
# MODEL
# ======================================================

model_choice = st.sidebar.radio(
    "🤖 AI Model",
    ["Gemini", "Llama3"]
)

# ======================================================
# SUBJECT
# ======================================================

subject = st.sidebar.selectbox(
    "📚 Subject",
    [
        "Physics",
        "Chemistry",
        "Biology",
        "Higher Math",
        "Bangla",
        "English",
        "ICT",
        "Economics",
        "Accounting",
        "History",
        "Sociology",
        "Finance",
        "Management"
    ]
)

st.sidebar.markdown("---")

# ======================================================
# NEW CHAT
# ======================================================

if st.sidebar.button(
    "➕ New Chat",
    use_container_width=True
):

    st.session_state.current_chat_id = None

    st.session_state.messages = []

    st.rerun()

# ======================================================
# CHAT HISTORY
# ======================================================

st.sidebar.markdown("## 💬 Chats History")

try:

    chat_list = get_chat_list()

    if chat_list:

        for chat in chat_list:

            title = chat["title"]

            chat_id = chat["chat_id"]

            if st.sidebar.button(
                f"💬 {title}",
                key=chat_id,
                use_container_width=True
            ):

                st.session_state.current_chat_id = chat_id

                st.session_state.messages = load_messages(
                    chat_id
                )

                st.rerun()

    else:

        st.sidebar.info(
            "কোনো পুরোনো চ্যাট নেই"
        )

except:

    st.sidebar.info(
        "কোনো পুরোনো চ্যাট নেই"
    )

st.sidebar.markdown("---")

# ======================================================
# LOGOUT
# ======================================================

if st.sidebar.button(
    "🚪 Logout",
    use_container_width=True
):

    logout()

    st.rerun()

# ======================================================
# DELETE HISTORY
# ======================================================

if st.sidebar.button(
    "🗑️ Delete All History",
    use_container_width=True
):

    delete_all_history()

    st.session_state.messages = []

    st.session_state.current_chat_id = None

    st.rerun()

# ======================================================
# LOAD CURRENT CHAT
# ======================================================

if (
    st.session_state.current_chat_id
    and not st.session_state.messages
):

    try:

        st.session_state.messages = load_messages(
            st.session_state.current_chat_id
        )

    except:

        st.session_state.messages = []

# ======================================================
# CHAT INPUT
# ======================================================

prompt = st.chat_input(
    "প্রশ্ন লেখো অথবা ছবি/PDF আপলোড করো...",
    accept_file=True,
    file_type=["jpg", "jpeg", "png", "pdf"]
)

# ======================================================
# GEMINI
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
# SHOW CHAT
# ======================================================

for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):

        st.markdown(msg["content"])

# ======================================================
# MAIN CHAT SYSTEM
# ======================================================

if prompt:

    if not st.session_state.current_chat_id:

        create_new_chat()

    image_to_send = None
    pdf_text = ""
    user_text = ""
    uploaded_file = None

    if prompt.text:

        user_text = prompt.text

    if prompt.files:

        uploaded_file = prompt.files[0]

    # ==================================================
    # FILE PROCESSING
    # ==================================================

    if uploaded_file:

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

                    txt = page.extract_text()

                    if txt:

                        pdf_text += txt

            except Exception as e:

                st.error(
                    f"PDF Error: {e}"
                )

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
            .document(
                st.session_state.current_chat_id
            ) \
            .update({

                "title": short_title
            })

    # ==================================================
    # AI RESPONSE
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

                    full_response = """
⚠️ Llama3 ছবি বুঝতে পারে না।

Gemini ব্যবহার করো।
"""

                else:

                    client = Groq(
                        api_key=GROQ_API_KEY
                    )

                    completion = client.chat.completions.create(

                        model="llama-3.3-70b-versatile",

                        messages=[

                            {
                                "role": "system",
                                "content":
                                f"You are an HSC {subject} teacher answering in Bengali."
                            },

                            {
                                "role": "user",
                                "content": final_prompt
                            }
                        ]
                    )

                    full_response = completion \
                        .choices[0] \
                        .message.content

        except Exception as e:

            full_response = str(e)

        # ==================================================
        # TYPING EFFECT
        # ==================================================

        typed = ""

        for char in full_response:

            typed += char

            placeholder.markdown(typed)

            time.sleep(0.001)

        st.session_state.messages.append({

            "role": "assistant",

            "content": full_response
        })

        save_message(
            "assistant",
            full_response
        )