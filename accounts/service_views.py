# accounts/service_views.py
# Complete views for Car Wash and EV Check services

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import (
    ServiceCategory, Service, Mechanic,
    ServiceBooking, ServiceReport, CustomerFeedback
)
from .serializers import (
    ServiceCategorySerializer, ServiceSerializer, MechanicSerializer,
    ServiceBookingSerializer, ServiceBookingCreateSerializer,
    ServiceReportSerializer, CustomerFeedbackSerializer
)


# ================================================================
#  CUSTOMER ENDPOINTS
# ================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_service_categories(request):
    """
    Returns all active service categories with their services.
    Customer uses this to see Car Wash and EV Check options.
    GET /api/services/categories/
    """
    categories = ServiceCategory.objects.filter(is_active=True)
    serializer = ServiceCategorySerializer(categories, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_services_by_category(request, category_name):
    """
    Returns all active services under a category.
    category_name: 'car_wash' or 'ev_check'
    GET /api/services/category/car_wash/
    GET /api/services/category/ev_check/
    """
    category = get_object_or_404(
        ServiceCategory,
        name=category_name,
        is_active=True
    )
    services = category.services.filter(is_active=True)
    serializer = ServiceSerializer(services, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_service_booking(request):
    """
    Customer creates a new service booking.
    POST /api/services/bookings/create/
    Body: {
        "service": "<uuid>",
        "vehicle": "<uuid>",
        "booking_date": "2026-03-15",
        "preferred_time": "10:00:00",
        "notes": "optional notes"
    }
    """
    serializer = ServiceBookingCreateSerializer(
        data=request.data,
        context={'request': request}
    )
    if serializer.is_valid():
        booking = serializer.save()
        return Response(
            ServiceBookingSerializer(booking).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_service_bookings(request):
    """
    Returns all service bookings for the logged-in customer.
    Optional filter: ?category=car_wash or ?category=ev_check
    GET /api/services/bookings/
    GET /api/services/bookings/?category=car_wash
    GET /api/services/bookings/?category=ev_check
    """
    try:
        customer = request.user.customer
    except Exception:
        return Response(
            {'error': 'Customer profile not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    bookings = ServiceBooking.objects.filter(
        customer=customer
    ).select_related(
        'service', 'service__category',
        'vehicle', 'assigned_mechanic',
        'assigned_mechanic__staff'
    ).prefetch_related('report', 'feedback')

    # Filter by category if provided
    category = request.query_params.get('category')
    if category:
        bookings = bookings.filter(service__category__name=category)

    serializer = ServiceBookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_service_booking_detail(request, booking_id):
    """
    Returns details of a specific service booking.
    GET /api/services/bookings/<booking_id>/
    """
    try:
        customer = request.user.customer
        booking = ServiceBooking.objects.get(
            id=booking_id,
            customer=customer
        )
    except ServiceBooking.DoesNotExist:
        return Response(
            {'error': 'Booking not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = ServiceBookingSerializer(booking)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_service_booking(request, booking_id):
    """
    Customer cancels their booking.
    Only allowed if status is pending or confirmed.
    POST /api/services/bookings/<booking_id>/cancel/
    """
    try:
        customer = request.user.customer
        booking = ServiceBooking.objects.get(
            id=booking_id,
            customer=customer
        )
    except ServiceBooking.DoesNotExist:
        return Response(
            {'error': 'Booking not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if booking.status not in ['pending', 'confirmed']:
        return Response(
            {'error': f'Cannot cancel booking with status: {booking.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    booking.status = 'cancelled'
    booking.save()

    return Response({'message': 'Booking cancelled successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_feedback(request, booking_id):
    """
    Customer submits feedback after service completion.
    POST /api/services/bookings/<booking_id>/feedback/
    Body: { "rating": 5, "comment": "Great service!" }
    """
    try:
        customer = request.user.customer
        booking = ServiceBooking.objects.get(
            id=booking_id,
            customer=customer
        )
    except ServiceBooking.DoesNotExist:
        return Response(
            {'error': 'Booking not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if booking.status != 'completed':
        return Response(
            {'error': 'You can only give feedback after service is completed'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check feedback not already submitted
    if hasattr(booking, 'feedback'):
        return Response(
            {'error': 'Feedback already submitted for this booking'},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = CustomerFeedbackSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(booking=booking)
        return Response(
            {'message': 'Feedback submitted successfully!',
             'data': serializer.data},
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_service_report(request, booking_id):
    """
    Customer views their vehicle health report after EV Check.
    GET /api/services/bookings/<booking_id>/report/
    """
    try:
        customer = request.user.customer
        booking = ServiceBooking.objects.get(
            id=booking_id,
            customer=customer
        )
    except ServiceBooking.DoesNotExist:
        return Response(
            {'error': 'Booking not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not hasattr(booking, 'report'):
        return Response(
            {'error': 'Report not yet available for this booking'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = ServiceReportSerializer(booking.report)
    return Response(serializer.data)


# ================================================================
#  STAFF ENDPOINTS
# ================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_get_all_service_bookings(request):
    """
    Staff views all service bookings.
    Optional filters:
      ?category=car_wash or ?category=ev_check
      ?status=pending
    GET /api/services/staff/bookings/
    """
    bookings = ServiceBooking.objects.all().select_related(
        'service', 'service__category',
        'customer', 'customer__user',
        'vehicle',
        'assigned_mechanic', 'assigned_mechanic__staff'
    ).prefetch_related('report', 'feedback')

    # Filter by category
    category = request.query_params.get('category')
    if category:
        bookings = bookings.filter(service__category__name=category)

    # Filter by status
    booking_status = request.query_params.get('status')
    if booking_status:
        bookings = bookings.filter(status=booking_status)

    serializer = ServiceBookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def staff_update_service_booking_status(request, booking_id):
    """
    Staff updates booking status.
    PATCH /api/services/staff/bookings/<booking_id>/update-status/
    Body: { "status": "confirmed", "staff_notes": "optional" }

    Status flow:
    pending → confirmed → in_progress → completed
    pending/confirmed → cancelled
    """
    booking = get_object_or_404(ServiceBooking, id=booking_id)

    new_status = request.data.get('status')
    valid_statuses = ['pending', 'confirmed', 'in_progress', 'completed', 'cancelled']

    if not new_status:
        return Response(
            {'error': 'Status is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if new_status not in valid_statuses:
        return Response(
            {'error': f'Invalid status. Choose from: {valid_statuses}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    booking.status = new_status
    if request.data.get('staff_notes'):
        booking.staff_notes = request.data.get('staff_notes')
    booking.save()

    return Response(
        ServiceBookingSerializer(booking).data,
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def staff_assign_mechanic(request, booking_id):
    """
    Staff assigns a mechanic to an EV Check booking.
    POST /api/services/staff/bookings/<booking_id>/assign-mechanic/
    Body: { "mechanic_id": "<uuid>" }
    """
    booking = get_object_or_404(ServiceBooking, id=booking_id)

    # Only for EV Check bookings
    if booking.service.category.name != 'ev_check':
        return Response(
            {'error': 'Mechanic assignment is only for EV Check bookings'},
            status=status.HTTP_400_BAD_REQUEST
        )

    mechanic_id = request.data.get('mechanic_id')
    if not mechanic_id:
        return Response(
            {'error': 'mechanic_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    mechanic = get_object_or_404(Mechanic, id=mechanic_id)

    if not mechanic.is_available:
        return Response(
            {'error': 'This mechanic is not available'},
            status=status.HTTP_400_BAD_REQUEST
        )

    booking.assigned_mechanic = mechanic
    booking.status = 'confirmed'
    booking.save()

    return Response(
        ServiceBookingSerializer(booking).data,
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_get_available_mechanics(request):
    """
    Staff gets list of available mechanics for assignment.
    GET /api/services/staff/mechanics/
    """
    mechanics = Mechanic.objects.filter(
        is_available=True
    ).select_related('staff', 'staff__user')

    serializer = MechanicSerializer(mechanics, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def staff_create_service_report(request, booking_id):
    """
    Staff creates a vehicle health report after EV Check.
    POST /api/services/staff/bookings/<booking_id>/report/
    Body: {
        "issues_found": "Battery at 72%...",
        "recommendations": "Check coolant...",
        "overall_condition": "good",
        "battery_health": 72
    }
    """
    booking = get_object_or_404(ServiceBooking, id=booking_id)

    # Only for EV Check bookings
    if booking.service.category.name != 'ev_check':
        return Response(
            {'error': 'Reports are only for EV Check bookings'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check report doesn't already exist
    if hasattr(booking, 'report'):
        return Response(
            {'error': 'Report already exists for this booking'},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = ServiceReportSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(booking=booking)
        # Auto mark booking as completed
        booking.status = 'completed'
        booking.save()
        return Response(
            {'message': 'Report created successfully!',
             'data': serializer.data},
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_get_service_statistics(request):
    """
    Staff dashboard statistics for services.
    GET /api/services/staff/statistics/
    """
    from django.utils import timezone
    today = timezone.now().date()

    total = ServiceBooking.objects.count()
    pending = ServiceBooking.objects.filter(status='pending').count()
    confirmed = ServiceBooking.objects.filter(status='confirmed').count()
    in_progress = ServiceBooking.objects.filter(status='in_progress').count()
    completed = ServiceBooking.objects.filter(status='completed').count()
    today_bookings = ServiceBooking.objects.filter(booking_date=today).count()
    car_wash = ServiceBooking.objects.filter(
        service__category__name='car_wash'
    ).count()
    ev_check = ServiceBooking.objects.filter(
        service__category__name='ev_check'
    ).count()

    return Response({
        'total': total,
        'pending': pending,
        'confirmed': confirmed,
        'in_progress': in_progress,
        'completed': completed,
        'today': today_bookings,
        'car_wash_total': car_wash,
        'ev_check_total': ev_check,
    })