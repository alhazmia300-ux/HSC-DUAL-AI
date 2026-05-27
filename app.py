# =========================================================
# PREMIUM PROFILE PICTURE SYSTEM
# =========================================================

from streamlit_cropper import st_cropper
from PIL import Image, ImageDraw
import io
import base64

# =========================================================
# SESSION STATE
# =========================================================

if "change_pfp" not in st.session_state:
    st.session_state.change_pfp = False

# =========================================================
# LOAD PROFILE PIC
# =========================================================

def get_profile_picture():

    try:

        doc = db.collection("users_profile") \
            .document(get_user_id()) \
            .get()

        if doc.exists:

            data = doc.to_dict()

            return data.get("profile_picture")

    except:
        pass

    return None

# =========================================================
# SAVE PROFILE PIC
# =========================================================

def save_profile_picture(image):

    try:

        buffered = io.BytesIO()

        image.save(buffered, format="PNG")

        img_str = base64.b64encode(
            buffered.getvalue()
        ).decode()

        db.collection("users_profile") \
            .document(get_user_id()) \
            .set({

                "profile_picture": img_str

            }, merge=True)

    except Exception as e:

        st.error(str(e))

# =========================================================
# CIRCLE IMAGE MASK
# =========================================================

def make_circle_image(img):

    img = img.convert("RGBA")

    size = min(img.size)

    img = img.resize((size, size))

    mask = Image.new("L", (size, size), 0)

    draw = ImageDraw.Draw(mask)

    draw.ellipse((0, 0, size, size), fill=255)

    output = Image.new("RGBA", (size, size))

    output.paste(img, (0, 0), mask)

    return output

# =========================================================
# SIDEBAR PROFILE UI
# =========================================================

st.sidebar.markdown("""
<style>

.profile-container{
display:flex;
justify-content:center;
margin-top:-10px;
margin-bottom:8px;
}

.profile-circle{
width:110px;
height:110px;
border-radius:50%;
overflow:hidden;
border:3px solid #7C4DFF;
box-shadow:0 0 20px rgba(124,77,255,0.7);
cursor:pointer;
}

.profile-circle img{
width:100%;
height:100%;
object-fit:cover;
}

.center-btn{
display:flex;
justify-content:center;
margin-top:-5px;
margin-bottom:10px;
}

.small-gap{
margin-top:-8px;
margin-bottom:-8px;
}

</style>
""", unsafe_allow_html=True)

profile_picture = get_profile_picture()

# =========================================================
# SHOW PROFILE
# =========================================================

if profile_picture:

    st.sidebar.markdown(
        f"""
        <div class="profile-container">
            <div class="profile-circle">
                <img src="data:image/png;base64,{profile_picture}">
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

else:

    st.sidebar.markdown("""
    <div class="profile-container">
        <div class="profile-circle"
        style="
        display:flex;
        align-items:center;
        justify-content:center;
        background:#1E1E1E;
        color:white;
        font-size:42px;
        ">
        +
        </div>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# CHANGE PROFILE BUTTON
# =========================================================

with st.sidebar:

    st.markdown('<div class="center-btn">', unsafe_allow_html=True)

    if st.button(
        "📸 Change Profile Picture",
        use_container_width=True
    ):

        st.session_state.change_pfp = True

    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# PROFILE EDIT INTERFACE
# =========================================================

if st.session_state.change_pfp:

    st.sidebar.markdown("---")

    st.sidebar.markdown("### ✨ Upload & Crop")

    uploaded_profile = st.sidebar.file_uploader(

        "Choose Image",

        type=["png", "jpg", "jpeg"],

        key="profile_uploader"

    )

    if uploaded_profile:

        image = Image.open(uploaded_profile)

        st.sidebar.markdown("#### ✂️ Crop Image")

        cropped_img = st_cropper(

            image,

            realtime_update=True,

            box_color="#7C4DFF",

            aspect_ratio=(1, 1)

        )

        st.sidebar.markdown("### 👀 Preview")

        preview = make_circle_image(cropped_img)

        st.sidebar.image(preview, width=130)

        col1, col2 = st.sidebar.columns(2)

        with col1:

            if st.button("✅ Save"):

                final_image = make_circle_image(cropped_img)

                save_profile_picture(final_image)

                st.session_state.change_pfp = False

                st.success("Saved!")

                time.sleep(1)

                st.rerun()

        with col2:

            if st.button("❌ Cancel"):

                st.session_state.change_pfp = False

                st.rerun()