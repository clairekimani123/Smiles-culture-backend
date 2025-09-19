from django.conf import settings
from django.urls import reverse
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Product, CartItem, Order, Payment
from .serializers import ProductSerializer, CartItemSerializer, CreatePaymentSerializer
from .mpesa import lipa_stk_push

# Products
class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

# Product detail
class ProductRetrieveView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

# Cart list/create for logged in user
class CartItemListCreateView(generics.ListCreateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class CartItemDeleteView(generics.DestroyAPIView):
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user)

# Payment: create order and call lipa_stk_push
class CreatePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        phone = serializer.validated_data['phone']
        items = serializer.validated_data.get('items', [])

        order = Order.objects.create(user=request.user, amount=amount, phone=phone)

        callback_url = settings.MPESA_CALLBACK_URL  # expects fully qualified URL

        try:
            resp = lipa_stk_push(phone_number=phone, amount=str(amount), account_reference=f"Order{order.id}", transaction_desc=f"Order {order.id}", callback_url=callback_url)
        except Exception as e:
            order.delete()
            return Response({'success': False, 'message': str(e)}, status=400)

        checkout_id = resp.get('CheckoutRequestID') or resp.get('ResponseCode')
        order.mpesa_checkout_request_id = checkout_id
        order.save()
        Payment.objects.create(order=order, status='pending', raw_response=resp)
        return Response({'success': True, 'data': resp})

# M-Pesa callback
class MpesaCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        try:
            body = data.get('Body') or data
            callback = body.get('stkCallback') or body
            checkout_request_id = callback.get('CheckoutRequestID')
            result_code = callback.get('ResultCode')
            order = Order.objects.filter(mpesa_checkout_request_id=checkout_request_id).first()
            if order:
                payment = Payment.objects.create(order=order, raw_response=data, status='pending')
                if int(result_code) == 0:
                    # parse metadata
                    metadata = callback.get('CallbackMetadata', {}).get('Item', [])
                    receipt = next((i.get('Value') for i in metadata if i.get('Name') == 'MpesaReceiptNumber'), None)
                    payment.status = 'success'
                    payment.mpesa_receipt_no = receipt
                    payment.amount = order.amount
                    payment.save()
                    order.completed = True
                    order.save()
                else:
                    payment.status = 'failed'
                    payment.save()
        except Exception as e:
            Payment.objects.create(order=None, raw_response=data, status='error')
            return Response({'error': str(e)}, status=400)
        return Response({'result':'received'}, status=200)
