import uuid
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect as django_redirect
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import User, Customer, Staff, PasswordResetToken
from .serializers import (
    CustomerRegistrationSerializer,
    CustomerSerializer,
    StaffSerializer,
    LoginSerializer,
)


# ==================== HELPERS ====================

def _send_email(subject, html_body, to_email):
    """Send HTML email. Silently logs on failure — never crashes a view."""
    try:
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            html_message=html_body,
            fail_silently=False,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Email send error to {to_email}: {e}')


def _verification_email_html(full_name, verify_url):
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px;
                border:1px solid #e0e0e0;border-radius:12px;">
      <h2 style="color:#2e7d32;">Welcome to Car Buddies 🚗⚡</h2>
      <p>Hi <strong>{full_name}</strong>,</p>
      <p>Thank you for signing up! Please verify your email address to activate your account.</p>
      <div style="text-align:center;margin:32px 0;">
        <a href="{verify_url}"
           style="background:#2e7d32;color:#fff;padding:14px 32px;border-radius:8px;
                  text-decoration:none;font-weight:bold;font-size:16px;">
          Verify Email
        </a>
      </div>
      <p style="color:#666;font-size:13px;">
        This link expires in <strong>24 hours</strong>.<br>
        If you did not create an account, you can safely ignore this email.
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
      <p style="color:#aaa;font-size:12px;text-align:center;">Car Buddies — EV Services Nepal</p>
    </div>
    """


def _password_reset_email_html(full_name, reset_url):
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px;
                border:1px solid #e0e0e0;border-radius:12px;">
      <h2 style="color:#1565c0;">Password Reset Request 🔐</h2>
      <p>Hi <strong>{full_name}</strong>,</p>
      <p>We received a request to reset your Car Buddies password.
         Tap the button below to create a new password.</p>
      <div style="text-align:center;margin:32px 0;">
        <a href="{reset_url}"
           style="background:#1565c0;color:#fff;padding:14px 32px;border-radius:8px;
                  text-decoration:none;font-weight:bold;font-size:16px;">
          Reset Password
        </a>
      </div>
      <p style="color:#666;font-size:13px;">
        This link expires in <strong>1 hour</strong> and can only be used once.<br>
        If you did not request a password reset, please ignore this email.
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
      <p style="color:#aaa;font-size:12px;text-align:center;">Car Buddies — EV Services Nepal</p>
    </div>
    """


