from django.db import models
from django.contrib.auth.models import User


class CartItem(models.Model):
    product = models.ForeignKey("store.Product", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING             = "pending",             "Pending payment"
        PAID                = "paid",                "Paid"
        AWAITING_TIMEFRAME  = "awaiting_timeframe",  "Awaiting timeframe (owner)"
        AWAITING_DEPOSIT    = "awaiting_deposit",    "Awaiting deposit (customer)"
        IN_PRODUCTION       = "in_production",       "In production"
        AWAITING_BALANCE    = "awaiting_balance",    "Awaiting balance (customer)"
        SHIPPED             = "shipped",             "Shipped"
        DELIVERED           = "delivered",           "Delivered"
        CANCELLED           = "cancelled",           "Cancelled"
        REFUNDED            = "refunded",            "Refunded"

    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="orders")
    name     = models.CharField(max_length=200, blank=True, default="")
    area     = models.CharField(max_length=200, blank=True, default="")
    phone    = models.CharField(max_length=20)
    email    = models.EmailField(blank=True, default="")
    total    = models.DecimalField(max_digits=12, decimal_places=2)
    status   = models.CharField(max_length=25, choices=Status.choices, default=Status.PENDING)

    # Made-to-order fields
    has_out_of_stock       = models.BooleanField(default=False)
    estimated_days         = models.PositiveIntegerField(null=True, blank=True)
    production_start_date  = models.DateField(null=True, blank=True)
    target_completion_date = models.DateField(null=True, blank=True)
    owner_note_to_customer = models.TextField(blank=True)

    # Deposit / balance fields
    deposit_percentage = models.PositiveSmallIntegerField(default=50)
    deposit_amount     = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deposit_paid_at    = models.DateTimeField(null=True, blank=True)
    balance_amount     = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    balance_paid_at    = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} — {self.phone} ({self.get_status_display()})"


class OrderItem(models.Model):
    order      = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product    = models.ForeignKey("store.Product", on_delete=models.PROTECT)
    quantity   = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    was_out_of_stock_at_purchase = models.BooleanField(default=False)

    @property
    def line_total(self):
        return self.unit_price * self.quantity