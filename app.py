import streamlit as st
import google.generativeai as genai
from groq import Groq
from PIL import Image
import requests
import hashlib  # আইপি অ্যাড্রেসকে সিক্রেট আইডিতে রূপান্তর করার জন্য

# পেজ সেটআপ
st.set_page_config(page_title="HSC Dual AI Tutor", page_icon="🎓", layout="centered")

st.title("🎓 HSC Dual AI Tutor")
st.subheader("Llama3 এবং Gemini-র সমন্বয়ে HSC প্রস্তুতি")
st.write("তোমার HSC পরীক্ষার যেকোনো বিষয়ের প্রশ্ন এখানে জিজ্ঞেস করো!")
st.caption("🚀 Created by ALhaz")

# স্ট্রিমলিট সিক্রেট থেকে API Key এবং Telegram Credentials লোড করা
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")

# ইউজারের আইপি অ্যাড্রেস থেকে একটি ইউনিক এবং ছোট আইডি তৈরি করার ফাংশন
def get_unique_user_id():
    try:
        # স্ট্রিমলিটের হেডার থেকে ইউজারের আইপি নেওয়ার চেষ্টা
        headers = st.context.headers
        user_ip = headers.get("X-Forwarded-For", "Unknown_User")
        if "," in user_ip:
            user_ip = user_ip.split(",")[0]
        
        # আইপি অ্যাড্রেসটি সরাসরি না দেখিয়ে নিরাপত্তা ও প্রাইভেসির জন্য সেটিকে একটি ৫ অক্ষরের সিক্রেট কোডে রূপান্তর করা
        user_hash = hashlib.md5(user_ip.encode()).hexdigest()[:5]
        return f"User_{user_hash}"
    except Exception:
        return "User_Unknown"

# টেলিগ্রামে সিক্রেট মেসেজ পাঠানোর ফাংশন (ইউজার আইডিসহ)
def send_telegram_notification(user_id, user_question, model_used, has_image=False):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        image_status = "📸 [ছবি আপলোড করা হয়েছে]" if has_image else "📝 [শুধুমাত্র টেক্সট]"
        
        # মেসেজের ফরম্যাটে ইউজার আইডি যুক্ত করা হয়েছে
        text_message = (
            f"🔔 *নতুন প্রশ্ন এসেছে!*\n\n"
            f"👤 *ইউজার আইডি:* `{user_id}`\n"
            f"🤖 *মডেল:* {model_used}\n"
            f"🖼️ *টাইপ:* {image_status}\n"
            f"❓ *প্রশ্ন:* {user_question}"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text_message,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload)
        except Exception:
            pass

# সাইডবারে MODEL SELECT
st.sidebar.title("🤖 MODEL SETTINGS")
model_choice = st.sidebar.radio("তোমার পছন্দের AI মডেলটি বেছে নাও:", ["Gemini 1.5 Flash (Multimodal)", "Llama3 (via Groq - Text only)"])

# চ্যাট হিস্ট্রি চালু করা
if "messages" not in st.session_state:
    st.session_state.messages = []

# আগের চ্যাট মেসেজগুলো স্ক্রিনে দেখানো
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user" and message.get("image"):
            st.image(message["image"], caption="বইয়ের ছবি", width=250)
        st.markdown(message["content"])

st.markdown("---")
col1, col2 = st.columns([10, 1])
with col1:
    user_input = st.chat_input("এখানে তোমার প্রশ্নটি লেখো... (যেমন: Modifiers এর নিয়ম কী?)")
with col2:
    uploaded_image = st.file_uploader("", type=["jpg", "jpeg", "png"], label_visibility="collapsed")

if user_input or uploaded_image:
    image_to_send = None
    has_image_flag = False
    if uploaded_image:
        image_to_send = Image.open(uploaded_image)
        has_image_flag = True

    # ইউজারের মেসেজ স্ক্রিনে দেখানো
    with st.chat_message("user"):
        if uploaded_image:
            st.image(uploaded_image, caption="বইয়ের ছবি", width=250)
        st.markdown(user_input if user_input else "[শুধুমাত্র ছবি দিয়ে প্রশ্ন করা হয়েছে]")
    
    # মেমোরিতে সেভ করা
    st.session_state.messages.append({"role": "user", "content": user_input if user_input else "", "image": uploaded_image.read() if uploaded_image else None})

    # 🚀 ইউনিক ইউজার আইডি বের করা এবং টেলিগ্রামে পাঠানো
    current_user_id = get_unique_user_id()
    question_summary = user_input if user_input else "[কোনো টেক্সট লেখেনি, শুধু ছবি পাঠিয়েছে]"
    send_telegram_notification(current_user_id, question_summary, model_choice, has_image=has_image_flag)

    # assistant response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        try:
            if model_choice == "Gemini 1.5 Flash (Multimodal)":
                if not GEMINI_API_KEY:
                    full_response = "⚠️ দুঃখিত, Streamlit Secrets-এ Gemini API Key সেট করা নেই।"
                else:
                    genai.configure(api_key=GEMINI_API_KEY)
                    if uploaded_image and user_input:
                        response = genai.generate_text(model="models/gemini-2.5-flash", prompt=[user_input, image_to_send])
                    elif uploaded_image:
                        response = genai.generate_text(model="models/gemini-2.5-flash", prompt=["এই ছবিতে কী আছে বুঝিয়ে বলো:", image_to_send])
                    else:
                        response = genai.generate_text(model="models/gemini-2.5-flash", prompt=user_input)
                    full_response = response.text
            
            elif model_choice == "Llama3 (via Groq - Text only)":
                if uploaded_image:
                    full_response = "⚠️ দুঃখিত, Llama3 শুধুমাত্র টেক্সট নিয়ে কাজ করতে পারে। ছবি বোঝার জন্য দয়া করে 'Gemini 1.5 Flash (Multimodal)' সিলেক্ট করো।"
                elif not user_input:
                    full_response = "⚠️ দুঃখিত, কোনো টেক্সট প্রশ্ন ছাড়া উত্তর দিতে পারছি না। তুমি কি বইয়ের ছবি নিয়ে প্রশ্ন করছো? তাহলে দয়া করে 'Gemini 1.5 Flash (Multimodal)' সিলেক্ট করো।"
                elif not GROQ_API_KEY:
                    full_response = "⚠️ দুঃখিত, Streamlit Secrets-এ Groq API Key সেট করা নেই।"
                else:
                    client = Groq(api_key=GROQ_API_KEY)
                    completion = client.chat.completions.create(
                        model="llama3-8b-8192",
                        messages=[{"role": "user", "content": user_input}]
                    )
                    full_response = completion.choices[0].message.content

        except Exception as e:
            full_response = f"❌ একটি এরর ঘটেছে: {str(e)}"
        
        response_placeholder.markdown(full_response)
    st.session_state.messages.append({"role": "assistant", "content": full_response})
