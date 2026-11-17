import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from orders.models import Order
from .models import MpesaTransaction
from .daraja import stk_push, query_status
from .services import on_payment_success, on_payment_failed

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def initiate_payment(request, order_id):
    """
    Fires STK push. Returns 202 with checkout_request_id — NOT 'success'.
    The frontend MUST poll /status/<checkout_id>/ for the real result.
    """
    order = get_object_or_404(Order, id=order_id)

    allowed = {
        Order.Status.PENDING,
        Order.Status.AWAITING_DEPOSIT,
        Order.Status.AWAITING_BALANCE,
    }
    if order.status not in allowed:
        return Response(
            {"detail": f"Order {order.id} isn't awaiting payment (status={order.status})."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    phone = request.data.get("phone") or order.phone
    purpose = request.data.get("purpose", "order")

    # Determine amount by purpose
    if purpose == "deposit":
        amount = order.deposit_amount
    elif purpose == "balance":
        amount = order.balance_amount
    else:
        amount = order.total
        # If customer already paid a deposit, remaining is total - deposit
        if order.deposit_amount and order.deposit_paid_at:
            amount = order.total - order.deposit_amount

    if not amount or amount <= 0:
        return Response({"detail": "Nothing to pay."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        daraja = stk_push(
            phone=phone,
            amount=int(Decimal(amount)),
            account_ref=f"ORDER{order.id}",
            description=f"Smiles Culture order #{order.id} ({purpose})",
        )
    except Exception as e:
        logger.exception("STK push failed for order %s", order.id)
        return Response(
            {"detail": "Failed to reach MPesa. Try again in a moment.", "error": str(e)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if daraja.get("ResponseCode") != "0":
        return Response(
            {"detail": "MPesa rejected the request.",
             "safaricom": daraja.get("errorMessage") or daraja},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    txn = MpesaTransaction.objects.create(
        order=order,
        checkout_request_id=daraja["CheckoutRequestID"],
        merchant_request_id=daraja.get("MerchantRequestID", ""),
        phone=phone,
        amount=Decimal(amount),
        purpose=purpose,
        status=MpesaTransaction.Status.INITIATED,
    )

    return Response(
        {
            "transaction_id": str(txn.id),
            "checkout_request_id": txn.checkout_request_id,
            "status": txn.status,
            "message": "STK push sent. Enter your PIN on your phone.",
        },
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def mpesa_callback(request):
    """Daraja POSTs here when the STK push resolves. We must respond 200 fast."""
    body = request.data
    logger.info("MPesa callback: %s", body)

    stk = body.get("Body", {}).get("stkCallback", {})
    checkout_id = stk.get("CheckoutRequestID")
    result_code = stk.get("ResultCode")
    result_desc = stk.get("ResultDesc", "")

    if not checkout_id:
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    try:
        txn = MpesaTransaction.objects.select_related("order").get(
            checkout_request_id=checkout_id
        )
    except MpesaTransaction.DoesNotExist:
        logger.warning("Callback for unknown CheckoutRequestID: %s", checkout_id)
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    # Idempotency — ignore duplicate callbacks
    if txn.status != MpesaTransaction.Status.INITIATED:
        logger.info("Duplicate callback for %s — ignoring", checkout_id)
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

    with transaction.atomic():
        txn.result_code = result_code
        txn.result_desc = result_desc
        txn.raw_callback = body

        if result_code == 0:
            metadata = {
                i["Name"]: i.get("Value")
                for i in stk.get("CallbackMetadata", {}).get("Item", [])
            }
            txn.mpesa_receipt = metadata.get("MpesaReceiptNumber", "") or ""
            txn.status = MpesaTransaction.Status.SUCCESS
            txn.save()
            on_payment_success(txn)
        elif result_code == 1032:
            txn.status = MpesaTransaction.Status.FAILED
            txn.save()
            on_payment_failed(txn, "cancelled")
        elif result_code == 1037:
            txn.status = MpesaTransaction.Status.TIMEOUT
            txn.save()
            on_payment_failed(txn, "timeout")
        else:
            txn.status = MpesaTransaction.Status.FAILED
            txn.save()
            on_payment_failed(txn, result_desc or "failed")

    return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


@api_view(["GET"])
@permission_classes([AllowAny])
def payment_status(request, checkout_request_id):
    """
    Frontend polls this every 3s after STK push. Returns the resolved status.
    If still 'initiated' after 45s, we re-query Daraja as a fallback.
    """
    try:
        txn = MpesaTransaction.objects.select_related("order").get(
            checkout_request_id=checkout_request_id
        )
    except MpesaTransaction.DoesNotExist:
        return Response({"status": "unknown"}, status=status.HTTP_404_NOT_FOUND)

    if txn.status == MpesaTransaction.Status.INITIATED:
        elapsed = timezone.now() - txn.created_at
        if elapsed > timedelta(seconds=45):
            try:
                q = query_status(txn.checkout_request_id)
                if str(q.get("ResultCode")) == "0":
                    txn.status = MpesaTransaction.Status.SUCCESS
                    txn.result_code = 0
                    txn.result_desc = "Confirmed via status query"
                    txn.save()
                    on_payment_success(txn)
            except Exception:
                pass  # keep polling; frontend will time out

    return Response({
        "status": txn.status,
        "result_code": txn.result_code,
        "result_desc": txn.result_desc,
        "mpesa_receipt": txn.mpesa_receipt,
        "purpose": txn.purpose,
        "order_id": txn.order_id,
        "order_status": txn.order.status,
    })