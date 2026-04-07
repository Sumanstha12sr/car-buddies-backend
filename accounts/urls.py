from django.urls import path
from . import views

urlpatterns = [

    # ==================== AUTH ====================
    path('register/',              views.customer_register,          name='customer_register'),
    path('login/customer/',        views.customer_login,             name='customer_login'),
    path('login/staff/',           views.staff_login,                name='staff_login'),

    # ==================== EMAIL VERIFICATION ====================
    path('verify-email/<str:token>/',           views.verify_email,              name='verify_email'),
    path('resend-verification/',                views.resend_verification_email, name='resend_verification'),

    # ==================== PASSWORD RESET ====================
    path('forgot-password/',                            views.forgot_password,           name='forgot_password'),
    path('password-reset-redirect/<str:token>/',        views.password_reset_redirect,   name='password_reset_redirect'),
    path('reset-password/',                             views.reset_password,            name='reset_password'),

    # ==================== CHANGE PASSWORD (authenticated) ====================
    path('change-password/',       views.change_password,            name='change_password'),

    # ==================== FCM + NOTIFICATIONS ====================
    path('save-fcm-token/',                 views.save_fcm_token,               name='save_fcm_token'),
    path('notifications/',                  views.get_notifications,            name='get_notifications'),
    path('notifications/mark-read/',        views.mark_all_notifications_read,  name='mark_all_read'),
    path('notifications/clear/',            views.clear_all_notifications,      name='clear_notifications'),
]