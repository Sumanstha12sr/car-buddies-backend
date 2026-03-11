from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
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

