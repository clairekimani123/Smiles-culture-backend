from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order, CartItem
from .serializers import (
    OrderSerializer, OrderCreateSerializer, CartItemSerializer,
)


class CartItemListCreateView(generics.ListCreateAPIView):
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
    permission_classes = [permissions.AllowAny]


class OrderListCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = Order.objects.prefetch_related("items").order_by("-created_at")
        return Response(OrderSerializer(qs, many=True).data)

    def post(self, request):
        """Creates an order + items. Does NOT fire STK push."""
        s = OrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        order = Order.objects.create(
            name=data.get("name", ""),
            phone=data["phone"],
            email=data.get("email", ""),
            area=data.get("area", ""),
            total=data["total"],
            status=Order.Status.PENDING,
        )

        for row in data["items"]:
            try:
                order.items.create(
                    product_id=row["product"],
                    quantity=row["quantity"],
                    unit_price=row["unit_price"],
                )
            except KeyError as e:
                order.delete()
                return Response(
                    {"detail": f"Missing field in items: {e}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(generics.RetrieveAPIView):
    queryset = Order.objects.prefetch_related("items")
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]