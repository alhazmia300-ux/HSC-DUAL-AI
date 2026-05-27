import streamlit as st
import time

# ======================================================
# GLOBAL CSS
# ======================================================

def load_css():

    st.markdown(
        """

<style>

.block-container{
    padding-top:0.8rem;
}

/* Sidebar */
section[data-testid="stSidebar"]{
    width:320px !important;
}

/* Chat Bubble */
[data-testid="stChatMessage"]{
    border-radius:18px;
    padding:14px;
    margin-bottom:10px;
}

/* Buttons */
.stButton button{
    border-radius:12px;
    width:100%;
}

/* Inputs */
.stTextInput input{
    border-radius:12px;
}

/* Profile */
.profile-center{
    display:flex;
    justify-content:center;
    margin-top:5px;
    margin-bottom:5px;
}

.profile-circle{
    width:110px;
    height:110px;
    border-radius:50%;
    overflow:hidden;
    border:4px solid #7C4DFF;
}

.profile-circle img{
    width:100%;
    height:100%;
    object-fit:cover;
}

</style>

        """,
        unsafe_allow_html=True
    )

# ======================================================
# TYPING EFFECT
# ======================================================

def typing_effect(
    placeholder,
    text,
    speed=0.002
):

    typed = ""

    for char in text:

        typed += char

        placeholder.markdown(typed)

        time.sleep(speed)