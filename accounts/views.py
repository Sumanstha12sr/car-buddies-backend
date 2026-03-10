from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import User, Customer, Staff
from .serializers import (
    CustomerRegistrationSerializer, CustomerSerializer, 
    StaffSerializer, LoginSerializer
)

# Customer Registration - SIMPLIFIED (No Email Verification)
@api_view(['POST'])
@permission_classes([AllowAny])
def customer_register(request):
    serializer = CustomerRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        return Response({
            'message': 'Registration successful! You can now login.',
            'email': user.email,
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Email Verification - KEEP THIS for when you add it back later
@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, token):
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

# Customer Login - SIMPLIFIED (Removed email verification check)
@api_view(['POST'])
@permission_classes([AllowAny])
def customer_login(request):
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
            
            # REMOVED: Email verification check
            # Users can login immediately after registration
            
            refresh = RefreshToken.for_user(user)
            customer = Customer.objects.get(user=user)
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user_type': 'customer',
                'user': CustomerSerializer(customer).data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Staff Login
@api_view(['POST'])
@permission_classes([AllowAny])
def staff_login(request):
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
            
            refresh = RefreshToken.for_user(user)
            staff = Staff.objects.get(user=user)
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user_type': 'staff',
                'user': StaffSerializer(staff).data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)