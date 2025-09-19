from django.urls import path
from .views import ProductListCreateView, ProductRetrieveView, CartItemListCreateView, CartItemDeleteView, CreatePaymentView, MpesaCallbackView

urlpatterns = [
    path('products/', ProductListCreateView.as_view(), name='product-list'),
    path('products/<int:pk>/', ProductRetrieveView.as_view(), name='product-detail'),
    path('cart-items/', CartItemListCreateView.as_view(), name='cart-items'),
    path('cart-items/<int:pk>/', CartItemDeleteView.as_view(), name='cart-item-delete'),
    path('create-payment/', CreatePaymentView.as_view(), name='create-payment'),
    path('mpesa-callback/', MpesaCallbackView.as_view(), name='mpesa-callback'),
]
