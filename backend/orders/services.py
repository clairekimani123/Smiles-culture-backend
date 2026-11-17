import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Order

logger = logging.getLogger(__name__)


def _send(subject, message, to):
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to] if isinstance(to, str) else to,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send email '%s' to %s", subject, to)


# ═══════════════════════════════════════════════════════════════════
# Payment confirmed — check stock, branch into the right flow
# ═══════════════════════════════════════════════════════════════════

@transaction.atomic
def handle_paid_order(order: Order) -> None:
    out_of_stock_items = []

    for item in order.items.select_related("product"):
        product = item.product
        # Lock the product row to avoid races when two people buy last item
        product = type(product).objects.select_for_update().get(pk=product.pk)

        if product.stock < item.quantity:
            item.was_out_of_stock_at_purchase = True
            item.save(update_fields=["was_out_of_stock_at_purchase"])
            out_of_stock_items.append(item)
        else:
            product.stock -= item.quantity
            product.save(update_fields=["stock"])

    if out_of_stock_items:
        order.has_out_of_stock = True
        order.status = Order.Status.AWAITING_TIMEFRAME
        order.save()
        _notify_owner_needs_timeframe(order, out_of_stock_items)
        _notify_customer_pending_timeframe(order)
    else:
        order.status = Order.Status.PAID
        order.save()
        _notify_owner_new_order(order)
        _notify_customer_order_confirmed(order)


# ═══════════════════════════════════════════════════════════════════
# Owner sets timeframe → deposit requested
# ═══════════════════════════════════════════════════════════════════

