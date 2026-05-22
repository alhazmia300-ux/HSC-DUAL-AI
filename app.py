import streamlit as st
import google.generativeai as genai
from groq import Groq
from PIL import Image
import requests
import hashlib

# পেজ সেটআপ
st.set_page_config(page_title="HSC Dual AI Tutor", page_icon="🎓", layout="centered")

st.title("🎓 HSC Dual AI Tutor")
st.write("তোমার HSC পরীক্ষার যেকোনো বিষয় এখানে জিজ্ঞেস করো!")

# Secrets লোড
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

# টেলিগ্রাম ফাংশন
def send_telegram(msg):
    token = st.secrets.get("TELEGRAM_BOT_TOKEN")
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": msg})

# মডেল চয়েস
model_choice = st.sidebar.radio("মডেল:", ["Gemini 1.5 Flash", "Llama3"])

# চ্যাট হিস্ট্রি
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if "image" in msg: st.image(msg["image"], width=200)
        st.markdown(msg["content"])

# ইনপুট এরিয়া
user_text = st.text_input("তোমার প্রশ্নটি লেখো:")
uploaded_file = st.file_uploader("বইয়ের ছবি আপলোড করো (ঐচ্ছিক):", type=["jpg", "png"])

if st.button("Send and Ask"):
    image = None
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, width=200)

    # ইউজার মেসেজ সেভ
    st.session_state.messages.append({"role": "user", "content": user_text, "image": image})
    
    with st.chat_message("assistant"):
        response_text = ""
        try:
            if model_choice == "Gemini 1.5 Flash":
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel("gemini-1.5-flash") # সঠিক মডিউল ও ফাংশন
                if image:
                    response = model.generate_content([user_text, image])
                else:
                    response = model.generate_content(user_text)
                response_text = response.text
            
            else:
                client = Groq(api_key=GROQ_API_KEY)
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": user_text}],
                    model="llama3-8b-8192",
                )
                response_text = chat_completion.choices[0].message.content
                
            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})
            send_telegram(f"Question: {user_text}")
            
        except Exception as e:
            st.error(f"এরর: {str(e)}")
