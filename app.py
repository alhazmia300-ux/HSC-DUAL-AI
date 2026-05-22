import streamlit as st
import google.generativeai as genai
from groq import Groq
from PIL import Image
import requests
import hashlib

# পেজ সেটআপ
st.set_page_config(page_title="HSC Dual AI Tutor", page_icon="🎓", layout="centered")

st.title("🎓 HSC Dual AI Tutor")
st.subheader("Llama3 এবং Gemini-র সমন্বয়ে HSC প্রস্তুতি")
st.write("তোমার HSC পরীক্ষার যেকোনো বিষয়ের প্রশ্ন এখানে জিজ্ঞেস করো!")
st.caption("🚀 Created by ALhaz")

# Secrets লোড
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")

# ইউজারের আইপি থেকে ইউনিক আইডি তৈরি করার ফাংশন
def get_unique_user_id():
    try:
        user_ip = st.context.headers.get("X-Forwarded-For", "Unknown_User")
        if "," in user_ip:
            user_ip = user_ip.split(",")[0]
        user_hash = hashlib.md5(user_ip.encode()).hexdigest()[:5]
        return f"User_{user_hash}"
    except Exception:
        return "User_Unknown"

# টেলিগ্রামে মেসেজ পাঠানোর ফাংশন
def send_telegram(user_id, q_text, model_name, has_img=False):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        img_status = "📸 [ছবি আপলোড করা হয়েছে]" if has_img else "📝 [শুধু টেক্সট]"
        msg = f"🔔 *নতুন প্রশ্ন!*\n\n👤 *আইডি:* `{user_id}`\n🤖 *মডেল:* {model_name}\n🖼️ *টাইপ:* {img_status}\n❓ *প্রশ্ন:* {q_text}"
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        except Exception:
            pass

# সাইডবারে মডেল চয়েস
model_choice = st.sidebar.radio("🤖 তোমার পছন্দের AI মডেলটি বেছে নাও:", ["Gemini (Multimodal)", "Llama3 (via Groq - Text only)"])

# চ্যাট হিস্ট্রি চালু করা
if "messages" not in st.session_state:
    st.session_state.messages = []

# স্ক্রিনে আগের চ্যাটগুলো দেখানো
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

st.markdown("---")

# 🛠️ [মাস্টার ফিক্স] চ্যাট ইনপুট এবং ফাইল আপলোডারকে একসাথে মার্জ করা হয়েছে
prompt = st.chat_input(
    "এখানে তোমার প্রশ্নটি লেখো বা প্লাস (+) বাটনে চেপে ছবি আপলোড করো...",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"]
)

# ইউজার যখন মেসেজ টাইপ করে বা ছবি দিয়ে সেন্ড করবে
if prompt:
    user_text = prompt.text
    uploaded_file = prompt.file
    
    current_user_id = get_unique_user_id()
    image_to_send = None
    has_image_flag = False
    
    if uploaded_file:
        image_to_send = Image.open(uploaded_file)
        has_image_flag = True

    # ইউজারের ইনপুট স্ক্রিনে চ্যাট বাবল হিসেবে দেখানো
    with st.chat_message("user"):
        if has_image_flag:
            st.image(image_to_send, caption="আপলোড করা বইয়ের ছবি", width=250)
        st.markdown(user_text if user_text else "[শুধুমাত্র ছবি দিয়ে প্রশ্ন করা হয়েছে]")
    
    # চ্যাট মেমোরিতে সেভ করা
    history_text = user_text if user_text else "[📸 ছবি পাঠানো হয়েছে]"
    st.session_state.messages.append({"role": "user", "content": history_text})

    # টেলিগ্রামে নোটিফিকেশন
    send_telegram(current_user_id, history_text, model_choice, has_img=has_image_flag)

    # অ্যাসিস্ট্যান্ট রেসপন্স জেনারেট করা
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        try:
            # ১. জেমিনি মডেল রেসপন্স
            if model_choice == "Gemini (Multimodal)":
                if not GEMINI_API_KEY:
                    full_response = "⚠️ দুঃখিত, Streamlit Secrets-এ Gemini API Key সেট করা নেই।"
                else:
                    genai.configure(api_key=GEMINI_API_KEY)
                    model = genai.GenerativeModel("gemini-1.5-flash-8b") # লাইটওয়েট এবং হাই-কোটা মডেল
                    
                    if has_image_flag and user_text:
                        response = model.generate_content([user_text, image_to_send])
                    elif has_image_flag:
                        response = model.generate_content(["এই ছবিতে কী আছে বা কী জানতে চাওয়া হয়েছে বুঝিয়ে বলো:", image_to_send])
                    else:
                        response = model.generate_content(user_text)
                    
                    full_response = response.text
            
            # ২. লামা৩ মডেল রেসপন্স
            elif model_choice == "Llama3 (via Groq - Text only)":
                if has_image_flag:
                    full_response = "⚠️ দুঃখিত, Llama3 ছবি পড়তে পারে না। ছবির প্রশ্নের জন্য সাইডবার থেকে 'Gemini' সিলেক্ট করো।"
                elif not GROQ_API_KEY:
                    full_response = "⚠️ দুঃখিত, Streamlit Secrets-এ Groq API Key সেট করা নেই।"
                else:
                    client = Groq(api_key=GROQ_API_KEY)
                    completion = client.chat.completions.create(
                        model="llama3-8b-8192",
                        messages=[{"role": "user", "content": user_text}]
                    )
                    full_response = completion.choices[0].message.content

        except Exception as e:
            full_response = f"❌ একটি ইন্টারনাল এরর ঘটেছে: {str(e)}"
        
        # স্ক্রিনে ফাইনাল উত্তর দেখানো এবং মেমোরিতে রাখা
        response_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})
