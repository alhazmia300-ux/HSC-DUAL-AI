import firebase_admin
from firebase_admin import credentials, firestore
import json
import streamlit as st

@st.cache_resource
def init_firestore(firebase_json_raw):
    if not firebase_admin._apps:
        try:
            # যদি secrets থেকে ডেটাটি স্ট্রিং আকারে আসে, তবে তাকে ডিকশনারিতে রূপান্তর (Parse) করতে হবে
            if isinstance(firebase_json_raw, str):
                firebase_info = json.loads(firebase_json_raw)
            else:
                firebase_info = firebase_json_raw
            
            # ফাইলের বদলে সরাসরি ডিকশনারি পাস করার সঠিক নিয়ম
            cred = credentials.Certificate(firebase_info)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Firebase Configuration Error: {e}")
    return firestore.client()
import hashlib

def get_user_id():
    import streamlit as st
    email = st.session_state.user_email if st.session_state.user_email else "guest"
    return hashlib.md5(email.encode()).hexdigest()