def _html_page(title, icon, heading, message, color='#2e7d32'):
    """Simple HTML page shown in browser after verify/reset actions."""
    return HttpResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{title} — Car Buddies</title>
      <style>
        body {{ font-family:Arial,sans-serif; background:#f5f5f5;
               display:flex; align-items:center; justify-content:center;
               min-height:100vh; margin:0; }}
        .card {{ background:#fff; border-radius:16px; padding:40px 32px;
                 max-width:400px; text-align:center; box-shadow:0 4px 16px rgba(0,0,0,.1); }}
        .icon {{ font-size:56px; margin-bottom:16px; }}
        h1 {{ color:{color}; font-size:22px; margin:0 0 12px; }}
        p  {{ color:#555; font-size:15px; line-height:1.6; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="icon">{icon}</div>
        <h1>{heading}</h1>
        <p>{message}</p>
      </div>
    </body>
    </html>
    """)


# ==================== CUSTOMER REGISTRATION ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_register(request):
    """Register customer → is_active=False → send verification email."""
    serializer = CustomerRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()

        # Get the token that was just generated in the serializer
        customer   = Customer.objects.get(user=user)
        token      = customer.email_verification_token
        verify_url = f"{settings.BACKEND_URL}/api/verify-email/{token}/"

        _send_email(
            subject='Verify your Car Buddies account ✅',
            html_body=_verification_email_html(customer.full_name, verify_url),
            to_email=user.email,
        )

        return Response({
            'message': 'Registration successful! Please check your email to verify your account.',
            'email': user.email,
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== EMAIL VERIFICATION ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, token):
    """Customer clicks link in email → activates account → shows success page."""
    try:
        customer = Customer.objects.get(email_verification_token=token)
    except Customer.DoesNotExist:
        return _html_page(
            'Invalid Link', '❌',
            'Invalid or Expired Link',
            'This verification link is invalid or has already been used. '
            'Please register again or request a new verification email.',
            color='#c62828',
        )

    if customer.email_verified_at is not None:
        return _html_page(
            'Already Verified', '✅',
            'Already Verified',
            'Your email has already been verified. You can login to Car Buddies.',
        )

    # Activate user
    customer.user.is_active        = True
    customer.user.save()
    customer.email_verified_at     = timezone.now()
    customer.email_verification_token = None
    customer.save()

    return _html_page(
        'Email Verified', '🎉',
        'Email Verified!',
        'Your Car Buddies account is now active. '
        'Open the app and log in to get started.',
    )


# ==================== RESEND VERIFICATION EMAIL ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_email(request):
    """
    POST /api/resend-verification/
    Body: { "email": "user@example.com" }
    """
    email = request.data.get('email', '').strip()
    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user     = User.objects.get(email=email, user_type='customer')
        customer = Customer.objects.get(user=user)
    except (User.DoesNotExist, Customer.DoesNotExist):
        # Return success anyway to avoid email enumeration
        return Response({'message': 'If that email exists, a verification link has been sent.'})

    if customer.email_verified_at is not None:
        return Response({'error': 'This email is already verified.'}, status=status.HTTP_400_BAD_REQUEST)

    # Generate fresh token
    new_token = str(uuid.uuid4())
    customer.email_verification_token = new_token
    customer.save()

    verify_url = f"{settings.BACKEND_URL}/api/verify-email/{new_token}/"
    _send_email(
        subject='Verify your Car Buddies account ✅',
        html_body=_verification_email_html(customer.full_name, verify_url),
        to_email=email,
    )

    return Response({'message': 'Verification email sent. Please check your inbox.'})


# ==================== CUSTOMER LOGIN ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_login(request):
    """Customer login — returns JWT tokens + customer profile."""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email    = serializer.validated_data['email']
        password = serializer.validated_data['password']

        # Check user exists before authenticate to give specific error
        try:
            user_obj = User.objects.get(email=email, user_type='customer')
        except User.DoesNotExist:
            return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)

        # ── GUARD: unverified email ───────────────────────────────────
        if not user_obj.is_active:
            return Response({
                'error': 'Please verify your email before logging in. Check your inbox.',
                'unverified': True,   # Flutter uses this flag to show Resend button
                'email': email,
            }, status=status.HTTP_401_UNAUTHORIZED)

        user = authenticate(email=email, password=password)
        if user is None:
            return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            customer = Customer.objects.get(user=user)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user_type': 'customer',
            'user': CustomerSerializer(customer).data,
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== STAFF LOGIN ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def staff_login(request):
    """Staff login — returns JWT tokens + staff profile."""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email    = serializer.validated_data['email']
        password = serializer.validated_data['password']

        user = authenticate(email=email, password=password)

        if user is not None:
            if user.user_type != 'staff':
                return Response({'error': 'Invalid credentials for staff login'}, status=status.HTTP_401_UNAUTHORIZED)

            try:
                staff = Staff.objects.get(user=user)
            except Staff.DoesNotExist:
                return Response({'error': 'Staff profile not found'}, status=status.HTTP_404_NOT_FOUND)

            if hasattr(staff, 'mechanic_profile'):
                return Response({'error': 'Mechanics are not allowed to log in to the app.'}, status=status.HTTP_403_FORBIDDEN)

            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user_type': 'staff',
                'user': StaffSerializer(staff).data,
            }, status=status.HTTP_200_OK)

        return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== FORGOT PASSWORD ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """
    POST /api/forgot-password/
    Body: { "email": "user@example.com" }
    Sends a deep-link password reset email.
    """
    email = request.data.get('email', '').strip()
    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    # Always return success to prevent email enumeration
    try:
        user     = User.objects.get(email=email, user_type='customer')
        customer = Customer.objects.get(user=user)
    except (User.DoesNotExist, Customer.DoesNotExist):
        return Response({'message': 'If that email exists, a reset link has been sent.'})

    if not user.is_active:
        return Response({'error': 'Please verify your email first before resetting your password.'}, status=status.HTTP_400_BAD_REQUEST)

    # Invalidate old tokens for this user
    PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)

    # Create new token
    token_obj = PasswordResetToken.objects.create(
        user=user,
        token=str(uuid.uuid4()),
    )

    # Link goes to backend redirect → deep link into Flutter app
    reset_url = f"{settings.BACKEND_URL}/api/password-reset-redirect/{token_obj.token}/"

    _send_email(
        subject='Reset your Car Buddies password 🔐',
        html_body=_password_reset_email_html(customer.full_name, reset_url),
        to_email=email,
    )

    return Response({'message': 'Password reset email sent. Please check your inbox.'})


# ==================== PASSWORD RESET REDIRECT (deep link) ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def password_reset_redirect(request, token):
    """
    GET /api/password-reset-redirect/<token>/
    Opens in browser from email click → validates token →
    redirects to carbuddies://reset-password?token=<token>
    so Flutter app_links opens ResetPasswordScreen.
    """
    try:
        token_obj = PasswordResetToken.objects.get(token=token, is_used=False)
    except PasswordResetToken.DoesNotExist:
        return _html_page(
            'Invalid Link', '❌',
            'Link Expired or Invalid',
            'This password reset link has already been used or has expired. '
            'Please request a new password reset from the Car Buddies app.',
            color='#c62828',
        )

    if token_obj.is_expired():
        return _html_page(
            'Link Expired', '⏰',
            'Link Expired',
            'This password reset link has expired (valid for 1 hour). '
            'Please request a new one from the Car Buddies app.',
            color='#e65100',
        )

    # Redirect to Flutter deep link
    return django_redirect(f'carbuddies://reset-password?token={token}')


# ==================== RESET PASSWORD ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    POST /api/reset-password/
    Body: { "token": "...", "new_password": "...", "confirm_password": "..." }
    """
    token            = request.data.get('token', '').strip()
    new_password     = request.data.get('new_password', '')
    confirm_password = request.data.get('confirm_password', '')

    if not all([token, new_password, confirm_password]):
        return Response({'error': 'All fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

    if new_password != confirm_password:
        return Response({'error': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 8:
        return Response({'error': 'Password must be at least 8 characters.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        token_obj = PasswordResetToken.objects.get(token=token, is_used=False)
    except PasswordResetToken.DoesNotExist:
        return Response({'error': 'Invalid or already used reset link.'}, status=status.HTTP_400_BAD_REQUEST)

    if token_obj.is_expired():
        return Response({'error': 'This reset link has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

    # Set new password
    user = token_obj.user
    user.set_password(new_password)
    user.save()

    # Invalidate token
    token_obj.is_used = True
    token_obj.save()

    return Response({'message': 'Password reset successfully. You can now login with your new password.'})


# ==================== CHANGE PASSWORD ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    POST /api/change-password/
    Body: { "old_password": "...", "new_password": "...", "confirm_password": "..." }
    Requires valid JWT token (authenticated users only).
    """
    old_password     = request.data.get('old_password', '')
    new_password     = request.data.get('new_password', '')
    confirm_password = request.data.get('confirm_password', '')

    if not all([old_password, new_password, confirm_password]):
        return Response({'error': 'All fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

    if not request.user.check_password(old_password):
        return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

    if new_password != confirm_password:
        return Response({'error': 'New passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 8:
        return Response({'error': 'Password must be at least 8 characters.'}, status=status.HTTP_400_BAD_REQUEST)

    if old_password == new_password:
        return Response({'error': 'New password must be different from the current password.'}, status=status.HTTP_400_BAD_REQUEST)

    request.user.set_password(new_password)
    request.user.save()

    return Response({'message': 'Password changed successfully.'})


# ==================== FCM TOKEN + NOTIFICATIONS ====================

from .models import FCMToken, Notification

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_fcm_token(request):
    token = request.data.get('token')
    if not token:
        return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)

    FCMToken.objects.update_or_create(
        user=request.user, token=token, defaults={'token': token}
    )
    return Response({'message': 'FCM token saved successfully'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    data = [{
        'id': str(n.id), 'title': n.title, 'body': n.body,
        'notification_type': n.notification_type,
        'is_read': n.is_read, 'created_at': n.created_at.isoformat(),
    } for n in notifications]
    return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({'message': 'All notifications marked as read'}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_all_notifications(request):
    Notification.objects.filter(user=request.user).delete()
    return Response({'message': 'All notifications cleared'}, status=status.HTTP_200_OK)