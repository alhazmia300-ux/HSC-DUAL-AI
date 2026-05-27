 import firebase_admin
import hashlib
import time
import uuid

from firebase_admin import credentials
from firebase_admin import firestore

# ======================================================
# FIREBASE INIT
# ======================================================

def init_firestore(firebase_json):

    if not firebase_admin._apps:

        cred = credentials.Certificate(
            firebase_json
        )

        firebase_admin.initialize_app(
            cred
        )

    return firestore.client()

# ======================================================
# USER ID
# ======================================================

def get_user_id(email):

    return hashlib.md5(
        email.encode()
    ).hexdigest()

# ======================================================
# CREATE CHAT
# ======================================================

def create_chat(db, user_id):

    chat_id = str(uuid.uuid4())

    db.collection("users") \
        .document(user_id) \
        .collection("chats") \
        .document(chat_id) \
        .set({

            "title":"New Chat",

            "created_at":time.time(),

            "updated_at":time.time()

        })

    return chat_id

# ======================================================
# SAVE MESSAGE
# ======================================================

def save_message(
    db,
    user_id,
    chat_id,
    role,
    content
):

    db.collection("users") \
        .document(user_id) \
        .collection("chats") \
        .document(chat_id) \
        .collection("messages") \
        .add({

            "role":role,

            "content":content,

            "created_at":time.time()

        })

    db.collection("users") \
        .document(user_id) \
        .collection("chats") \
        .document(chat_id) \
        .update({

            "updated_at":time.time()

        })

# ======================================================
# UPDATE CHAT TITLE
# ======================================================

def update_chat_title(
    db,
    user_id,
    chat_id,
    title
):

    db.collection("users") \
        .document(user_id) \
        .collection("chats") \
        .document(chat_id) \
        .update({

            "title":title[:40]

        })

# ======================================================
# LOAD MESSAGES
# ======================================================

def load_messages(
    db,
    user_id,
    chat_id
):

    msgs = db.collection("users") \
        .document(user_id) \
        .collection("chats") \
        .document(chat_id) \
        .collection("messages") \
        .stream()

    temp = []

    for msg in msgs:

        data = msg.to_dict()

        temp.append({

            "role":data.get("role"),

            "content":data.get("content"),

            "created_at":data.get(
                "created_at",
                0
            )

        })

    temp.sort(
        key=lambda x:x["created_at"]
    )

    return temp

# ======================================================
# GET CHAT LIST
# ======================================================

def get_chat_list(
    db,
    user_id
):

    chats = db.collection("users") \
        .document(user_id) \
        .collection("chats") \
        .stream()

    temp = []

    for chat in chats:

        data = chat.to_dict()

        # empty chat skip
        if data.get("title") == "New Chat":
            continue

        temp.append({

            "chat_id":chat.id,

            "title":data.get(
                "title",
                "Chat"
            ),

            "updated_at":data.get(
                "updated_at",
                0
            )

        })

    temp.sort(
        key=lambda x:x["updated_at"],
        reverse=True
    )

    return temp

# ======================================================
# DELETE CHAT
# ======================================================

def delete_chat(
    db,
    user_id,
    chat_id
):

    msgs = db.collection("users") \
        .document(user_id) \
        .collection("chats") \
        .document(chat_id) \
        .collection("messages") \
        .stream()

    for msg in msgs:

        msg.reference.delete()

    db.collection("users") \
        .document(user_id) \
        .collection("chats") \
        .document(chat_id) \
        .delete()