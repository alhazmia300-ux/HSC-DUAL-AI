import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st
import hashlib
import json
import time

# ======================================================
# INIT FIRESTORE
# ======================================================
@st.cache_resource
def init_firestore(_firebase_json_raw):
    if not firebase_admin._apps:
        try:
            if isinstance(_firebase_json_raw, str):
                firebase_info = json.loads(_firebase_json_raw)
            else:
                firebase_info = dict(_firebase_json_raw)
            cred = credentials.Certificate(firebase_info)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Firebase Error: {e}")
    return firestore.client()

# ======================================================
# USER ID
# ======================================================
def get_user_id(email_input=None):
    email = email_input or st.session_state.get("user_email", "guest") or "guest"
    return hashlib.md5(email.encode()).hexdigest()

# ======================================================
# CREATE CHAT
# ======================================================
def create_chat(db, user_id):
    chat_id = f"chat_{int(time.time())}"
    db.collection("chats").document(user_id)\
      .collection("sessions").document(chat_id)\
      .set({"title": "New Chat", "created_at": time.time()})
    return chat_id

# ======================================================
# GET CHAT LIST
# ======================================================
def get_chat_list(db, user_id):
    try:
        docs = db.collection("chats").document(user_id)\
                 .collection("sessions")\
                 .stream()
        result = []
        for d in docs:
            data = d.to_dict()
            result.append({
                "chat_id": d.id,
                "title": data.get("title", "New Chat"),
                "created_at": data.get("created_at", 0)
            })
        result.sort(key=lambda x: x["created_at"], reverse=True)
        return result
    except:
        return []

# ======================================================
# DELETE CHAT
# ======================================================
def delete_chat(db, user_id, chat_id):
    try:
        msgs = db.collection("chats").document(user_id)\
                 .collection("sessions").document(chat_id)\
                 .collection("messages").stream()
        for m in msgs:
            m.reference.delete()
        db.collection("chats").document(user_id)\
          .collection("sessions").document(chat_id).delete()
    except:
        pass

# ======================================================
# SAVE MESSAGE
# ======================================================
def save_message(db, user_id, chat_id, role, content):
    try:
        db.collection("chats").document(user_id)\
          .collection("sessions").document(chat_id)\
          .collection("messages")\
          .add({
              "role": role,
              "content": content,
              "timestamp": time.time()
          })
    except:
        pass

# ======================================================
# LOAD MESSAGES
# ======================================================
def load_messages(db, user_id, chat_id):
    try:
        docs = db.collection("chats").document(user_id)\
                 .collection("sessions").document(chat_id)\
                 .collection("messages")\
                 .stream()
        result = []
        for d in docs:
            data = d.to_dict()
            result.append({
                "role": data.get("role", "user"),
                "content": data.get("content", ""),
                "timestamp": data.get("timestamp", 0)
            })
        result.sort(key=lambda x: x["timestamp"])
        return [{"role": m["role"], "content": m["content"]} for m in result]
    except:
        return []

# ======================================================
# UPDATE CHAT TITLE
# ======================================================
def update_chat_title(db, user_id, chat_id, text):
    try:
        title = text[:30] if text else "New Chat"
        db.collection("chats").document(user_id)\
          .collection("sessions").document(chat_id)\
          .update({"title": title})
    except:
        pass