def set_production_timeframe(order: Order, days: int, note: str = "") -> None:
    if order.status != Order.Status.AWAITING_TIMEFRAME:
        raise ValueError("This order isn't awaiting a timeframe.")

    today = timezone.now().date()
    order.estimated_days = days
    order.production_start_date = today
    order.target_completion_date = today + timedelta(days=days)
    order.owner_note_to_customer = note

    oos_total = sum(
        (i.line_total for i in order.items.filter(was_out_of_stock_at_purchase=True)),
        Decimal("0"),
    )
    deposit = (oos_total * Decimal(order.deposit_percentage) / Decimal(100)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    order.deposit_amount = deposit
    order.balance_amount = (oos_total - deposit).quantize(Decimal("1"))
    order.status = Order.Status.AWAITING_DEPOSIT
    order.save()

    _notify_customer_timeframe_and_deposit(order)


# ═══════════════════════════════════════════════════════════════════
# Deposit paid → start production
# ═══════════════════════════════════════════════════════════════════

def handle_deposit_paid(order: Order, amount: Decimal) -> None:
    if order.status != Order.Status.AWAITING_DEPOSIT:
        logger.warning("Deposit paid on order %s but status=%s", order.id, order.status)
        return
    if order.deposit_amount and amount < order.deposit_amount:
        _notify_owner_underpaid(order, amount)
        return

    order.deposit_paid_at = timezone.now()
    order.status = Order.Status.IN_PRODUCTION
    order.save()
    _notify_owner_deposit_paid(order)
    _notify_customer_in_production(order)


# ═══════════════════════════════════════════════════════════════════
# Owner marks finished → balance requested
# ═══════════════════════════════════════════════════════════════════

def mark_ready_for_balance(order: Order) -> None:
    if order.status != Order.Status.IN_PRODUCTION:
        raise ValueError("Order isn't in production.")
    order.status = Order.Status.AWAITING_BALANCE
    order.save()
    _notify_customer_balance_due(order)


# ═══════════════════════════════════════════════════════════════════
# Balance paid → ship
# ═══════════════════════════════════════════════════════════════════

def handle_balance_paid(order: Order, amount: Decimal) -> None:
    if order.status != Order.Status.AWAITING_BALANCE:
        logger.warning("Balance paid on order %s but status=%s", order.id, order.status)
        return
    if order.balance_amount and amount < order.balance_amount:
        _notify_owner_underpaid(order, amount)
        return

    order.balance_paid_at = timezone.now()
    order.status = Order.Status.SHIPPED
    order.save()
    _notify_owner_balance_paid(order)
    _notify_customer_shipped(order)


# ═══════════════════════════════════════════════════════════════════
# Emails
# ═══════════════════════════════════════════════════════════════════

def _owner_email():
    return getattr(settings, "OWNER_EMAIL", settings.DEFAULT_FROM_EMAIL)


def _notify_owner_needs_timeframe(order, items):
    lines = "\n".join(
        f"  - {i.product.name} x{i.quantity}" for i in items
    )
    _send(
        f"[ACTION] Order #{order.id} — set production timeframe",
        f"Order #{order.id} from {order.phone} ({order.email or 'no email'}) "
        f"has out-of-stock items:\n\n{lines}\n\n"
        f"Admin: {settings.FRONTEND_URL}/admin/orders/order/{order.id}/change/",
        _owner_email(),
    )


def _notify_customer_pending_timeframe(order):
    if not order.email:
        return
    _send(
        f"Order #{order.id} received — designer will confirm shortly",
        "Thanks for your order! Some items are made to order. "
        "Our designer will email you a timeframe and deposit request shortly.",
        order.email,
    )


def _notify_customer_timeframe_and_deposit(order):
    if not order.email:
        return
    note = f"\n\nNote from our designer:\n{order.owner_note_to_customer}" \
        if order.owner_note_to_customer else ""
    _send(
        f"Order #{order.id}: timeframe + deposit required",
        f"Your made-to-order piece is scheduled.\n\n"
        f"Estimated production: {order.estimated_days} days\n"
        f"Target completion: {order.target_completion_date:%d %b %Y}\n\n"
        f"Deposit due ({order.deposit_percentage}%): KES {order.deposit_amount:,.0f}\n"
        f"Balance on completion: KES {order.balance_amount:,.0f}\n\n"
        f"Pay deposit: {settings.FRONTEND_URL}/orders/{order.id}/pay?purpose=deposit"
        f"{note}",
        order.email,
    )


def _notify_owner_deposit_paid(order):
    _send(
        f"[DEPOSIT PAID] Order #{order.id}",
        f"Deposit KES {order.deposit_amount:,.0f} received. Start production.",
        _owner_email(),
    )


def _notify_customer_in_production(order):
    if not order.email:
        return
    _send(
        f"Order #{order.id} is in production ✂️",
        f"Deposit received! Target completion: "
        f"{order.target_completion_date:%d %b %Y}.",
        order.email,
    )


def _notify_customer_balance_due(order):
    if not order.email:
        return
    _send(
        f"Order #{order.id} is ready — balance due",
        f"Your piece is finished. Pay KES {order.balance_amount:,.0f} to ship.\n\n"
        f"Pay balance: {settings.FRONTEND_URL}/orders/{order.id}/pay?purpose=balance",
        order.email,
    )


def _notify_owner_balance_paid(order):
    _send(
        f"[BALANCE PAID] Order #{order.id} — ready to ship",
        f"Balance KES {order.balance_amount:,.0f} received. Ship order #{order.id}.",
        _owner_email(),
    )


def _notify_customer_shipped(order):
    if not order.email:
        return
    _send(
        f"Order #{order.id} has shipped 🚚",
        "Your order is on its way!",
        order.email,
    )


def _notify_owner_new_order(order):
    _send(
        f"[NEW ORDER] #{order.id} — {order.phone}",
        f"All items in stock. Total KES {order.total:,.0f}.",
        _owner_email(),
    )


def _notify_customer_order_confirmed(order):
    if not order.email:
        return
    _send(
        f"Order #{order.id} confirmed",
        "Thanks! We'll notify you when it ships.",
        order.email,
    )


def _notify_owner_underpaid(order, amount):
    _send(
        f"[UNDERPAID] Order #{order.id}",
        f"Received KES {amount:,.0f}. Expected "
        f"{order.deposit_amount or order.balance_amount:,.0f}.",
        _owner_email(),
    )