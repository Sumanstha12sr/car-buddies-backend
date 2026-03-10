from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.customer_register, name='customer_register'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('login/customer/', views.customer_login, name='customer_login'),
    path('login/staff/', views.staff_login, name='staff_login'),
]