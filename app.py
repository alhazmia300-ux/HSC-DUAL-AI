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
import base64

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

.block-container{
    padding-top:1rem;
}

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
    border-right: 1px solid rgba(128,128,128,0.12);
}

.profile-container{
    text-align:center;
    margin-bottom:8px;
}

.profile-pic{
    width:90px;
    height:90px;
    border-radius:50%;
    object-fit:cover;
    border:3px solid #4CAF50;
    margin:auto;
    display:block;
}

.small-gap{
    margin-top:-12px;
}

.new-chat-btn button{
    height:42px;
    width:42px !important;
    border-radius:50% !important;
    font-size:20px !important;
    float:right;
}

.chat-history-btn button{
    text-align:left !important;
    justify-content:flex-start !important;
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
    "current_chat_id": None,
    "profile_pic": ""

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
    st.session_state.profile_pic = cookies.get("profile_pic")

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
    cookies["profile_pic"] = ""

    cookies.save()

    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.messages = []
    st.session_state.current_chat_id = None

# ======================================================
# CHAT FUNCTIONS
# ======================================================

def create_new_chat():

    st.session_state.current_chat_id = str(uuid.uuid4())
    st.session_state.messages = []

def save_message(role, content):

    if not st.session_state.current_chat_id:
        return

    chat_ref = db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .document(st.session_state.current_chat_id)

    chat_doc = chat_ref.get()

    # FIRST MESSAGE -> CREATE CHAT
    if not chat_doc.exists:

        title = content[:35] if content else "New Chat"

        chat_ref.set({
            "title": title,
            "created_at": time.time()
        })

    chat_ref.collection("messages").add({

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
            "title": data.get("title", "New Chat"),
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

    st.markdown("<br><br>", unsafe_allow_html=True)

    st.markdown("""
    <h1 style='text-align:center;'>
    Welcome my friend 👋
    </h1>
    """, unsafe_allow_html=True)

    st.markdown("""
    <p style='text-align:center;font-size:18px;color:gray;'>
    This platform is created by ALhaz
    </p>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    option = st.selectbox(
        "Choose Option",
        ["Login", "Sign Up"]
    )

    with st.form("auth"):

        name = st.text_input(
            "👤 Enter your name"
        )

        email = st.text_input(
            "📧 Enter email/phone number"
        )

        password = st.text_input(
            "🔑 Password",
            type="password"
        )

        submit = st.form_submit_button("Continue")

    if submit:

        if not name.strip():

            st.warning("Name required")
            st.stop()

        if not email.strip():

            st.warning("Email/Phone required")
            st.stop()

        if not password.strip():

            st.warning("Password required")
            st.stop()

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
                st.session_state.user_name = name

                cookies["logged_in"] = "true"
                cookies["user_email"] = result["email"]
                cookies["user_name"] = name

                cookies.save()

                st.rerun()

            else:

                st.error(
                    result.get("error", {})
                    .get("message")
                )

    st.stop()

# ======================================================
# HEADER
# ======================================================

col1, col2 = st.columns([10,1])

with col1:

    st.title("🎓 HSC Dual AI Tutor")

    st.subheader(
        "Llama3 এবং Gemini-র সমন্বয়ে HSC প্রস্তুতি"
    )

    st.write(
        "তোমার HSC পরীক্ষার যেকোনো বিষয়ের প্রশ্ন এখানে জিজ্ঞেস করো!"
    )

    st.caption("🚀 Created by ALhaz")

with col2:

    st.markdown("<div class='new-chat-btn'>", unsafe_allow_html=True)

    if st.button("➕"):

        create_new_chat()
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ======================================================
# SIDEBAR
# ======================================================

st.sidebar.markdown("""
<h1 style='margin-bottom:0px;'>⚙️ Settings</h1>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

# ======================================================
# PROFILE PIC
# ======================================================

uploaded_profile = st.sidebar.file_uploader(
    " ",
    type=["jpg","jpeg","png"]
)

if uploaded_profile:

    image_bytes = uploaded_profile.read()

    encoded = base64.b64encode(
        image_bytes
    ).decode()

    st.session_state.profile_pic = encoded

    cookies["profile_pic"] = encoded

    cookies.save()

# ======================================================
# SHOW PROFILE
# ======================================================

if st.session_state.profile_pic:

    st.sidebar.markdown(f"""
    <div class="profile-container">
        <img src="data:image/png;base64,{st.session_state.profile_pic}" class="profile-pic">
    </div>
    """, unsafe_allow_html=True)

else:

    st.sidebar.markdown("""
    <div class="profile-container">
        <img src="https://cdn-icons-png.flaticon.com/512/3135/3135715.png" class="profile-pic">
    </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown(
    f"### 👤 {st.session_state.user_name}"
)

st.sidebar.caption(
    st.session_state.user_email
)

# ======================================================
# MODEL
# ======================================================

st.sidebar.markdown("### 🤖 AI Model")

model_choice = st.sidebar.radio(
    "",
    ["Gemini", "Llama3"],
    label_visibility="collapsed"
)

# ======================================================
# SUBJECT
# ======================================================

st.sidebar.markdown("### 📚 Subject")

subject = st.sidebar.selectbox(
    "",
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
        "History"
    ],
    label_visibility="collapsed"
)

# ======================================================
# SEARCH CHAT
# ======================================================

st.sidebar.markdown("### 🔍 Search Chat")

search_chat = st.sidebar.text_input(
    "",
    placeholder="Search history...",
    label_visibility="collapsed"
)

# ======================================================
# CHAT HISTORY
# ======================================================

st.sidebar.markdown("### 💬 Chats")

chat_list = get_chat_list()

filtered_chats = []

for chat in chat_list:

    title = chat.get("title", "New Chat")

    if search_chat.lower() in title.lower():

        filtered_chats.append(chat)

for chat in filtered_chats:

    if st.sidebar.button(
        f"📝 {chat['title']}",
        key=chat["chat_id"],
        use_container_width=True
    ):

        st.session_state.current_chat_id = chat["chat_id"]

        st.session_state.messages = load_messages(
            chat["chat_id"]
        )

        st.rerun()

# ======================================================
# BOTTOM SIDEBAR
# ======================================================

st.sidebar.markdown("---")

if st.sidebar.button(
    "🚪 Logout",
    use_container_width=True
):

    logout()
    st.rerun()

# ======================================================
# GEMINI FUNCTION
# ======================================================

def call_gemini(prompt_text, image_obj=None):

    for attempt in range(3):

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

            error_text = str(e)

            if "503" in error_text:

                time.sleep(3)
                continue

            return f"❌ Gemini Error:\n{error_text}"

    if image_obj:

        return """
⚠️ Gemini server busy।

ছবি/PDF বিশ্লেষণের জন্য Gemini প্রয়োজন।

⏳ কিছুক্ষণ পরে আবার চেষ্টা করো।
"""

    try:

        client = Groq(
            api_key=GROQ_API_KEY
        )

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[

                {
                    "role":"system",
                    "content":"You are expert HSC teacher."
                },

                {
                    "role":"user",
                    "content":prompt_text
                }
            ]
        )

        return (
            "⚠️ Gemini busy ছিল তাই Llama3 ব্যবহার করা হয়েছে:\n\n"
            + completion.choices[0].message.content
        )

    except Exception as fallback_error:

        return str(fallback_error)

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

    file_type=[
        "jpg",
        "jpeg",
        "png",
        "pdf"
    ]
)

# ======================================================
# MAIN CHAT
# ======================================================

if prompt:

    if not st.session_state.current_chat_id:

        create_new_chat()

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

        if file_name.endswith((
            ".jpg",
            ".jpeg",
            ".png"
        )):

            image_to_send = Image.open(
                uploaded_file
            )

        elif file_name.endswith(".pdf"):

            reader = PyPDF2.PdfReader(
                uploaded_file
            )

            for page in reader.pages:

                txt = page.extract_text()

                if txt:

                    pdf_text += txt

    # ==================================================
    # PROMPT
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
    # USER MESSAGE
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

        "role":"user",
        "content":display_text

    })

    save_message(
        "user",
        display_text
    )

    # ==================================================
    # ASSISTANT
    # ==================================================

    with st.chat_message("assistant"):

        placeholder = st.empty()

        full_response = ""

        try:

            if model_choice == "Gemini":

                full_response = call_gemini(
                    final_prompt,
                    image_to_send
                )

            else:

                if image_to_send:

                    full_response = (
                        "⚠️ Llama3 ছবি বুঝতে পারে না। Gemini ব্যবহার করো।"
                    )

                else:

                    client = Groq(
                        api_key=GROQ_API_KEY
                    )

                    completion = client.chat.completions.create(

                        model="llama-3.3-70b-versatile",

                        messages=[

                            {
                                "role":"system",
                                "content":
                                f"You are HSC {subject} teacher."
                            },

                            {
                                "role":"user",
                                "content":final_prompt
                            }
                        ]
                    )

                    full_response = (
                        completion
                        .choices[0]
                        .message
                        .content
                    )

        except Exception as e:

            full_response = str(e)

        typed = ""

        for char in full_response:

            typed += char

            placeholder.markdown(typed)

            time.sleep(0.002)

        st.session_state.messages.append({

            "role":"assistant",
            "content":full_response

        })

        save_message(
            "assistant",
            full_response
        )