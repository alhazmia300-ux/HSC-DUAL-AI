 import requests

# ======================================================
# SIGN UP
# ======================================================

def signup(email, password, api_key):

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    try:

        r = requests.post(
            url,
            json=payload,
            timeout=10
        )

        return r.json()

    except Exception as e:

        return {
            "error":{
                "message":str(e)
            }
        }

# ======================================================
# LOGIN
# ======================================================

def login(email, password, api_key):

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    try:

        r = requests.post(
            url,
            json=payload,
            timeout=10
        )

        return r.json()

    except Exception as e:

        return {
            "error":{
                "message":str(e)
            }
        }