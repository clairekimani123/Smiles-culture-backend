from django.urls import path
from .views import (
    ProductListCreateView, CartItemListCreateView,
    OrderListCreateView, CheckoutView, MpesaCallbackView
)

urlpatterns = [
    path("products/", ProductListCreateView.as_view(), name="products"),
    path("cart/", CartItemListCreateView.as_view(), name="cart"),
    path("orders/", OrderListCreateView.as_view(), name="orders"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("mpesa/callback/", MpesaCallbackView.as_view(), name="mpesa_callback"),
]
