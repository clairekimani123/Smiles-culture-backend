from rest_framework import serializers
from .models import Product, CartItem, Order, Payment


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class CartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = "__all__"


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = "__all__"


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class CreatePaymentSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    phone = serializers.CharField(max_length=20)
    area = serializers.CharField(max_length=200, required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    items = serializers.ListField(child=serializers.DictField(), required=False)
