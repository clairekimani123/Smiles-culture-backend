# backend/mpesa/models.py
import uuid
from django.db import models


class MpesaTransaction(models.Model):
    class Status(models.TextChoices):
        INITIATED  = "initiated",  "STK push sent"
        SUCCESS    = "success",    "Paid"
        FAILED     = "failed",     "Failed / cancelled"
        TIMEOUT    = "timeout",    "No response"
        UNKNOWN    = "unknown",    "Unknown (callback not received)"

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order             = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="mpesa_transactions")
    checkout_request_id = models.CharField(max_length=100, unique=True, db_index=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    phone             = models.CharField(max_length=20)
    amount            = models.DecimalField(max_digits=10, decimal_places=2)
    purpose           = models.CharField(max_length=20, choices=[
        ("order", "Order payment"),
        ("deposit", "Deposit for made-to-order"),
        ("balance", "Balance before shipping"),
    ], default="order")
    status            = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED)
    result_code       = models.IntegerField(null=True, blank=True)
    result_desc       = models.TextField(blank=True)
    mpesa_receipt     = models.CharField(max_length=50, blank=True)  # e.g. QGR7XYZ123
    raw_callback      = models.JSONField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["order", "status"]),
        ]