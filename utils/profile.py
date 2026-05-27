from PIL import Image
from PIL import ImageDraw

import io
import base64

# ======================================================
# CIRCLE IMAGE
# ======================================================

def make_circle_image(img):

    img = img.convert("RGBA")

    size = min(img.size)

    img = img.resize(
        (size,size)
    )

    mask = Image.new(
        "L",
        (size,size),
        0
    )

    draw = ImageDraw.Draw(mask)

    draw.ellipse(
        (0,0,size,size),
        fill=255
    )

    output = Image.new(
        "RGBA",
        (size,size)
    )

    output.paste(
        img,
        (0,0),
        mask
    )

    return output

# ======================================================
# IMAGE → BASE64
# ======================================================

def image_to_base64(img):

    buffer = io.BytesIO()

    img.save(
        buffer,
        format="PNG"
    )

    return base64.b64encode(
        buffer.getvalue()
    ).decode()

# ======================================================
# BASE64 → IMAGE
# ======================================================

def base64_to_image(base64_string):

    image_data = base64.b64decode(
        base64_string
    )

    return Image.open(
        io.BytesIO(image_data)
    )