from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import (
    ServiceCategory, Service, Mechanic,
    ServiceBooking, ServiceReport, BlueBookRenewal
)
from .serializers import (
    ServiceCategorySerializer, ServiceSerializer, MechanicSerializer,
    ServiceBookingSerializer, ServiceBookingCreateSerializer,
    ServiceReportSerializer, BlueBookRenewalSerializer,
    BlueBookRenewalCreateSerializer,
)
from .firebase_service import (
    notify_staff_new_booking,
    notify_customer_booking_update,
    notify_all_customers_new_service,
)
from .notification_utils import notify_staff, notify_customer  # ← updated


# ================================================================
#  CUSTOMER ENDPOINTS
# ================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_service_categories(request):
    categories = ServiceCategory.objects.filter(is_active=True)
    serializer = ServiceCategorySerializer(categories, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_services_by_category(request, category_name):
    category = get_object_or_404(ServiceCategory, name=category_name, is_active=True)
    services = category.services.filter(is_active=True)
    serializer = ServiceSerializer(services, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_service_booking(request):
    serializer = ServiceBookingCreateSerializer(
        data=request.data,
        context={'request': request}
    )
    if serializer.is_valid():
        booking = serializer.save()

        # ── Notify staff of new booking (Firebase push) ────────
        try:
            notify_staff_new_booking(booking)
        except Exception:
            pass

        # ── Notify staff (in-app + FCM via notification_utils) ─
        # Determine type from the service category name
        try:
            category_name = booking.service.category.name  # e.g. 'car_wash' or 'ev_check'

            if category_name == 'car_wash':
                notify_staff(
                    notification_type='carwash_booking',
                    title='🚿 New Car Wash Booking',
                    body=(
                        f'{request.user.get_full_name() or request.user.email} '
                        f'booked a car wash for '
                        f'{booking.booking_date.strftime("%d %b %Y")}.'
                    ),
                    extra_data={'booking_id': str(booking.id)},
                )
            elif category_name == 'ev_check':
                notify_staff(
                    notification_type='ev_checkup_booking',
                    title='🔍 New EV Checkup Booking',
                    body=(
                        f'{request.user.get_full_name() or request.user.email} '
                        f'booked an EV health checkup for '
                        f'{booking.booking_date.strftime("%d %b %Y")}.'
                    ),
                    extra_data={'booking_id': str(booking.id)},
                )
        except Exception:
            pass

        return Response(
            ServiceBookingSerializer(booking).data,
            status=status.HTTP_201_CREATED
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


import traceback

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_service_bookings(request):
    try:
        customer = request.user.customer
    except Exception:
        return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)

    bookings = ServiceBooking.objects.filter(
        customer=customer
    ).select_related(
        'service', 'service__category', 'vehicle', 'assigned_mechanic',
    ).prefetch_related('report',) 

    category = request.query_params.get('category')
    if category:
        bookings = bookings.filter(service__category__name=category)

    try:
        serializer = ServiceBookingSerializer(bookings, many=True)
        data = serializer.data
        return Response(data)
    except Exception as e:
        traceback.print_exc()  # ← prints full error to terminal
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_service_booking_detail(request, booking_id):
    try:
        customer = request.user.customer
        booking = ServiceBooking.objects.get(id=booking_id, customer=customer)
    except ServiceBooking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ServiceBookingSerializer(booking)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_service_booking(request, booking_id):
    try:
        customer = request.user.customer
        booking = ServiceBooking.objects.get(id=booking_id, customer=customer)
    except ServiceBooking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    if booking.status not in ['pending', 'confirmed']:
        return Response(
            {'error': f'Cannot cancel booking with status: {booking.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    booking.status = 'cancelled'
    booking.save()

    # ── Notify staff that customer cancelled ──────────────────
    try:
        notify_staff(
            notification_type='booking_cancelled',
            title='❌ Service Booking Cancelled',
            body=(
                f'{request.user.get_full_name() or request.user.email} '
                f'cancelled their {booking.service.name} booking for '
                f'{booking.booking_date.strftime("%d %b %Y")}.'
            ),
            extra_data={'booking_id': str(booking.id)},
        )
    except Exception:
        pass

    return Response({'message': 'Booking cancelled successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_service_report(request, booking_id):
    try:
        customer = request.user.customer
        booking = ServiceBooking.objects.get(id=booking_id, customer=customer)
    except ServiceBooking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

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
    bookings = ServiceBooking.objects.all().select_related(
        'service', 'service__category',
        'customer', 'customer__user',
        'vehicle',
    ).prefetch_related('report',)

    category = request.query_params.get('category')
    if category:
        bookings = bookings.filter(service__category__name=category)

    booking_status = request.query_params.get('status')
    if booking_status:
        bookings = bookings.filter(status=booking_status)

    serializer = ServiceBookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def staff_update_service_booking_status(request, booking_id):
    booking = get_object_or_404(ServiceBooking, id=booking_id)

    new_status = request.data.get('status')
    valid_statuses = ['pending', 'confirmed', 'in_progress', 'completed', 'cancelled']

    if not new_status:
        return Response({'error': 'Status is required'}, status=status.HTTP_400_BAD_REQUEST)

    if new_status not in valid_statuses:
        return Response(
            {'error': f'Invalid status. Choose from: {valid_statuses}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ── Guard: mechanic must be assigned before confirming ─────
    if new_status == 'confirmed' and booking.assigned_mechanic is None:
        return Response(
            {'error': 'Please assign a mechanic before confirming this booking.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    booking.status = new_status
    if request.data.get('staff_notes'):
        booking.staff_notes = request.data.get('staff_notes')
    booking.save()

    # ── FIXED: Prevent double notification on staff cancel ─────────────
    # notify_customer_booking_update() creates BOTH FCM push AND a DB record
    # with "Auto-Cancelled" wording. Skip it for cancelled; use notify_customer() only.
    if new_status != 'cancelled':
        try:
            notify_customer_booking_update(booking, new_status)
        except Exception:
            pass

    # For cancelled by staff: send single correct DB notification
    if new_status == 'cancelled':
        try:
            notify_customer(
                user=booking.customer.user,
                notification_type='booking_cancelled',
                title='❌ Booking Cancelled by Staff',
                body=(
                    f'Your {booking.service.name} booking on '
                    f'{booking.booking_date.strftime("%d %b %Y")} '
                    f'has been cancelled by our staff.'
                ),
            )
        except Exception:
            pass

    return Response(
        ServiceBookingSerializer(booking).data,
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def staff_assign_mechanic(request, booking_id):
    booking = get_object_or_404(ServiceBooking, id=booking_id)

    mechanic_id = request.data.get('mechanic_id')
    if not mechanic_id:
        return Response({'error': 'mechanic_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    mechanic = get_object_or_404(Mechanic, id=mechanic_id)

    if not mechanic.is_available:
        return Response({'error': 'This mechanic is not available'}, status=status.HTTP_400_BAD_REQUEST)

    booking.assigned_mechanic = mechanic
    booking.save()

    return Response(ServiceBookingSerializer(booking).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_get_available_mechanics(request):
    mechanics = Mechanic.objects.filter(is_available=True)
    serializer = MechanicSerializer(mechanics, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def staff_create_service_report(request, booking_id):
    booking = get_object_or_404(ServiceBooking, id=booking_id)

    if booking.service.category.name != 'ev_check':
        return Response({'error': 'Reports are only for EV Check bookings'}, status=status.HTTP_400_BAD_REQUEST)

    if hasattr(booking, 'report'):
        return Response({'error': 'Report already exists for this booking'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ServiceReportSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(booking=booking)
        booking.status = 'completed'
        booking.save()

        # ── Notify customer report is ready ───────────────────
        try:
            notify_customer_booking_update(booking, 'completed')
        except Exception:
            pass

        return Response(
            {'message': 'Report created successfully!', 'data': serializer.data},
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_get_service_statistics(request):
    from django.utils import timezone
    today = timezone.now().date()

    total = ServiceBooking.objects.count()
    pending = ServiceBooking.objects.filter(status='pending').count()
    confirmed = ServiceBooking.objects.filter(status='confirmed').count()
    in_progress = ServiceBooking.objects.filter(status='in_progress').count()
    completed = ServiceBooking.objects.filter(status='completed').count()
    today_bookings = ServiceBooking.objects.filter(booking_date=today).count()
    car_wash = ServiceBooking.objects.filter(service__category__name='car_wash').count()
    ev_check = ServiceBooking.objects.filter(service__category__name='ev_check').count()

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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vehicle_booked_slots(request, vehicle_id):
    from .models import Vehicle, ChargingBooking
    from django.utils.dateparse import parse_date

    date_str = request.query_params.get('date')
    if not date_str:
        return Response({'error': 'date parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    booking_date = parse_date(date_str)
    if not booking_date:
        return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
    except Vehicle.DoesNotExist:
        return Response({'error': 'Vehicle not found'}, status=status.HTTP_404_NOT_FOUND)

    booked_hours = set()

    service_bookings = ServiceBooking.objects.filter(
        vehicle=vehicle, booking_date=booking_date,
        status__in=['pending', 'confirmed', 'in_progress']
    )
    for booking in service_bookings:
        if booking.preferred_time:
            try:
                hour = int(str(booking.preferred_time).split(':')[0])
                booked_hours.add(hour)
            except (ValueError, IndexError):
                pass

    charging_bookings = ChargingBooking.objects.filter(
        vehicle=vehicle, booking_date=booking_date,
        status__in=['pending', 'confirmed', 'in_progress']
    )
    for booking in charging_bookings:
        if booking.start_time:
            try:
                hour = int(str(booking.start_time).split(':')[0])
                booked_hours.add(hour)
            except (ValueError, IndexError):
                pass

    return Response({
        'date': date_str,
        'vehicle_id': str(vehicle_id),
        'booked_hours': sorted(list(booked_hours)),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_analytics(request):
    from .models import ChargingBooking, ChargingStation
    from django.db.models import Sum, Count
    from django.utils import timezone
    from collections import defaultdict
    import calendar

    try:
        customer = request.user.customer
    except Exception:
        return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)

    completed_services = ServiceBooking.objects.filter(
        customer=customer, status='completed'
    ).select_related('service', 'service__category')

    completed_charging = ChargingBooking.objects.filter(
        customer=customer, status='completed'
    ).select_related('charger__station')

    service_spent = sum(float(b.estimated_cost or b.service.price) for b in completed_services)
    charging_spent = sum(float(b.estimated_cost or 0) for b in completed_charging if b.estimated_cost)
    total_spent = service_spent + charging_spent

    car_wash_spent = sum(
        float(b.estimated_cost or b.service.price)
        for b in completed_services if b.service.category.name == 'car_wash'
    )
    ev_check_spent = sum(
        float(b.estimated_cost or b.service.price)
        for b in completed_services if b.service.category.name == 'ev_check'
    )

    spent_by_category = {
        'charging': round(charging_spent, 2),
        'car_wash': round(car_wash_spent, 2),
        'ev_check': round(ev_check_spent, 2),
    }

    service_counts = defaultdict(lambda: {'count': 0, 'total': 0.0})
    for b in completed_services:
        name = b.service.name
        service_counts[name]['count'] += 1
        service_counts[name]['total'] += float(b.estimated_cost or b.service.price)

    bookings_by_service = [
        {'name': name, 'count': data['count'], 'total': round(data['total'], 2)}
        for name, data in service_counts.items()
    ]
    bookings_by_service.sort(key=lambda x: x['count'], reverse=True)

    today = timezone.now().date()
    monthly = defaultdict(float)

    for b in completed_services:
        key = b.booking_date.strftime('%b %Y')
        monthly[key] += float(b.estimated_cost or b.service.price)

    for b in completed_charging:
        if b.estimated_cost:
            key = b.booking_date.strftime('%b %Y')
            monthly[key] += float(b.estimated_cost)

    monthly_trend = []
    for i in range(5, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        key = f"{calendar.month_abbr[month]} {year}"
        monthly_trend.append({'month': key, 'amount': round(monthly.get(key, 0.0), 2)})

    all_charging = ChargingBooking.objects.filter(customer=customer).select_related('charger__station')
    station_counts = defaultdict(int)
    for b in all_charging:
        try:
            station_counts[b.charger.station.name] += 1
        except Exception:
            pass

    most_visited_station = None
    if station_counts:
        top_station = max(station_counts, key=station_counts.get)
        most_visited_station = {'name': top_station, 'count': station_counts[top_station]}

    total_service_bookings = ServiceBooking.objects.filter(customer=customer).count()
    total_charging_bookings = ChargingBooking.objects.filter(customer=customer).count()

    return Response({
        'total_spent': round(total_spent, 2),
        'spent_by_category': spent_by_category,
        'bookings_by_service': bookings_by_service,
        'monthly_trend': monthly_trend,
        'most_visited_station': most_visited_station,
        'total_bookings': total_service_bookings + total_charging_bookings,
        'completed_bookings': completed_services.count() + completed_charging.count(),
    })


# ==================== BLUE BOOK RENEWAL ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_blue_book_renewal(request):
    serializer = BlueBookRenewalCreateSerializer(
        data=request.data, context={'request': request}
    )
    if serializer.is_valid():
        renewal = serializer.save()

        # ── Notify staff of new blue book submission ───────────
        try:
            notify_staff(
                notification_type='bluebook_submission',
                title='📋 New Blue Book Renewal',
                body=(
                    f'{request.user.get_full_name() or request.user.email} '
                    f'submitted a blue book renewal for a '
                    f'{renewal.vehicle_type.replace("_", " ").title()}.'
                ),
                extra_data={'renewal_id': str(renewal.id)},
            )
        except Exception:
            pass

        return Response(BlueBookRenewalSerializer(renewal).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_blue_book_renewals(request):
    try:
        customer = request.user.customer
    except Exception:
        return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)
    renewals = BlueBookRenewal.objects.filter(customer=customer)
    serializer = BlueBookRenewalSerializer(renewals, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_get_all_blue_book_renewals(request):
    renewals = BlueBookRenewal.objects.all().select_related('customer', 'customer__user')
    status_filter = request.query_params.get('status')
    if status_filter:
        renewals = renewals.filter(status=status_filter)
    serializer = BlueBookRenewalSerializer(renewals, many=True)
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def staff_update_blue_book_status(request, renewal_id):
    try:
        renewal = BlueBookRenewal.objects.get(id=renewal_id)
    except BlueBookRenewal.DoesNotExist:
        return Response({'error': 'Renewal not found'}, status=status.HTTP_404_NOT_FOUND)

    new_status = request.data.get('status')
    valid_statuses = ['submitted', 'under_review', 'completed', 'rejected']
    if new_status not in valid_statuses:
        return Response(
            {'error': f'Invalid status. Choose from: {valid_statuses}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    renewal.status = new_status
    if request.data.get('staff_notes'):
        renewal.staff_notes = request.data.get('staff_notes')
    renewal.save()

    return Response(BlueBookRenewalSerializer(renewal).data, status=status.HTTP_200_OK)