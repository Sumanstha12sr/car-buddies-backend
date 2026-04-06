from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.customer_register, name='customer_register'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('login/customer/', views.customer_login, name='customer_login'),
    path('login/staff/', views.staff_login, name='staff_login'),
    path('save-fcm-token/', views.save_fcm_token, name='save-fcm-token'),
    path('notifications/', views.get_notifications, name='notifications'),
    path('notifications/mark-read/', views.mark_all_notifications_read, name='mark-notifications-read'),
    path('notifications/clear/', views.clear_all_notifications, name='clear-notifications'),
]