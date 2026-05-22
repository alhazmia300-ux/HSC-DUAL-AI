import streamlit as st
from groq import Groq
from PIL import Image
import requests
import hashlib
import io
import base64

# =========================
# PAGE SETUP
# =========================

st.set_page_config(
    page_title="HSC Dual AI Tutor",
    page_icon="🎓",
    layout="centered"
)

st.title("🎓 HSC Dual AI Tutor")
st.subheader("Llama3 এবং Gemini-র সমন্বয়ে HSC প্রস্তুতি")
st.write("তোমার HSC পরীক্ষার যেকোনো বিষয়ের প্রশ্ন এখানে জিজ্ঞেস করো!")
st.caption("🚀 Created by ALhaz")

# =========================
# LOAD SECRETS
# =========================

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")

# =========================
# UNIQUE USER ID
# =========================

def get_unique_user_id():
    try:
        session_data = str(st.session_state)
        user_hash = hashlib.md5(session_data.encode()).hexdigest()[:6]
        return f"User_{user_hash}"
    except:
        return "User_Unknown"

# =========================
# TELEGRAM NOTIFICATION
# =========================

def send_telegram(user_id, q_text, model_name, has_img=False):

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    img_status = "📸 ছবি" if has_img else "📝 টেক্সট"

    msg = f"""
🔔 নতুন প্রশ্ন!

👤 User: {user_id}
🤖 Model: {model_name}
🖼️ Type: {img_status}

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

# =========================
# IMAGE TO BASE64
# =========================

def process_image(image_pil):

    buffered = io.BytesIO()

    image_pil.save(buffered, format="JPEG")

    img_bytes = buffered.getvalue()

    return base64.b64encode(img_bytes).decode("utf-8")

# =========================
# GEMINI API FUNCTION
# =========================

def call_gemini_via_api(api_key, text_prompt, image_pil=None):

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={api_key}"

    headers = {
        "Content-Type": "application/json"
    }

    parts = []

    # IMAGE
    if image_pil:

        b64_string = process_image(image_pil)

        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": b64_string
            }
        })

    # TEXT
    final_text = text_prompt if text_prompt else "এই ছবিটি বিশ্লেষণ করে ব্যাখ্যা করো।"

    parts.append({
        "text": final_text
    })

    payload = {
        "contents": [
            {
                "parts": parts
            }
        ]
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60
        )

        # DEBUG (চাইলে remove করতে পারো)
        # st.write(response.text)

        if response.status_code == 200:

            data = response.json()

            candidates = data.get("candidates")

            if not candidates:
                return "❌ Gemini কোনো উত্তর দেয়নি।"

            return candidates[0]["content"]["parts"][0]["text"]

        elif response.status_code == 401:
            return "❌ Invalid Gemini API Key"

        elif response.status_code == 403:
            return "❌ Permission denied অথবা billing সমস্যা"

        elif response.status_code == 404:
            return "❌ Gemini model পাওয়া যায়নি"

        elif response.status_code == 429:
            return "⚠️ Rate limit exceeded"

        else:
            return f"❌ Error {response.status_code}\n\n{response.text}"

    except Exception as e:
        return f"❌ Error: {str(e)}"

# =========================
# SIDEBAR MODEL CHOICE
# =========================

model_choice = st.sidebar.radio(
    "🤖 AI Model নির্বাচন করো",
    [
        "Gemini (Multimodal)",
        "Llama3 (Groq - Text Only)"
    ]
)

# =========================
# CHAT HISTORY
# =========================

if "messages" not in st.session_state:
    st.session_state.messages = []

# পুরোনো মেসেজ দেখানো

for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

st.markdown("---")

# =========================
# CHAT INPUT
# =========================

prompt = st.chat_input(
    "এখানে প্রশ্ন লেখো অথবা ছবি আপলোড করো...",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"]
)

# =========================
# HANDLE USER INPUT
# =========================

if prompt:

    user_text = prompt.text

    uploaded_files = prompt.files

    current_user_id = get_unique_user_id()

    image_to_send = None

    has_image_flag = False

    # IMAGE HANDLE

    if uploaded_files and len(uploaded_files) > 0:

        uploaded_file = uploaded_files[0]

        image_to_send = Image.open(uploaded_file)

        has_image_flag = True

    # SHOW USER MESSAGE

    with st.chat_message("user"):

        if has_image_flag:
            st.image(
                image_to_send,
                caption="আপলোড করা ছবি",
                width=250
            )

        st.markdown(
            user_text if user_text
            else "[📸 শুধুমাত্র ছবি পাঠানো হয়েছে]"
        )

    # SAVE USER MESSAGE

    history_text = user_text if user_text else "[📸 ছবি পাঠানো হয়েছে]"

    st.session_state.messages.append({
        "role": "user",
        "content": history_text
    })

    # TELEGRAM SEND

    send_telegram(
        current_user_id,
        history_text,
        model_choice,
        has_img=has_image_flag
    )

    # =========================
    # ASSISTANT RESPONSE
    # =========================

    with st.chat_message("assistant"):

        response_placeholder = st.empty()

        full_response = ""

        try:

            # =========================
            # GEMINI
            # =========================

            if model_choice == "Gemini (Multimodal)":

                if not GEMINI_API_KEY:

                    full_response = "⚠️ Gemini API Key সেট করা নেই"

                else:

                    full_response = call_gemini_via_api(
                        GEMINI_API_KEY,
                        user_text,
                        image_to_send
                    )

            # =========================
            # LLAMA3
            # =========================

            elif model_choice == "Llama3 (Groq - Text Only)":

                if has_image_flag:

                    full_response = (
                        "⚠️ Llama3 ছবি বুঝতে পারে না। "
                        "ছবির জন্য Gemini ব্যবহার করো।"
                    )

                elif not GROQ_API_KEY:

                    full_response = "⚠️ Groq API Key সেট করা নেই"

                else:

                    client = Groq(
                        api_key=GROQ_API_KEY
                    )

                    completion = client.chat.completions.create(
                        model="llama3-8b-8192",
                        messages=[
                            {
                                "role": "user",
                                "content": user_text
                            }
                        ]
                    )

                    full_response = completion.choices[0].message.content

        except Exception as e:

            full_response = f"❌ Internal Error:\n{str(e)}"

        # SHOW RESPONSE

        response_placeholder.markdown(full_response)

        # SAVE RESPONSE

        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response
        })