from django.db import models
from django.conf import settings

class Product(models.Model):
    CATEGORY_CHOICES = [
        ('women', 'Women'),
        ('men', 'Men'),
        ('unisex', 'Unisex'),
    ]

  
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='unisex')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class CartItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
class Order(models.Model):
    name = models.CharField(max_length=200, blank=True, default="")  
    area = models.CharField(max_length=200, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    mpesa_checkout_request_id = models.CharField(max_length=255, blank=True, null=True)

class Payment(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='payments',
        null=True, blank=True   # ✅ allow nulls, no weird default
    )
    mpesa_receipt_no = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=50, default='pending')
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    raw_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
