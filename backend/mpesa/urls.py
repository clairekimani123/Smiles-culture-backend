# backend/mpesa/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("initiate/<int:order_id>/", views.initiate_payment, name="mpesa-initiate"),
    path("callback/",                 views.mpesa_callback,   name="mpesa-callback"),
    path("status/<str:checkout_request_id>/", views.payment_status, name="mpesa-status"),
]