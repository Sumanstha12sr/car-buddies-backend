from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import User, Customer, Staff
from .serializers import (
    CustomerRegistrationSerializer,
    CustomerSerializer,
    StaffSerializer,
    LoginSerializer,
)


# ==================== CUSTOMER REGISTRATION ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_register(request):
    """Customer registration — no email verification required"""
    serializer = CustomerRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'message': 'Registration successful! You can now login.',
            'email': user.email,
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== EMAIL VERIFICATION (disabled for now) ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, token):
    """Email verification — kept for future use"""
    try:
        customer = Customer.objects.get(email_verification_token=token)
        customer.user.is_active = True
        customer.user.save()
        customer.email_verified_at = timezone.now()
        customer.email_verification_token = None
        customer.save()

        return Response({
            'message': 'Email verified successfully! You can now login.'
        }, status=status.HTTP_200_OK)

    except Customer.DoesNotExist:
        return Response({
            'error': 'Invalid verification token'
        }, status=status.HTTP_400_BAD_REQUEST)


# ==================== CUSTOMER LOGIN ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_login(request):
    """Customer login — returns JWT tokens + customer profile"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        user = authenticate(email=email, password=password)

        if user is not None:
            if user.user_type != 'customer':
                return Response({
                    'error': 'Invalid credentials for customer login'
                }, status=status.HTTP_401_UNAUTHORIZED)

            try:
                customer = Customer.objects.get(user=user)
            except Customer.DoesNotExist:
                return Response({
                    'error': 'Customer profile not found'
                }, status=status.HTTP_404_NOT_FOUND)

            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user_type': 'customer',
                'user': CustomerSerializer(customer).data,
            }, status=status.HTTP_200_OK)

        return Response({
            'error': 'Invalid email or password'
        }, status=status.HTTP_401_UNAUTHORIZED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== STAFF LOGIN ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def staff_login(request):
    """Staff login — returns JWT tokens + staff profile"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        user = authenticate(email=email, password=password)

        if user is not None:
            if user.user_type != 'staff':
                return Response({
                    'error': 'Invalid credentials for staff login'
                }, status=status.HTTP_401_UNAUTHORIZED)

            try:
                staff = Staff.objects.get(user=user)
            except Staff.DoesNotExist:
                return Response({
                    'error': 'Staff profile not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # ── Block mechanic from logging in ───────────────────
            if hasattr(staff, 'mechanic_profile'):
                return Response({
                    'error': 'Mechanics are not allowed to log in to the app.'
                }, status=status.HTTP_403_FORBIDDEN)

            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user_type': 'staff',
                'user': StaffSerializer(staff).data,
            }, status=status.HTTP_200_OK)

        return Response({
            'error': 'Invalid email or password'
        }, status=status.HTTP_401_UNAUTHORIZED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== FCM TOKEN + NOTIFICATIONS ====================

from .models import FCMToken, Notification

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_fcm_token(request):
    """
    Save FCM device token for the logged-in user.
    POST /api/save-fcm-token/
    Body: { "token": "<fcm_token>" }
    """
    token = request.data.get('token')
    if not token:
        return Response(
            {'error': 'Token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    FCMToken.objects.update_or_create(
        user=request.user,
        token=token,
        defaults={'token': token}
    )

    return Response(
        {'message': 'FCM token saved successfully'},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """
    Get all notifications for logged-in user, newest first.
    GET /api/notifications/
    """
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')  # ← FIXED: was missing, notifications now newest first

    data = [{
        'id': str(n.id),
        'title': n.title,
        'body': n.body,
        'notification_type': n.notification_type,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
    } for n in notifications]

    return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """
    Mark all notifications as read for logged-in user.
    POST /api/notifications/mark-read/
    """
    Notification.objects.filter(
        user=request.user,
        is_read=False
    ).update(is_read=True)

    return Response(
        {'message': 'All notifications marked as read'},
        status=status.HTTP_200_OK
    )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_all_notifications(request):
    """
    Delete all notifications for logged-in user.
    DELETE /api/notifications/clear/
    """
    Notification.objects.filter(user=request.user).delete()

    return Response(
        {'message': 'All notifications cleared'},
        status=status.HTTP_200_OK
    )