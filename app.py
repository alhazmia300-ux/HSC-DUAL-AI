# =========================================================
# IMPORTS
# =========================================================

import streamlit as st
from groq import Groq
from google import genai
from PIL import Image, ImageDraw
from streamlit_cropper import st_cropper

import firebase_admin
from firebase_admin import credentials, firestore

from streamlit_cookies_manager import EncryptedCookieManager

import requests
import PyPDF2
import hashlib
import json
import uuid
import io
import base64
import time

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="🎓 HSC Dual AI Tutor",
    page_icon="🎓",
    layout="wide"
)

# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown("""
<style>

.block-container{
    padding-top:1rem;
}

section[data-testid="stSidebar"]{
    width:320px !important;
    border-right:1px solid rgba(255,255,255,0.08);
}

.stChatMessage{
    border-radius:18px;
}

.stButton > button{
    border-radius:14px;
}

.profile-wrap{
    display:flex;
    justify-content:center;
    margin-top:-10px;
    margin-bottom:8px;
}

.profile-circle{
    width:115px;
    height:115px;
    border-radius:50%;
    overflow:hidden;
    border:4px solid #7C4DFF;
    box-shadow:0 0 25px rgba(124,77,255,0.75);
}

.profile-circle img{
    width:100%;
    height:100%;
    object-fit:cover;
}

.profile-empty{
    width:115px;
    height:115px;
    border-radius:50%;
    border:4px solid #7C4DFF;
    display:flex;
    align-items:center;
    justify-content:center;
    background:#161616;
    color:white;
    font-size:45px;
    box-shadow:0 0 25px rgba(124,77,255,0.75);
}

.small-gap{
    margin-top:-10px;
    margin-bottom:-10px;
}

