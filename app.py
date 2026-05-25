import streamlit as st
from groq import Groq
from PIL import Image
from google import genai
import requests
import hashlib
import time
import PyPDF2
import firebase_admin
import json

from firebase_admin import credentials
from firebase_admin import firestore

# =========================================
# PAGE CONFIG & STYLE
# =========================================
st.set_page_config(
    page_title="🎓 HSC Dual AI Tutor",
    page_icon="🎓",
    layout="centered"
)

st.markdown("""
<style>
[data-testid="stChatMessage"] { border-radius: 18px; padding: 14px; margin-bottom: 12px; }
.stButton > button { border-radius: 12px; }
.stChatInputContainer { border-top: 1px solid rgba(128,128,128,0.2); }
section[data-testid="stSidebar"] { border-right: 1px solid rgba(128,128,128,0.1); }
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
# LOAD SECRETS
# =========================================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")

# =========================================
# FIREBASE INIT (Safe Wrapper)
# =========================================
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

# =========================================
# USER ID
# =========================================
def get_unique_user_id():
    try:
        raw_data = str(st.context.headers)
        user_hash = hashlib.md5(raw_data.encode()).hexdigest()[:10]
        return f"user_{user_hash}"
    except:
        return "user_unknown"

USER_ID = get_unique_user_id()

# =========================================
# FIREBASE CORE FUNCTIONS
# =========================================
def save_message(role, content):
    if db:
        try:
            db.collection("chat_history").add({
                "user_id": USER_ID,
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
        chats = db.collection("chat_history") \
            .where("user_id", "==", USER_ID) \
            .order_by("timestamp", direction=firestore.Query.ASCENDING) \
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
        # যদি নো-ইন্ডেক্স এরর আসে, ক্র্যাশ না করে নরমাল স্ট্রিম করবে
        try:
            chats = db.collection("chat_history").where("user_id", "==", USER_ID).stream()
            return [{"role": c.to_dict()["role"], "content": c.to_dict()["content"]} for c in chats]
        except:
            return []

def clear_chat_history():
    if db:
        try:
            chats = db.collection("chat_history").where("user_id", "==", USER_ID).stream()
            for chat in chats:
                chat.reference.delete()
        except:
            pass

# =========================================
# SIDEBAR SETTINGS
# =========================================
st.sidebar.title("⚙️ Settings")
model_choice = st.sidebar.radio("🤖 AI Model নির্বাচন করো", ["Gemini (Multimodal)", "Llama3 (Groq - Text Only)"])
subject = st.sidebar.selectbox("📚 বিষয় নির্বাচন করো", [
    "Physics 1st Paper", "Physics 2nd Paper", "Chemistry 1st Paper", "Chemistry 2nd Paper",
    "Biology 1st Paper", "Biology 2nd Paper", "Higher Math 1st Paper", "Higher Math 2nd Paper",
    "Accounting 1st Paper", "Accounting 2nd Paper", "Finance & Banking 1st Paper", "Finance & Banking 2nd Paper",
    "History 1st Paper", "History 2nd Paper", "Civics", "Economics 1st Paper", "Economics 2nd Paper",
    "Bangla 1st Paper", "Bangla 2nd Paper", "English 1st Paper", "English 2nd Paper", "ICT"
])

if st.sidebar.button("🗑️ Clear Chat", use_container_width=True):
    clear_chat_history()
    st.session_state.messages = []
    st.rerun()

# =========================================
# TELEGRAM NOTIFICATION
# =========================================
def send_telegram(user_id, q_text, model_name, has_file=False):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    file_status = "📎 File" if has_file else "📝 Text"
    msg = f"🔔 নতুন প্রশ্ন!\n\n👤 User: {user_id}\n🤖 Model: {model_name}\n📂 Type: {file_status}\n\n❓ Question:\n{q_text[:300]}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=5)
    except:
        pass

# =========================================
# GEMINI COGNITION FUNCTION
# =========================================
def call_gemini(api_key, text_prompt, image_pil=None):
    try:
        # সঠিক লাইব্রেরি কনফিগারেশন মেথড
        client = genai.Client(http_options={'api_key': api_key})
        
        if image_pil:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[text_prompt, image_pil]
            )
        else:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=text_prompt
            )
        return response.text
    except Exception as e:
        error_text = str(e)
        if "429" in error_text and GROQ_API_KEY:
            try:
                groq_client = Groq(api_key=GROQ_API_KEY)
                completion = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": text_prompt}]
                )
                return "⚠️ Gemini quota শেষ হয়েছে (Llama3 Fallback):\n\n" + completion.choices[0].message.content
            except Exception as groq_error:
                return f"❌ Fallback failed:\n{str(groq_error)}"
        return f"❌ Gemini Error:\n{error_text}"

# =========================================
# MCQ GENERATOR
# =========================================
if st.sidebar.button("📝 Generate MCQ", use_container_width=True):
    mcq_prompt = f"তুমি একজন বিশেষজ্ঞ শিক্ষক। {subject} বিষয়ের HSC স্তরের ১০টি গুরুত্বপূর্ণ MCQ প্রশ্ন তৈরি করো এবং নিচে তার সঠিক উত্তর ব্যাখ্যাসহ দাও।"
    with st.spinner("MCQ তৈরি হচ্ছে..."):
        mcq_response = call_gemini(GEMINI_API_KEY, mcq_prompt)
    st.markdown("---")
    st.markdown(mcq_response)

# =========================================
# LOAD & SHOW CHAT HISTORY
# =========================================
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

st.markdown("---")

# =========================================
# CHAT INPUT & SYSTEM CORE
# =========================================
prompt = st.chat_input("প্রশ্ন লেখো অথবা PDF / ছবি আপলোড করো...", accept_file=True, file_type=["jpg", "jpeg", "png", "pdf"])

if prompt:
    raw_user_text = prompt.text if prompt.text else ""
    uploaded_files = prompt.files
    image_to_send = None
    has_file_flag = False
    pdf_text = ""

    # ফাইল প্রসেসিং লজিক
    if uploaded_files and len(uploaded_files) > 0:
        uploaded_file = uploaded_files[0]
        file_name = uploaded_file.name.lower()
        has_file_flag = True

        if file_name.endswith((".jpg", ".jpeg", ".png")):
            image_to_send = Image.open(uploaded_file)
        elif file_name.endswith(".pdf"):
            try:
                reader = PyPDF2.PdfReader(uploaded_file)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        pdf_text += extracted
            except Exception as e:
                st.error(f"PDF Read Error: {e}")

    # UI-তে মেসেজ রেন্ডার করা (ক্লিন লুকের জন্য)
    with st.chat_message("user"):
        if image_to_send:
            st.image(image_to_send, caption="আপলোড করা ছবি", width=250)
        if pdf_text:
            st.info("📄 PDF সফলভাবে আপলোড হয়েছে")
        st.markdown(raw_user_text if raw_user_text else "[ফাইল পাঠানো হয়েছে]")

    # ফাইনাল এআই প্রম্পট ইঞ্জিনিয়ারিং
    ai_prompt = f"তুমি একজন {subject} বিষয়ের HSC স্তরের অভিজ্ঞ শিক্ষক। সহজ সাবলীল বাংলায় বুঝিয়ে বলো।\n\nপ্রশ্ন: {raw_user_text}"
    if pdf_text:
        ai_prompt += f"\n\n[সংযুক্ত PDF-এর তথ্য]:\n{pdf_text[:3000]}"

    # ডাটাবেজে শুধুমাত্র ইউজারের অরিজিনাল মেসেজ সেভ হবে (সিস্টেম প্রম্পট বাদে)
    display_text = raw_user_text if raw_user_text else "[📎 ফাইল সংযুক্তি]"
    st.session_state.messages.append({"role": "user", "content": display_text})
    save_message("user", display_text)

    # ব্যাকগ্রাউন্ড টেলিগ্রাম নোটিফিকেশন
    send_telegram(USER_ID, display_text, model_choice, has_file=has_file_flag)

    # রেসপন্স জেনারেশন
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""

        try:
            if model_choice == "Gemini (Multimodal)":
                if not GEMINI_API_KEY:
                    full_response = "⚠️ Gemini API Key সেট করা নেই"
                else:
                    full_response = call_gemini(GEMINI_API_KEY, ai_prompt, image_to_send)

            elif model_choice == "Llama3 (Groq - Text Only)":
                if image_to_send:
                    full_response = "⚠️ Llama3 ছবি বুঝতে পারে না। ছবির প্রশ্নের জন্য সাইডবার থেকে Gemini সিলেক্ট করো।"
                elif not GROQ_API_KEY:
                    full_response = "⚠️ Groq API Key সেট করা নেই"
                else:
                    client = Groq(api_key=GROQ_API_KEY)
                    
                    # Groq ফরম্যাট কম্প্যাটিবিলিটি ফিল্টার
                    groq_messages = [{"role": "system", "content": f"You are an expert HSC teacher teaching {subject} in Bengali."}]
                    for m in st.session_state.messages[:-1]:
                        groq_messages.append({"role": m["role"], "content": m["content"]})
                    groq_messages.append({"role": "user", "content": ai_prompt})

                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=groq_messages
                    )
                    full_response = completion.choices[0].message.content

        except Exception as e:
            full_response = f"❌ Internal Error:\n{str(e)}"

        # টাইপিং স্ট্রিমিং ইফেক্ট
        typed_text = ""
        for char in full_response:
            typed_text += char
            response_placeholder.markdown(typed_text)
            time.sleep(0.005) # টাইপিং স্পিড আরেকটু স্মুথ করা হলো

        # ফাইনাল রেসপন্স হিস্ট্রি ও ক্লাউডে সেভ
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        save_message("assistant", full_response)
