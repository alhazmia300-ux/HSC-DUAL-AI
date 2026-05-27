import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper
from streamlit_cookies_manager import EncryptedCookieManager

import json
import time
import PyPDF2

from utils.auth import *
from utils.database import *
from utils.ai_models import *
from utils.profile import *
from utils.ui import *

# ======================================================
# PAGE CONFIG
# ======================================================
st.set_page_config(
    page_title="🎓 HSC Dual AI Tutor",
    page_icon="🎓",
    layout="wide"
)

# ======================================================
# CSS
# ======================================================
load_css()

# ======================================================
# API KEYS & FIREBASE INIT
# ======================================================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
FIREBASE_API_KEY = st.secrets["FIREBASE_API_KEY"]

firebase_json = st.secrets["FIREBASE_CREDENTIALS"]
db = init_firestore(firebase_json)

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
# SESSION STATE
# ======================================================
defaults = {
    "logged_in": False,
    "user_email": "",
    "user_name": "",
    "messages": [],
    "current_chat_id": None,
    "profile_pic": None,
    "change_pfp": False
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ======================================================
# AUTO LOGIN
# ======================================================
if cookies.get("logged_in") == "true":
    st.session_state.logged_in = True
    st.session_state.user_email = cookies.get("user_email")
    st.session_state.user_name = cookies.get("user_name")
    st.session_state.profile_pic = cookies.get("profile_pic")

# ======================================================
# LOGIN / SIGNUP PAGE
# ======================================================
if not st.session_state.logged_in:
    st.title("Welcome my friend")
    st.caption("This platform is created by ALhaz")

    option = st.selectbox(
        "Choose Option",
        ["Login", "Sign Up"]
    )

    with st.form("auth"):
        name = st.text_input("Enter your name")
        email = st.text_input("Enter email/phone number")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Continue")

    if submit:
        if not name.strip():
            st.error("Name required")
            st.stop()

        if option == "Sign Up":
            result = signup(email, password, FIREBASE_API_KEY)
            if "email" in result:
                st.success("Account Created")
            else:
                st.error(result.get("error", {}).get("message"))
        else:
            result = login(email, password, FIREBASE_API_KEY)
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
                st.error(result.get("error", {}).get("message"))
    st.stop()

# ======================================================
# USER ID GENERATION (ফিক্সড কমেন্ট ও সিনট্যাক্স)
# ======================================================
USER_ID = get_user_id(st.session_state.user_email)

# ======================================================
# HEADER
# ======================================================
st.title("🎓 HSC Dual AI Tutor")
st.subheader("Llama3 এবং Gemini-র সমন্বয়ে HSC প্রস্তুতি")
st.caption("🚀 Created by ALhaz")

# ======================================================
# SIDEBAR
# ======================================================
with st.sidebar:
    st.markdown("## ⚙️ Settings")

    # ==================================================
    # PROFILE SECTION
    # ==================================================
    st.markdown('<div class="profile-center">', unsafe_allow_html=True)
    if st.session_state.profile_pic:
        st.markdown(
            f'<div class="profile-circle"><img src="data:image/png;base64,{st.session_state.profile_pic}"></div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="profile-circle"><img src="https://cdn-icons-png.flaticon.com/512/149/149071.png"></div>',
            unsafe_allow_html=True
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Change Profile Picture", use_container_width=True):
        st.session_state.change_pfp = True

    # ==================================================
    # PROFILE UPLOAD + CROPPER
    # ==================================================
    if st.session_state.change_pfp:
        uploaded_pfp = st.file_uploader("Upload Profile Picture", type=["jpg", "jpeg", "png"], key="pfp")
        if uploaded_pfp:
            image = Image.open(uploaded_pfp)
            cropped = st_cropper(image, realtime_update=True, box_color="#7C4DFF", aspect_ratio=(1,1))
            
            if st.button("Save Profile Picture", use_container_width=True):
                final_img = make_circle_image(cropped)
                base64_img = image_to_base64(final_img)
                st.session_state.profile_pic = base64_img
                cookies["profile_pic"] = base64_img
                cookies.save()
                st.session_state.change_pfp = False
                st.rerun()

    st.markdown(f"### {st.session_state.user_name}")
    st.caption(st.session_state.user_email)
    st.markdown("---")

    # ==================================================
    # MODEL + SUBJECT SELECTBOXES
    # ==================================================
    col1, col2 = st.columns(2)
    with col1:
        model_choice = st.selectbox("AI Model", ["Gemini", "Llama3"])
    with col2:
        subject = st.selectbox("Subject", [
            "Physics", "Chemistry", "Biology", "Higher Math", 
            "Bangla", "English", "ICT", "Economics", "Accounting", "History"
        ])

    st.markdown("---")

    # ==================================================
    # NEW CHAT BUTTON
    # ==================================================
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.current_chat_id = None
        st.session_state.messages = []
        st.rerun()

    # ==================================================
    # SEARCH HISTORY & CHAT HISTORY (ক্লিন ড্রপডাউন মেনু)
    # ==================================================
    st.markdown("### 💬 Chats History")
    search_chat = st.text_input("🔍 Search History", label_visibility="collapsed", placeholder="Search history...")

    try:
        chat_list = get_chat_list(db, USER_ID)
    except:
        chat_list = []

    # সার্চ ফিল্টারিং অনুযায়ী চ্যাট লিস্ট রেডি করা
    filtered_chats = []
    if chat_list:
        for chat in chat_list:
            if search_chat.lower() in chat["title"].lower():
                filtered_chats.append(chat)

    if filtered_chats:
        chat_options = {chat["title"]: chat["chat_id"] for chat in filtered_chats}
        
        # বর্তমান চ্যাট ইনডেক্স নির্ধারণ
        default_index = 0
        current_id = st.session_state.get("current_chat_id")
        if current_id:
            for i, chat in enumerate(filtered_chats):
                if chat.get("chat_id") == current_id:
                    default_index = i
                    break

        # ক্লিন সিলেক্টবক্স এবং পাশে ডিলিট লেআউট
        c1, c2 = st.columns([4, 1])
        with c1:
            selected_chat_title = st.selectbox(
                "Select Chat",
                options=list(chat_options.keys()),
                index=default_index,
                label_visibility="collapsed",
                key="chat_selector_dropdown"
            )
        
        selected_chat_id = chat_options.get(selected_chat_title)
        
        # ইউজারের সিলেকশন পরিবর্তন হলে চ্যাট লোড করা
        if selected_chat_id and selected_chat_id != st.session_state.get("current_chat_id"):
            st.session_state.current_chat_id = selected_chat_id
            st.session_state.messages = load_messages(db, USER_ID, selected_chat_id)
            st.rerun()

        with c2:
            if st.button("🗑️", key="delete_current_chat_btn", use_container_width=True):
                if selected_chat_id:
                    delete_chat(db, USER_ID, selected_chat_id)
                    if st.session_state.current_chat_id == selected_chat_id:
                        st.session_state.current_chat_id = None
                        st.session_state.messages = []
                    st.rerun()
    else:
        st.sidebar.caption("No past chats found.")

    st.markdown("---")
    
    # ==================================================
    # LOGOUT BUTTON
    # ==================================================
    if st.button("🚪 Logout", use_container_width=True):
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
        st.rerun()

# ======================================================
# SHOW CHAT MESSAGES
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
# MAIN CHAT SYSTEM (লজিক ও প্রম্পট প্রসেসিং)
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
        if file_name.endswith((".jpg", ".jpeg", ".png")):
            image_to_send = Image.open(uploaded_file)

        # PDF
        elif file_name.endswith(".pdf"):
            try:
                reader = PyPDF2.PdfReader(uploaded_file)
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt:
                        pdf_text += txt
            except Exception as e:
                st.error(f"PDF Error: {e}")

    # ==================================================
    # CREATE CHAT SESSIONS
    # ==================================================
    if not st.session_state.current_chat_id:
        st.session_state.current_chat_id = create_chat(db, USER_ID)

    # ==================================================
    # SYSTEM PROMPT BUILDER
    # ==================================================
    final_prompt = f"তুমি একজন {subject} বিষয়ের HSC শিক্ষক।\nসহজ বাংলায় উত্তর দাও।\n\nপ্রশ্ন:\n{user_text}\n"

    if pdf_text:
        final_prompt += f"\nPDF Content:\n{pdf_text[:12000]}\n"

    # DISPLAY USER MESSAGE
    display_text = user_text if user_text else "[📎 File Uploaded]"
    
    with st.chat_message("user"):
        if image_to_send:
            st.image(image_to_send, width=250)
        st.markdown(display_text)

    # SAVE USER MESSAGE TO STATE & DATABASE
    st.session_state.messages.append({"role": "user", "content": display_text})
    save_message(db, USER_ID, st.session_state.current_chat_id, "user", display_text)

    # AUTO CHAT TITLE UPDATE
    if len(st.session_state.messages) <= 2:  # প্রথম প্রশ্নের পরেই টাইটেল হবে
        update_chat_title(db, USER_ID, st.session_state.current_chat_id, display_text)

    # ==================================================
    # AI RESPONSE GENERATION
    # ==================================================
    with st.chat_message("assistant"):
        placeholder = st.empty()

        if model_choice == "Gemini":
            full_response = smart_ai_response(
                GEMINI_API_KEY, GROQ_API_KEY, final_prompt, subject, image_to_send
            )
        else:
            if image_to_send:
                full_response = "⚠️ Llama3 ছবি বুঝতে পারে না।\nছবি/PDF এর জন্য Gemini ব্যবহার করো।"
            else:
                full_response = call_llama(GROQ_API_KEY, final_prompt, subject)

        # STREAMING EFFECT & SAVE RESPONSE
        typing_effect(placeholder, full_response, speed=0.002)
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        save_message(db, USER_ID, st.session_state.current_chat_id, "assistant", full_response)
