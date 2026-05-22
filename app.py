import streamlit as st
import google.generativeai as genai
from groq import Groq

# পেজ সেটআপ
st.set_page_config(page_title="HSC Dual AI Tutor", page_icon="🎓", layout="centered")

st.title("🎓 HSC Dual AI Tutor")
st.subheader("Llama3 এবং Gemini-র সমন্বয়ে HSC প্রস্তুতি")
st.write("তোমার HSC পরীক্ষার যেকোনো বিষয়ের প্রশ্ন এখানে জিজ্ঞেস করো!")
st.caption("🚀 Created by ALhaz")


# স্ট্রিমলিট সিক্রেট থেকে API Key লোড করা
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

# সাইডবারে মডেল সিলেক্ট করার অপশন
st.sidebar.title("🤖 মডেল সেটিংস")
model_choice = st.sidebar.radio("তোমার পছন্দের AI মডেলটি বেছে নাও:", ["Gemini 2.5 Flash", "Llama3 (via Groq)"])

# চ্যাট হিস্ট্রি চালু করা (মেমোরি ধরে রাখার জন্য)
if "messages" not in st.session_state:
    st.session_state.messages = []

# আগের চ্যাট মেসেজগুলো স্ক্রিনে দেখানো
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ইউজারের ইনপুট নেওয়ার ঘর
if user_input := st.chat_input("এখানে তোমার প্রশ্নটি লেখো... (যেমন: English Changing sentence এর নিয়ম কী?)"):
    
    # ইউজারের মেসেজ স্ক্রিনে দেখানো এবং মেমোরিতে সেভ করা
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # AI এর উত্তরের জন্য লোডিং ইফেক্ট
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        try:
            # ১. জেমিনি মডেল রেসপন্স লজিক
            if model_choice == "Gemini 2.5 Flash":
                if not GEMINI_API_KEY:
                    full_response = "⚠️ দুঃখিত, Streamlit Secrets-এ Gemini API Key সেট করা নেই।"
                else:
                    genai.configure(api_key=GEMINI_API_KEY)
                    # লেটেস্ট ওয়ান-লাইন জেনারেশন মেথড
                    response = genai.generate_text(
                        model="models/gemini-2.5-flash",
                        prompt=user_input
                    )
                    full_response = response.text
            
            # ২. লামা৩ মডেল রেসপন্স লজিক
            elif model_choice == "Llama3 (via Groq)":
                if not GROQ_API_KEY:
                    full_response = "⚠️ দুঃখিত, Streamlit Secrets-এ Groq API Key সেট করা নেই।"
                else:
                    client = Groq(api_key=GROQ_API_KEY)
                    completion = client.chat.completions.create(
                        model="llama3-8b-8192",
                        messages=[{"role": "user", "content": user_input}]
                    )
                    full_response = completion.choices[0].message.content

        except Exception as e:
            # যদি নতুন মেথডে সমস্যা হয়, তবে অল্টারনেটিভ মেথড ট্রাই করবে
            try:
                if model_choice == "Gemini 2.5 Flash" and GEMINI_API_KEY:
                    model = genai.GenerativeModel("gemini-2.5-flash")
                    response = model.generate_content(user_input)
                    full_response = response.text
                else:
                    full_response = f"❌ একটি এরর ঘটেছে: {str(e)}"
            except Exception as e_inner:
                full_response = f"❌ একটি এরর ঘটেছে: {str(e_inner)}"
        
        # স্ক্রিনে উত্তরটি দেখানো এবং সেভ করা
        response_placeholder.markdown(full_response)
    st.session_state.messages.append({"role": "assistant", "content": full_response})