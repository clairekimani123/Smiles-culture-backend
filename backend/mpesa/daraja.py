# backend/mpesa/daraja.py
import base64
import requests
from datetime import datetime
from django.conf import settings


def _auth_headers():
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials" \
        if settings.MPESA_ENV == "sandbox" else \
        "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(url, auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET), timeout=10)
    r.raise_for_status()
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _password():
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{ts}".encode()
    return base64.b64encode(raw).decode(), ts


def stk_push(phone: str, amount: int, account_ref: str, description: str) -> dict:
    """Initiate STK push. Returns Daraja's response dict (contains CheckoutRequestID)."""
    base = "https://sandbox.safaricom.co.ke" if settings.MPESA_ENV == "sandbox" \
           else "https://api.safaricom.co.ke"
    password, ts = _password()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": ts,
        "TransactionType": "CustomerPayBillOnline",   # use CustomerBuyGoodsOnline for Till numbers
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_ref,
        "TransactionDesc": description,
    }
    r = requests.post(f"{base}/mpesa/stkpush/v1/processrequest",
                      json=payload, headers=_auth_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def query_status(checkout_request_id: str) -> dict:
    """Fallback — ask Daraja what happened to a push when the callback is late."""
    base = "https://sandbox.safaricom.co.ke" if settings.MPESA_ENV == "sandbox" \
           else "https://api.safaricom.co.ke"
    password, ts = _password()
    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": ts,
        "CheckoutRequestID": checkout_request_id,
    }
    r = requests.post(f"{base}/mpesa/stkpushquery/v1/query",
                      json=payload, headers=_auth_headers(), timeout=15)
    r.raise_for_status()
    return r.json()