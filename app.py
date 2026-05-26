# ======================================================
# SEARCH CHAT
# ======================================================

search_chat = st.sidebar.text_input(
    "🔍 Search Chats",
    placeholder="Search..."
)

# ======================================================
# GET CHAT LIST
# ======================================================

def get_chat_list():

    chats = db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .stream()

    temp = []

    for chat in chats:

        data = chat.to_dict()

        title = data.get(
            "title",
            ""
        ).strip()

        # Skip Empty Chats
        if not title:
            continue

        # Skip Untitled
        if title.lower() in [
            "new chat",
            "untitled",
            "new conversation"
        ]:
            continue

        temp.append({

            "chat_id": chat.id,

            "title": title,

            "created_at": data.get(
                "created_at",
                0
            )
        })

    # Latest First
    temp.sort(
        key=lambda x: x["created_at"],
        reverse=True
    )

    # Search Filter
    if search_chat:

        temp = [

            c for c in temp

            if search_chat.lower()
            in c["title"].lower()
        ]

    return temp

# ======================================================
# RENAME CHAT
# ======================================================

def rename_chat(chat_id, new_title):

    db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .document(chat_id) \
        .update({

            "title": new_title
        })

# ======================================================
# DELETE SINGLE CHAT
# ======================================================

def delete_chat(chat_id):

    # Delete Messages
    messages = db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .document(chat_id) \
        .collection("messages") \
        .stream()

    for msg in messages:

        msg.reference.delete()

    # Delete Chat Document
    db.collection("users") \
        .document(get_user_id()) \
        .collection("chats") \
        .document(chat_id) \
        .delete()

# ======================================================
# CHAT HISTORY UI
# ======================================================

st.sidebar.markdown("### 💬 Chats")

chat_list = get_chat_list()

if chat_list:

    for chat in chat_list:

        chat_id = chat["chat_id"]

        title = chat["title"]

        row1, row2, row3 = st.sidebar.columns([6,1,1])

        # ==============================================
        # OPEN CHAT
        # ==============================================

        with row1:

            if st.button(
                f"🗨️ {title}",
                key=f"open_{chat_id}",
                use_container_width=True
            ):

                st.session_state.current_chat_id = chat_id

                st.session_state.messages = load_messages(chat_id)

                st.rerun()

        # ==============================================
        # RENAME BUTTON
        # ==============================================

        with row2:

            if st.button(
                "✏️",
                key=f"rename_{chat_id}"
            ):

                st.session_state[
                    "rename_chat_id"
                ] = chat_id

        # ==============================================
        # DELETE BUTTON
        # ==============================================

        with row3:

            if st.button(
                "🗑️",
                key=f"delete_{chat_id}"
            ):

                delete_chat(chat_id)

                # Current Chat Deleted
                if (
                    st.session_state.current_chat_id
                    == chat_id
                ):

                    st.session_state.current_chat_id = None

                    st.session_state.messages = []

                st.rerun()

else:

    st.sidebar.info(
        "No chats found"
    )

# ======================================================
# RENAME INPUT BOX
# ======================================================

if st.session_state.get("rename_chat_id"):

    rename_id = st.session_state[
        "rename_chat_id"
    ]

    current_title = ""

    for c in chat_list:

        if c["chat_id"] == rename_id:

            current_title = c["title"]

    st.sidebar.markdown("---")

    st.sidebar.markdown("### ✏️ Rename Chat")

    new_title = st.sidebar.text_input(
        "New Title",
        value=current_title
    )

    save_rename = st.sidebar.button(
        "✅ Save Rename"
    )

    cancel_rename = st.sidebar.button(
        "❌ Cancel"
    )

    if save_rename:

        if new_title.strip():

            rename_chat(
                rename_id,
                new_title.strip()
            )

            st.session_state[
                "rename_chat_id"
            ] = None

            st.rerun()

    if cancel_rename:

        st.session_state[
            "rename_chat_id"
        ] = None

        st.rerun()