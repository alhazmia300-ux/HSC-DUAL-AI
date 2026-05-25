import streamlit as st
from groq import Groq
from PIL import Image
from google import genai
import requests
import hashlib
import time
import PyPDF2

# =========================================
# PAGE CONFIG
# =========================================

st.set_page_config(
    page_title="🎓 HSC Dual AI Tutor",
    page_icon="🎓",
    layout="centered"
)

# =========================================
# CLEAN UI STYLE
# =========================================

st.markdown("""
<style>

/* Chat Message */
[data-testid="stChatMessage"] {
    border-radius: 18px;
    padding: 14px;
    margin-bottom: 12px;
}

/* Buttons */
.stButton > button {
    border-radius: 12px;
}

/* Chat Input */
.stChatInputContainer {
    border-top: 1px solid rgba(128,128,128,0.2);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128,128,128,0.1);
}

</style>
""", unsafe_allow_html=True)

# =========================================
# HEADER
# =========================================

st.title("🎓 HSC Dual AI Tutor")

st.subheader("Gemini + Llama3 দিয়ে HSC প্রস্তুতি")

st.write("যেকোনো HSC বিষয়ের প্রশ্ন করো, ছবি বা PDF আপলোড করো।")

st.caption("🚀 Created by ALhaz")

# =========================================
# LOAD API KEYS
# =========================================

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")

# =========================================
# SIDEBAR
# =========================================

st.sidebar.title("⚙️ Settings")

model_choice = st.sidebar.radio(
    "🤖 AI Model নির্বাচন করো",
    [
        "Gemini (Multimodal)",
        "Llama3 (Groq - Text Only)"
    ]
)

subject = st.sidebar.selectbox(
    "📚 বিষয় নির্বাচন করো",
    [

        # SCIENCE
        "Physics 1st Paper",
        "Physics 2nd Paper",
        "Chemistry 1st Paper",
        "Chemistry 2nd Paper",
        "Biology 1st Paper",
        "Biology 2nd Paper",
        "Higher Math 1st Paper",
        "Higher Math 2nd Paper",

        # BUSINESS STUDIES
        "Accounting 1st Paper",
        "Accounting 2nd Paper",
        "Finance & Banking 1st Paper",
        "Finance & Banking 2nd Paper",
        "Business Organization & Management 1st Paper",
        "Business Organization & Management 2nd Paper",

        # HUMANITIES
        "History 1st Paper",
        "History 2nd Paper",
        "Civics",
        "Economics 1st Paper",
        "Economics 2nd Paper",
        "Sociology 1st Paper",
        "Sociology 2nd Paper",
        "Islamic History & Culture",
        "Logic",
        "Social Work",
        "Geography",

        # COMPULSORY
        "Bangla 1st Paper",
        "Bangla 2nd Paper",
        "English 1st Paper",
        "English 2nd Paper",
        "ICT",

        # OPTIONAL
        "Agriculture",
        "Statistics",
        "Psychology",
        "Home Science",
        "Islamic Studies"
    ]
)

# =========================================
# USER ID
# =========================================

def get_unique_user_id():

    try:

        raw_data = str(st.session_state)

        user_hash = hashlib.md5(raw_data.encode()).hexdigest()[:6]

        return f"User_{user_hash}"

    except:

        return "User_Unknown"

# =========================================
# TELEGRAM NOTIFICATION
# =========================================

