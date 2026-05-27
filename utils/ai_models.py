from groq import Groq
from google import genai

import time

# ======================================================
# GEMINI
# ======================================================

def call_gemini(
    api_key,
    prompt,
    image=None
):

    for attempt in range(3):

        try:

            client = genai.Client(
                api_key=api_key
            )

            # IMAGE
            if image:

                response = client.models.generate_content(

                    model="gemini-2.5-flash",

                    contents=[
                        prompt,
                        image
                    ]
                )

            # TEXT
            else:

                response = client.models.generate_content(

                    model="gemini-2.5-flash",

                    contents=prompt
                )

            return response.text

        except Exception as e:

            error_text = str(e)

            # Retry if busy
            if (

                "503" in error_text

                or

                "UNAVAILABLE" in error_text
            ):

                time.sleep(3)

                continue

            return f"❌ Gemini Error:\n{error_text}"

    return None

# ======================================================
# LLAMA3
# ======================================================

def call_llama(
    api_key,
    prompt,
    subject="General"
):

    try:

        client = Groq(
            api_key=api_key
        )

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[

                {
                    "role": "system",

                    "content":
                    f"You are an expert HSC {subject} teacher answering in Bengali."
                },

                {
                    "role": "user",

                    "content": prompt
                }
            ]
        )

        return completion \
            .choices[0] \
            .message.content

    except Exception as e:

        return f"❌ Llama Error:\n{str(e)}"

# ======================================================
# SMART RESPONSE
# ======================================================

def smart_ai_response(
    gemini_key,
    groq_key,
    prompt,
    subject,
    image=None
):

    # Try Gemini first
    gemini_response = call_gemini(

        gemini_key,

        prompt,

        image
    )

    if gemini_response:

        return gemini_response

    # IMAGE fallback impossible
    if image:

        return """

⚠️ Gemini server বর্তমানে busy।

ছবি/PDF বিশ্লেষণের জন্য Gemini প্রয়োজন।

⏳ একটু পরে আবার চেষ্টা করো।
"""

    # TEXT fallback → Llama3
    llama_response = call_llama(

        groq_key,

        prompt,

        subject
    )

    return (

        "⚠️ Gemini busy ছিল, তাই Llama3 দিয়ে উত্তর দেওয়া হলো:\n\n"

        +

        llama_response
    )