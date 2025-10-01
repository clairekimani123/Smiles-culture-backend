from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Product, CartItem, Order, Payment
from .serializers import (
    ProductSerializer, CartItemSerializer, OrderSerializer,
    PaymentSerializer, CreatePaymentSerializer
)
from .mpesa import lipa_stk_push


# ---- Products ----
class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]


# ---- Cart ----
class CartItemListCreateView(generics.ListCreateAPIView):
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
    permission_classes = [permissions.AllowAny]


# ---- Orders ----
class OrderListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]


# ---- Payments / Checkout ----
class CheckoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data.get("name", "Guest")
        phone = serializer.validated_data["phone"]
        area = serializer.validated_data.get("area", "")
        amount = serializer.validated_data["amount"]

        # Create order
        order = Order.objects.create(name=name, phone=phone, area=area, amount=amount)

        try:
            resp = lipa_stk_push(
                phone_number=phone,
                amount=str(amount),
                account_reference=f"Order{order.id}",
                transaction_desc=f"Order {order.id}"
            )
        except Exception as e:
            order.delete()
            return Response({"success": False, "message": str(e)}, status=400)

        order.mpesa_checkout_request_id = resp.get("CheckoutRequestID")
        order.save()

        Payment.objects.create(order=order, status="pending", raw_response=resp)
        return Response({"success": True, "order_id": order.id, "data": resp})


class MpesaCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        try:
            body = data.get("Body", {})
            callback = body.get("stkCallback", {})
            checkout_id = callback.get("CheckoutRequestID")
            result_code = callback.get("ResultCode")

            order = Order.objects.filter(mpesa_checkout_request_id=checkout_id).first()
            if not order:
                return Response({"error": "Order not found"}, status=404)

            payment = order.payments.last()
            if not payment:
                return Response({"error": "Payment not found"}, status=404)

            if int(result_code) == 0:
                metadata = callback.get("CallbackMetadata", {}).get("Item", [])
                receipt = next((i.get("Value") for i in metadata if i.get("Name") == "MpesaReceiptNumber"), None)
                payment.status = "success"
                payment.mpesa_receipt_no = receipt
                payment.amount = order.amount
                order.completed = True
                order.save()
            else:
                payment.status = "failed"

            payment.raw_response = data
            payment.save()

        except Exception as e:
            return Response({"error": str(e)}, status=400)

        return Response({"result": "received"}, status=200)
