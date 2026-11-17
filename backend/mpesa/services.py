import logging
from orders.services import (
    handle_paid_order,
    handle_deposit_paid,
    handle_balance_paid,
)

logger = logging.getLogger(__name__)


def on_payment_success(txn):
    """Called from the callback when result_code == 0."""
    order = txn.order
    if txn.purpose == "deposit":
        handle_deposit_paid(order, txn.amount)
    elif txn.purpose == "balance":
        handle_balance_paid(order, txn.amount)
    else:
        handle_paid_order(order)


def on_payment_failed(txn, reason: str):
    """Called when result_code != 0. Order status is untouched — user can retry."""
    logger.info(
        "Payment failed for order %s (%s): %s",
        txn.order_id, txn.checkout_request_id, reason,
    )