def send_telegram(user_id, q_text, model_name, has_file=False):

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    file_status = "📎 File" if has_file else "📝 Text"

    msg = f"""
🔔 নতুন প্রশ্ন!

👤 User: {user_id}
🤖 Model: {model_name}
📂 Type: {file_status}

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
# GEMINI FUNCTION
# =========================================

def call_gemini(api_key, text_prompt, image_pil=None):

    try:

        client = genai.Client(api_key=api_key)

        # IMAGE + TEXT
        if image_pil:

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    text_prompt if text_prompt else "এই ছবিটি ব্যাখ্যা করো",
                    image_pil
                ]
            )

        # TEXT ONLY
        else:

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=text_prompt if text_prompt else "Hi"
            )

        return response.text

    except Exception as e:

        error_text = str(e)

        # FALLBACK TO GROQ
        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:

            try:

                client = Groq(api_key=GROQ_API_KEY)

                completion = client.chat.completions.create(

                    model="llama-3.3-70b-versatile",

                    messages=[
                        {
                            "role": "user",
                            "content": text_prompt if text_prompt else "Hi"
                        }
                    ]
                )

                return (
                    "⚠️ Gemini quota শেষ হয়েছে।\n\n"
                    "নিচে Llama3 এর উত্তর দেওয়া হলো:\n\n"
                    + completion.choices[0].message.content
                )

            except Exception as groq_error:

                return f"❌ Gemini quota শেষ এবং Groq fallback failed:\n{str(groq_error)}"

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
# CHAT HISTORY
# =========================================

if "messages" not in st.session_state:

    st.session_state.messages = []

# =========================================
# SHOW CHAT HISTORY
# =========================================

for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):

        st.markdown(msg["content"])

st.markdown("---")

# =========================================
# CHAT INPUT
# =========================================

prompt = st.chat_input(
    "প্রশ্ন লেখো অথবা PDF / ছবি আপলোড করো...",
    accept_file=True,
    file_type=["jpg", "jpeg", "png", "pdf"]
)

# =========================================
# MAIN CHAT SYSTEM
# =========================================

if prompt:

    user_text = prompt.text

    uploaded_files = prompt.files

    current_user_id = get_unique_user_id()

    image_to_send = None

    has_file_flag = False

    pdf_text = ""

    # =========================================
    # SUBJECT TUTOR MODE
    # =========================================

    user_text = f"""
তুমি একজন {subject} বিষয়ের HSC শিক্ষক।

সহজ ভাষায় উত্তর দাও।

প্রশ্ন:
{user_text}
"""

    # =========================================
    # FILE HANDLE
    # =========================================

    if uploaded_files and len(uploaded_files) > 0:

        uploaded_file = uploaded_files[0]

        file_name = uploaded_file.name.lower()

        has_file_flag = True

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

            st.success("✅ PDF সফলভাবে আপলোড হয়েছে")

    # =========================================
    # PDF CONTENT ADD
    # =========================================

    if pdf_text:

        user_text += f"\n\nPDF Content:\n{pdf_text[:4000]}"

    # =========================================
    # SHOW USER MESSAGE
    # =========================================

    with st.chat_message("user"):

        if image_to_send:

            st.image(
                image_to_send,
                caption="আপলোড করা ছবি",
                width=250
            )

        if pdf_text:

            st.info("📄 PDF আপলোড করা হয়েছে")

        st.markdown(
            prompt.text if prompt.text
            else "[ফাইল পাঠানো হয়েছে]"
        )

    # =========================================
    # SAVE USER MESSAGE
    # =========================================

    st.session_state.messages.append({
        "role": "user",
        "content": user_text
    })

    # =========================================
    # SEND TELEGRAM
    # =========================================

    send_telegram(
        current_user_id,
        user_text,
        model_choice,
        has_file=has_file_flag
    )

    # =========================================
    # ASSISTANT RESPONSE
    # =========================================

    with st.chat_message("assistant"):

        response_placeholder = st.empty()

        full_response = ""

        try:

            # GEMINI
            if model_choice == "Gemini (Multimodal)":

                if not GEMINI_API_KEY:

                    full_response = "⚠️ Gemini API Key সেট করা নেই"

                else:

                    full_response = call_gemini(
                        GEMINI_API_KEY,
                        user_text,
                        image_to_send
                    )

            # LLAMA3
            elif model_choice == "Llama3 (Groq - Text Only)":

                if image_to_send:

                    full_response = (
                        "⚠️ Llama3 ছবি বুঝতে পারে না। "
                        "ছবির জন্য Gemini ব্যবহার করো।"
                    )

                elif not GROQ_API_KEY:

                    full_response = "⚠️ Groq API Key সেট করা নেই"

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

            full_response = f"❌ Internal Error:\n{str(e)}"

        # =========================================
        # STREAMING EFFECT
        # =========================================

        typed_text = ""

        for char in full_response:

            typed_text += char

            response_placeholder.markdown(typed_text)

            time.sleep(0.01)

        # =========================================
        # SAVE RESPONSE
        # =========================================

        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response
        })