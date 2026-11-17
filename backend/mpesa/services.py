# backend/mpesa/services.py
from decimal import Decimal
from django.db import transaction
from orders.models import Order
from orders.services import (
    handle_paid_order,                 # ← the function from Part 2.8 below
    handle_deposit_paid,
    handle_balance_paid,
)


def _on_payment_success(txn):
    order = txn.order
    if txn.purpose == "deposit":
        handle_deposit_paid(order, txn.amount)
    elif txn.purpose == "balance":
        handle_balance_paid(order, txn.amount)
    else:
        handle_paid_order(order)


def _on_payment_failed(txn, reason):
    # Order stays in whatever "awaiting payment" state it was — frontend shows error,
    # user can retry. Don't mutate the order; the transaction carries the failure.
    pass