.top-btn button{
    height:42px;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# SECRETS
# =========================================================

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
FIREBASE_API_KEY = st.secrets.get("FIREBASE_API_KEY")

# =========================================================
# COOKIES
# =========================================================

cookies = EncryptedCookieManager(
    prefix="hsc_ai_",
    password="ALhaz_secure_key"
)

if not cookies.ready():
    st.stop()

# =========================================================
# FIREBASE INIT
# =========================================================

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

# =========================================================
# SESSION STATE
# =========================================================

defaults = {

    "logged_in": False,
    "user_email": "",
    "user_name": "",
    "messages": [],
    "current_chat_id": None,
    "change_pfp": False
}

for key, value in defaults.items():

    if key not in st.session_state:

        st.session_state[key] = value

# =========================================================
# AUTO LOGIN
# =========================================================

if cookies.get("logged_in") == "true":

    st.session_state.logged_in = True
    st.session_state.user_email = cookies.get("user_email")
    st.session_state.user_name = cookies.get("user_name")

# =========================================================
# USER ID
# =========================================================

def get_user_id():

    return hashlib.md5(
        st.session_state.user_email.encode()
    ).hexdigest()

# =========================================================
# FIREBASE AUTH
# =========================================================

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

# =========================================================
# LOGOUT
# =========================================================

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

# =========================================================
# PROFILE PICTURE SAVE
# =========================================================

def save_profile_picture(image):

    buffered = io.BytesIO()

    image.save(buffered, format="PNG")

    img_str = base64.b64encode(
        buffered.getvalue()
    ).decode()

    db.collection("users_profile") \
        .document(get_user_id()) \
        .set({

            "profile_picture": img_str

        }, merge=True)

# =========================================================
# LOAD PROFILE PIC
# =========================================================

def load_profile_picture():

    try:

        doc = db.collection("users_profile") \
            .document(get_user_id()) \
            .get()

        if doc.exists:

            return doc.to_dict().get(
                "profile_picture"
            )

    except:
        pass

    return None

# =========================================================
# CIRCLE IMAGE
# =========================================================

def make_circle_image(img):

    img = img.convert("RGBA")

    size = min(img.size)

    img = img.resize((size, size))

    mask = Image.new("L", (size, size), 0)

    draw = ImageDraw.Draw(mask)

    draw.ellipse(
        (0, 0, size, size),
        fill=255
    )

    output = Image.new(
        "RGBA",
        (size, size)
    )

    output.paste(
        img,
        (0, 0),
        mask
    )

    return output

# =========================================================
# CHAT DATABASE
# =========================================================

def create_new_chat():

    chat_id = str(uuid.uuid4())

    st.session_state.current_chat_id = chat_id

    st.session_state.messages = []

def save_message(role, content):

    if not content.strip():
        return

    if not st.session_state.current_chat_id:
        create_new_chat()

    chat_ref = db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .document(st.session_state.current_chat_id)

    if role == "user" and len(st.session_state.messages) <= 1:

        chat_ref.set({

            "title": content[:40],
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

    temp.sort(
        key=lambda x: x["created_at"]
    )

    return [

        {
            "role": x["role"],
            "content": x["content"]
        }

        for x in temp
    ]

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

# =========================================================
# LOGIN PAGE
# =========================================================

if not st.session_state.logged_in:

    st.markdown("<br><br>", unsafe_allow_html=True)

    st.markdown(
        "<h1 style='text-align:center;'>Welcome my friend</h1>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<p style='text-align:center;'>This platform is created by ALhaz</p>",
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    option = st.selectbox(
        "Choose Option",
        ["Login", "Sign Up"]
    )

    with st.form("auth"):

        name = st.text_input(
            "Enter your name"
        )

        email = st.text_input(
            "Enter email/phone number"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        submit = st.form_submit_button(
            "Continue"
        )

    if submit:

        if not name.strip():

            st.error("Name required")
            st.stop()

        if option == "Sign Up":

            result = signup(email, password)

            if "email" in result:

                st.success("Account created")

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

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## ⚙️ Settings")

    profile_picture = load_profile_picture()

    if profile_picture:

        st.markdown(
            f"""
            <div class="profile-wrap">
                <div class="profile-circle">
                    <img src="data:image/png;base64,{profile_picture}">
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    else:

        st.markdown("""
        <div class="profile-wrap">
            <div class="profile-empty">
                +
            </div>
        </div>
        """, unsafe_allow_html=True)

    if st.button(
        "📸 Change Profile Picture",
        use_container_width=True
    ):

        st.session_state.change_pfp = True

    st.markdown(
        "<div class='small-gap'></div>",
        unsafe_allow_html=True
    )

    st.write(f"👤 {st.session_state.user_name}")

    st.caption(
        st.session_state.user_email
    )

    if st.session_state.change_pfp:

        uploaded = st.file_uploader(
            "Upload",
            type=["png", "jpg", "jpeg"]
        )

        if uploaded:

            image = Image.open(uploaded)

            cropped = st_cropper(
                image,
                realtime_update=True,
                aspect_ratio=(1,1),
                box_color="#7C4DFF"
            )

            preview = make_circle_image(
                cropped
            )

            st.image(
                preview,
                width=140
            )

            c1, c2 = st.columns(2)

            with c1:

                if st.button("Save"):

                    save_profile_picture(
                        preview
                    )

                    st.session_state.change_pfp = False

                    st.rerun()

            with c2:

                if st.button("Cancel"):

                    st.session_state.change_pfp = False

                    st.rerun()

    st.markdown("---")

    model_choice = st.selectbox(
        "🤖 AI Model",
        ["Gemini", "Llama3"]
    )

    subject = st.selectbox(
        "📚 Subject",
        [
            "Physics",
            "Chemistry",
            "Biology",
            "Higher Math",
            "Bangla",
            "English",
            "ICT"
        ]
    )

    st.markdown("---")

    if st.button(
        "➕ New Chat",
        use_container_width=True
    ):

        create_new_chat()

        st.rerun()

    st.markdown("### 💬 Chat History")

    chat_list = get_chat_list()

    for chat in chat_list:

        if st.button(
            chat["title"],
            key=chat["chat_id"]
        ):

            st.session_state.current_chat_id = chat["chat_id"]

            st.session_state.messages = load_messages(
                chat["chat_id"]
            )

            st.rerun()

    st.markdown("---")

    if st.button(
        "🚪 Logout",
        use_container_width=True
    ):

        logout()

        st.rerun()

# =========================================================
# TOP RIGHT NEW CHAT
# =========================================================

top1, top2 = st.columns([9,1])

with top2:

    if st.button(
        "➕",
        use_container_width=True
    ):

        create_new_chat()

        st.rerun()

# =========================================================
# MAIN HEADER
# =========================================================

st.title("🎓 HSC Dual AI Tutor")

st.subheader(
    "Llama3 এবং Gemini-র সমন্বয়ে HSC প্রস্তুতি"
)

st.write(
    "তোমার HSC পরীক্ষার যেকোনো বিষয়ের প্রশ্ন এখানে জিজ্ঞেস করো!"
)

st.caption("🚀 Created by ALhaz")

# =========================================================
# SHOW CHAT
# =========================================================

for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):

        st.markdown(msg["content"])

# =========================================================
# GEMINI FUNCTION
# =========================================================

def call_gemini(prompt_text, image_obj=None):

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

# =========================================================
# CHAT INPUT
# =========================================================

prompt = st.chat_input(
    "প্রশ্ন লেখো অথবা ছবি/PDF আপলোড করো...",
    accept_file=True,
    file_type=["jpg","jpeg","png","pdf"]
)

# =========================================================
# MAIN CHAT SYSTEM
# =========================================================

if prompt:

    user_text = prompt.text if prompt.text else ""

    uploaded_files = prompt.files

    image_to_send = None

    pdf_text = ""

    if uploaded_files:

        file = uploaded_files[0]

        if file.name.lower().endswith(
            (".jpg",".jpeg",".png")
        ):

            image_to_send = Image.open(file)

        elif file.name.lower().endswith(".pdf"):

            reader = PyPDF2.PdfReader(file)

            for page in reader.pages:

                txt = page.extract_text()

                if txt:
                    pdf_text += txt

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

    with st.chat_message("user"):

        if image_to_send:

            st.image(
                image_to_send,
                width=250
            )

        st.markdown(
            user_text
            if user_text
            else "[📎 File]"
        )

    display_text = user_text if user_text else "[📎 File]"

    st.session_state.messages.append({

        "role": "user",
        "content": display_text

    })

    save_message(
        "user",
        display_text
    )

    with st.chat_message("assistant"):

        placeholder = st.empty()

        try:

            if model_choice == "Gemini":

                full_response = call_gemini(
                    final_prompt,
                    image_to_send
                )

            else:

                if image_to_send:

                    full_response = (
                        "⚠️ Llama3 image support করে না।"
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
                                "You are an HSC teacher answering in Bengali."
                            },

                            {
                                "role":"user",
                                "content":final_prompt
                            }

                        ]
                    )

                    full_response = completion \
                        .choices[0] \
                        .message.content

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