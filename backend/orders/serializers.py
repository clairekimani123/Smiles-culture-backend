from rest_framework import serializers
from .models import Order, OrderItem, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product_name  = serializers.CharField(source="product.name", read_only=True)
    product_price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2, read_only=True,
    )

    class Meta:
        model = CartItem
        fields = ("id", "product", "product_name", "product_price", "quantity")


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id", "product", "product_name",
            "quantity", "unit_price", "line_total",
            "was_out_of_stock_at_purchase",
        )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", "name", "phone", "email", "area", "total", "status",
            "has_out_of_stock", "estimated_days", "target_completion_date",
            "owner_note_to_customer",
            "deposit_amount", "deposit_paid_at",
            "balance_amount", "balance_paid_at",
            "items", "created_at", "updated_at",
        )
        read_only_fields = fields   # order creation is via the create endpoint below


class OrderCreateSerializer(serializers.Serializer):
    """Input for POST /api/orders/ — creates the order + items in one call."""
    name    = serializers.CharField(required=False, allow_blank=True, default="")
    phone   = serializers.CharField()
    email   = serializers.EmailField(required=False, allow_blank=True, default="")
    area    = serializers.CharField(required=False, allow_blank=True, default="")
    total   = serializers.DecimalField(max_digits=12, decimal_places=2)
    items   = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    # items: [{"product": 1, "quantity": 2, "unit_price": "1500.00"}, ...]