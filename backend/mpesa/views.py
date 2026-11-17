# backend/mpesa/views.py
from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from orders.models import Order
from .models import MpesaTransaction
from .daraja import stk_push

from django.utils import timezone
from datetime import timedelta
from .daraja import query_status

import logging
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("0"):
        p = "254" + p[1:]
    elif p.startswith("+"):
        p = p[1:]
    elif p.startswith("7") or p.startswith("1"):
        p = "254" + p
    return p


@api_view(["POST"])
@permission_classes([AllowAny])
def initiate_payment(request, order_id):
    """
    Body: { phone, amount?, purpose? }
    If amount omitted, uses order.total. purpose defaults to 'order'.
    """
    order = get_object_or_404(Order, id=order_id)
    if order.status not in (Order.Status.PENDING, Order.Status.AWAITING_DEPOSIT,
                            Order.Status.AWAITING_BALANCE):
        return Response({"detail": "Order isn't awaiting payment."},
                        status=status.HTTP_400_BAD_REQUEST)

    phone = normalize_phone(request.data.get("phone") or order.phone)
    purpose = request.data.get("purpose", "order")
    amount = Decimal(str(request.data.get("amount") or order.total))

    daraja_resp = stk_push(
        phone=phone,
        amount=amount,
        account_ref=f"ORDER{order.id}",
        description=f"Smiles Culture order #{order.id}",
    )

    if daraja_resp.get("ResponseCode") != "0":
        return Response(
            {"detail": "Failed to send STK push.",
             "safaricom": daraja_resp.get("errorMessage") or daraja_resp},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    txn = MpesaTransaction.objects.create(
        order=order,
        checkout_request_id=daraja_resp["CheckoutRequestID"],
        merchant_request_id=daraja_resp.get("MerchantRequestID", ""),
        phone=phone,
        amount=amount,
        purpose=purpose,
        status=MpesaTransaction.Status.INITIATED,
    )

    # Return only what the frontend needs to poll — never the password.
    return Response({
        "transaction_id": str(txn.id),
        "checkout_request_id": txn.checkout_request_id,
        "status": txn.status,
        "message": "STK push sent. Enter your PIN on your phone.",
    }, status=status.HTTP_202_ACCEPTED)


@api_view(["POST"])
@permission_classes([AllowAny])   # Safaricom can't authenticate — verify by CheckoutRequestID
def mpesa_callback(request):
    """
    Daraja POSTs here when the STK push resolves.
    We MUST respond 200 quickly, then do work.
    """
    body = request.data
    logger.info("MPesa callback: %s", body)

    stk = body.get("Body", {}).get("stkCallback", {})
    checkout_request_id = stk.get("CheckoutRequestID")
    result_code = stk.get("ResultCode")
    result_desc = stk.get("ResultDesc", "")

    if not checkout_request_id:
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    try:
        txn = MpesaTransaction.objects.select_related("order").get(
            checkout_request_id=checkout_request_id
        )
    except MpesaTransaction.DoesNotExist:
        logger.warning("Callback for unknown CheckoutRequestID: %s", checkout_request_id)
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    # ── Idempotency: ignore duplicate callbacks ─────────────────────
    if txn.status != MpesaTransaction.Status.INITIATED:
        logger.info("Duplicate callback for %s — ignoring", checkout_request_id)
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    with transaction.atomic():
        txn.result_code = result_code
        txn.result_desc = result_desc
        txn.raw_callback = body

        if result_code == 0:
            items = stk.get("CallbackMetadata", {}).get("Item", [])
            metadata = {i["Name"]: i.get("Value") for i in items}
            txn.mpesa_receipt = metadata.get("MpesaReceiptNumber", "")
            txn.status = MpesaTransaction.Status.SUCCESS
            txn.save()
            _on_payment_success(txn)
        elif result_code in (1032,):
            txn.status = MpesaTransaction.Status.FAILED
            txn.save()
            _on_payment_failed(txn, "cancelled")
        elif result_code in (1037,):
            txn.status = MpesaTransaction.Status.TIMEOUT
            txn.save()
            _on_payment_failed(txn, "timeout")
        else:
            txn.status = MpesaTransaction.Status.FAILED
            txn.save()
            _on_payment_failed(txn, result_desc or "failed")

    # Safaricom REQUIRES this exact shape of response
    return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


@api_view(["GET"])
@permission_classes([AllowAny])
def payment_status(request, checkout_request_id):
    """
    Frontend polls this every 3s for up to 60s after STK push.
    Returns the resolved status — never "initiated" forever.
    """
    try:
        txn = MpesaTransaction.objects.get(checkout_request_id=checkout_request_id)
    except MpesaTransaction.DoesNotExist:
        return Response({"status": "unknown"}, status=404)

    # Fallback: if still initiated and >45s elapsed, ask Daraja directly
   

    if txn.status == MpesaTransaction.Status.INITIATED:
        if timezone.now() - txn.created_at > timedelta(seconds=45):
            try:
                q = query_status(txn.checkout_request_id)
                if q.get("ResultCode") == "0":
                    # Callback is late — treat Daraja's answer as authoritative
                    txn.status = MpesaTransaction.Status.SUCCESS
                    txn.result_code = 0
                    txn.result_desc = "Confirmed via status query"
                    txn.save()
                    from .services import _on_payment_success
                    _on_payment_success(txn)
            except Exception:
                pass  # let the poll continue; frontend will time out

    return Response({
        "status": txn.status,
        "result_code": txn.result_code,
        "result_desc": txn.result_desc,
        "mpesa_receipt": txn.mpesa_receipt,
        "order_id": txn.order_id,
        "order_status": txn.order.status,
    })