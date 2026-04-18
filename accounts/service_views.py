from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
import traceback
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
    notify_customer_booking_update,
    notify_all_customers_new_service,
    send_fcm_push_to_user,
)
from .notification_utils import notify_staff, notify_customer


def get_customer_name(request):
    try:
        return request.user.customer.full_name
    except Exception:
        return request.user.email


# ================================================================
#  CUSTOMER ENDPOINTS
# ================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_service_categories(request):
    categories = ServiceCategory.objects.filter(is_active=True)
    return Response(ServiceCategorySerializer(categories, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_services_by_category(request, category_name):
    category = get_object_or_404(ServiceCategory, name=category_name, is_active=True)
    services = category.services.filter(is_active=True)
    return Response(ServiceSerializer(services, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_service_booking(request):
    serializer = ServiceBookingCreateSerializer(
        data=request.data, context={'request': request}
    )
    if serializer.is_valid():
        booking = serializer.save()
        try:
            category_name = booking.service.category.name
            if category_name == 'car_wash':
                notify_staff(
                    notification_type='carwash_booking',
                    title='🚿 New Car Wash Booking',
                    body=(
                        f'{get_customer_name(request)} booked a car wash for '
                        f'{booking.booking_date.strftime("%d %b %Y")}.'
                    ),
                    extra_data={'booking_id': str(booking.id)},
                )
            elif category_name == 'ev_check':
                notify_staff(
                    notification_type='ev_checkup_booking',
                    title='🔍 New EV Checkup Booking',
                    body=(
                        f'{get_customer_name(request)} booked an EV health checkup for '
                        f'{booking.booking_date.strftime("%d %b %Y")}.'
                    ),
                    extra_data={'booking_id': str(booking.id)},
                )
        except Exception:
            traceback.print_exc()

        return Response(
            ServiceBookingSerializer(booking).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_service_bookings(request):
    try:
        customer = request.user.customer
    except Exception:
        return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)

    bookings = ServiceBooking.objects.filter(customer=customer).select_related(
        'service', 'service__category', 'vehicle', 'assigned_mechanic',
    ).prefetch_related('report')

    category = request.query_params.get('category')
    if category:
        bookings = bookings.filter(service__category__name=category)

    try:
        return Response(ServiceBookingSerializer(bookings, many=True).data)
    except Exception as e:
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_service_booking_detail(request, booking_id):
    try:
        customer = request.user.customer
        booking = ServiceBooking.objects.get(id=booking_id, customer=customer)
    except ServiceBooking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response(ServiceBookingSerializer(booking).data)


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

    try:
        notify_staff(
            notification_type='booking_cancelled',
            title='❌ Service Booking Cancelled',
            body=(
                f'{get_customer_name(request)} cancelled their '
                f'{booking.service.name} booking for '
                f'{booking.booking_date.strftime("%d %b %Y")}.'
            ),
            extra_data={'booking_id': str(booking.id)},
        )
    except Exception:
        traceback.print_exc()

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
    return Response(ServiceReportSerializer(booking.report).data)


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
    ).prefetch_related('report')

    category = request.query_params.get('category')
    if category:
        bookings = bookings.filter(service__category__name=category)

    booking_status = request.query_params.get('status')
    if booking_status:
        bookings = bookings.filter(status=booking_status)

    return Response(ServiceBookingSerializer(bookings, many=True).data)


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
    if new_status == 'confirmed' and booking.assigned_mechanic is None:
        return Response(
            {'error': 'Please assign a mechanic before confirming this booking.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    booking.status = new_status
    if request.data.get('staff_notes'):
        booking.staff_notes = request.data.get('staff_notes')
    booking.save()

    # ── Notification routing — one path, one notification ────────────────
    #
    # cancelled → notify_customer() + send_fcm_push_to_user() directly
    #             (staff-specific message differs from auto-cancel message)
    #
    # completed + ev_check → SKIP here entirely.
    #             staff_create_service_report() owns this notification
    #             because it fires at the same moment and includes the
    #             "report is ready" message. Sending here too = duplicate.
    #
    # completed + car_wash → notify_customer_booking_update() handles
    #             DB write + FCM push in one call.
    #
    # confirmed / in_progress → notify_customer_booking_update() handles
    #             DB write + FCM push in one call.
    #
    try:
        is_ev_check = booking.service.category.name == 'ev_check'

        if new_status == 'cancelled':
            title = '❌ Booking Cancelled by Staff'
            body = (
                f'Your {booking.service.name} booking on '
                f'{booking.booking_date.strftime("%d %b %Y")} '
                f'has been cancelled by our staff.'
            )
            notify_customer(
                user=booking.customer.user,
                notification_type='booking_cancelled',
                title=title,
                body=body,
            )
            send_fcm_push_to_user(
                user=booking.customer.user,
                title=title,
                body=body,
                data={'notification_type': 'booking_cancelled',
                      'booking_id': str(booking_id)},
            )

        elif new_status == 'completed' and is_ev_check:
            # DO NOTHING here — staff_create_service_report() sends the
            # notification with the report-ready message. If the report
            # endpoint hasn't been called yet this is a premature status
            # change; the customer will get notified when the report is filed.
            pass

        else:
            # confirmed, in_progress, completed (car_wash)
            # notify_customer_booking_update() calls notify_customer() for
            # the DB record and send_fcm_push_to_user() for FCM — one each.
            notify_customer_booking_update(booking, new_status)

    except Exception:
        traceback.print_exc()

    return Response(ServiceBookingSerializer(booking).data, status=status.HTTP_200_OK)


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
    return Response(MechanicSerializer(mechanics, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_get_all_mechanics(request):
    """
    Returns ALL mechanics with their active assigned bookings
    (confirmed or in_progress).
    """
    from django.db.models import Prefetch

    active_bookings_qs = ServiceBooking.objects.filter(
        status__in=['confirmed', 'in_progress']
    ).select_related('service', 'service__category', 'customer', 'vehicle')

    mechanics = Mechanic.objects.prefetch_related(
        Prefetch('assigned_bookings', queryset=active_bookings_qs,
                 to_attr='active_assigned_bookings')
    ).order_by('full_name')

    result = []
    for mechanic in mechanics:
        result.append({
            'id':               str(mechanic.id),
            'full_name':        mechanic.full_name,
            'specialization':   mechanic.specialization,
            'experience_years': mechanic.experience_years,
            'is_available':     mechanic.is_available,
            'assigned_bookings': [
                {
                    'id':             str(b.id),
                    'service_name':   b.service.name,
                    'category':       b.service.category.name,
                    'status':         b.status,
                    'booking_date':   str(b.booking_date),
                    'preferred_time': str(b.preferred_time)[:5],
                    'customer_name':  b.customer.full_name,
                    'vehicle_name':   b.vehicle.vehicle_name,
                    'vehicle_number': b.vehicle.vehicle_number,
                }
                for b in mechanic.active_assigned_bookings
            ],
        })

    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def staff_create_service_report(request, booking_id):
    booking = get_object_or_404(ServiceBooking, id=booking_id)

    if booking.service.category.name != 'ev_check':
        return Response(
            {'error': 'Reports are only for EV Check bookings'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if hasattr(booking, 'report'):
        return Response(
            {'error': 'Report already exists for this booking'},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = ServiceReportSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(booking=booking)
        booking.status = 'completed'
        booking.save()

        # This is the ONE and ONLY place that notifies the customer
        # about EV check completion. staff_update_service_booking_status
        # explicitly skips 'completed' for ev_check to avoid firing here too.
        try:
            title = '🎉 EV Check-up Completed'
            body = (
                f'Your {booking.service.name} has been completed. '
                f'Your service report is now available. Tap to view details.'
            )
            notify_customer(
                user=booking.customer.user,
                notification_type='booking_completed',
                title=title,
                body=body,
            )
            send_fcm_push_to_user(
                user=booking.customer.user,
                title=title,
                body=body,
                data={'notification_type': 'booking_completed',
                      'booking_id': str(booking_id)},
            )
        except Exception:
            traceback.print_exc()

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
    return Response({
        'total':         ServiceBooking.objects.count(),
        'pending':       ServiceBooking.objects.filter(status='pending').count(),
        'confirmed':     ServiceBooking.objects.filter(status='confirmed').count(),
        'in_progress':   ServiceBooking.objects.filter(status='in_progress').count(),
        'completed':     ServiceBooking.objects.filter(status='completed').count(),
        'today':         ServiceBooking.objects.filter(booking_date=today).count(),
        'car_wash_total': ServiceBooking.objects.filter(service__category__name='car_wash').count(),
        'ev_check_total': ServiceBooking.objects.filter(service__category__name='ev_check').count(),
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
    for b in ServiceBooking.objects.filter(
        vehicle=vehicle, booking_date=booking_date,
        status__in=['pending', 'confirmed', 'in_progress']
    ):
        if b.preferred_time:
            try:
                booked_hours.add(int(str(b.preferred_time).split(':')[0]))
            except (ValueError, IndexError):
                pass

    for b in ChargingBooking.objects.filter(
        vehicle=vehicle, booking_date=booking_date,
        status__in=['pending', 'confirmed', 'in_progress']
    ):
        if b.start_time:
            try:
                booked_hours.add(int(str(b.start_time).split(':')[0]))
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
    from .models import ChargingBooking
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

    service_spent  = sum(float(b.estimated_cost or b.service.price) for b in completed_services)
    charging_spent = sum(float(b.estimated_cost or 0) for b in completed_charging if b.estimated_cost)
    car_wash_spent = sum(
        float(b.estimated_cost or b.service.price)
        for b in completed_services if b.service.category.name == 'car_wash'
    )
    ev_check_spent = sum(
        float(b.estimated_cost or b.service.price)
        for b in completed_services if b.service.category.name == 'ev_check'
    )

    service_counts = defaultdict(lambda: {'count': 0, 'total': 0.0})
    for b in completed_services:
        service_counts[b.service.name]['count'] += 1
        service_counts[b.service.name]['total'] += float(b.estimated_cost or b.service.price)

    bookings_by_service = sorted(
        [{'name': n, 'count': d['count'], 'total': round(d['total'], 2)}
         for n, d in service_counts.items()],
        key=lambda x: x['count'], reverse=True
    )

    today = timezone.now().date()
    monthly = defaultdict(float)
    for b in completed_services:
        monthly[b.booking_date.strftime('%b %Y')] += float(b.estimated_cost or b.service.price)
    for b in completed_charging:
        if b.estimated_cost:
            monthly[b.booking_date.strftime('%b %Y')] += float(b.estimated_cost)

    monthly_trend = []
    for i in range(5, -1, -1):
        month = today.month - i
        year  = today.year
        while month <= 0:
            month += 12
            year  -= 1
        key = f"{calendar.month_abbr[month]} {year}"
        monthly_trend.append({'month': key, 'amount': round(monthly.get(key, 0.0), 2)})

    all_charging  = ChargingBooking.objects.filter(customer=customer).select_related('charger__station')
    station_counts = defaultdict(int)
    for b in all_charging:
        try:
            station_counts[b.charger.station.name] += 1
        except Exception:
            pass

    most_visited_station = None
    if station_counts:
        top = max(station_counts, key=station_counts.get)
        most_visited_station = {'name': top, 'count': station_counts[top]}

    return Response({
        'total_spent':        round(service_spent + charging_spent, 2),
        'spent_by_category':  {
            'charging':  round(charging_spent, 2),
            'car_wash':  round(car_wash_spent, 2),
            'ev_check':  round(ev_check_spent, 2),
        },
        'bookings_by_service':    bookings_by_service,
        'monthly_trend':          monthly_trend,
        'most_visited_station':   most_visited_station,
        'total_bookings':         ServiceBooking.objects.filter(customer=customer).count() +
                                  ChargingBooking.objects.filter(customer=customer).count(),
        'completed_bookings':     completed_services.count() + completed_charging.count(),
    })


# ==================== BLUE BOOK RENEWAL ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_blue_book_renewal(request):
    serializer = BlueBookRenewalCreateSerializer(
        data=request.data, context={'request': request}
    )
    if serializer.is_valid():
        try:
            renewal = serializer.save()
        except Exception as e:
            traceback.print_exc()
            return Response({'debug_error': str(e)}, status=500)
        try:
            notify_staff(
                notification_type='blue_book_renewal',
                title='📋 New Blue Book Renewal',
                body=(
                    f'{renewal.full_name} submitted a blue book renewal '
                    f'for vehicle {renewal.vehicle_number}.'
                ),
                extra_data={'renewal_id': str(renewal.id)},
            )
        except Exception:
            traceback.print_exc()
        return Response(
            BlueBookRenewalSerializer(renewal, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_blue_book_renewals(request):
    try:
        customer = request.user.customer
    except Exception:
        return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)
    renewals = BlueBookRenewal.objects.filter(customer=customer)
    return Response(
        BlueBookRenewalSerializer(renewals, many=True, context={'request': request}).data
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_get_all_blue_book_renewals(request):
    renewals = BlueBookRenewal.objects.all().select_related('customer', 'customer__user')
    status_filter = request.query_params.get('status')
    if status_filter:
        renewals = renewals.filter(status=status_filter)
    return Response(
        BlueBookRenewalSerializer(renewals, many=True, context={'request': request}).data
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def staff_update_blue_book_status(request, renewal_id):
    try:
        renewal = BlueBookRenewal.objects.get(id=renewal_id)
    except BlueBookRenewal.DoesNotExist:
        return Response({'error': 'Renewal not found'}, status=status.HTTP_404_NOT_FOUND)

    new_status = request.data.get('status')
    if new_status not in ['submitted', 'under_review', 'completed', 'rejected']:
        return Response(
            {'error': 'Invalid status. Choose from: submitted, under_review, completed, rejected'},
            status=status.HTTP_400_BAD_REQUEST
        )

    renewal.status = new_status
    if request.data.get('staff_notes'):
        renewal.staff_notes = request.data.get('staff_notes')
    renewal.save()
    return Response(
        BlueBookRenewalSerializer(renewal, context={'request': request}).data,
        status=status.HTTP_200_OK
    )