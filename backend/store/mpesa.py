import base64
import datetime
import requests
from django.conf import settings


def format_phone_number(phone_number):
    """Ensure M-Pesa phone number is in the correct 2547XXXXXXXX format"""
    phone_number = str(phone_number).strip()
    if phone_number.startswith("0"):
        return "254" + phone_number[1:]
    elif phone_number.startswith("+"):
        return phone_number[1:]
    elif phone_number.startswith("254"):
        return phone_number
    else:
        return "254" + phone_number  # fallback


def get_mpesa_token():
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(url, auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET))
    return response.json().get("access_token")


def lipa_stk_push(phone_number, amount, account_reference, transaction_desc):
    token = get_mpesa_token()
    headers = {"Authorization": f"Bearer {token}"}

    # ✅ Ensure the phone number format is correct
    phone_number = format_phone_number(phone_number)

        # ✅ Ensure amount is a positive integer
    try:
        amount = int(float(amount))
        if amount <= 0:
            amount = 1
    except:
        amount = 1


    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    shortcode = settings.MPESA_SHORTCODE
    passkey = settings.MPESA_PASSKEY
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode("utf-8")

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_desc,
    }

    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    response = requests.post(url, json=payload, headers=headers)
    print("📡 M-Pesa STK Response:", response.json())  # ✅ Debug log

    return response.json()
