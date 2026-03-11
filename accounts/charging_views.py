from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import datetime, timedelta, time
from .models import Vehicle, ChargingStation, Charger, TimeSlot, ChargingBooking, Customer
from .serializers import (
    VehicleSerializer, VehicleCreateSerializer,
    ChargingStationListSerializer, ChargingStationDetailSerializer,
    ChargerSerializer, TimeSlotSerializer,
    ChargingBookingSerializer, ChargingBookingCreateSerializer
)

# ==================== VEHICLE MANAGEMENT ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_vehicles(request):
    """Get all vehicles for logged-in customer"""
    try:
        customer = Customer.objects.get(user=request.user)
        vehicles = Vehicle.objects.filter(customer=customer)
        serializer = VehicleSerializer(vehicles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Customer.DoesNotExist:
        return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_vehicle(request):
    """Add a new vehicle for customer"""
    try:
        customer = Customer.objects.get(user=request.user)
        serializer = VehicleCreateSerializer(data=request.data)

        if serializer.is_valid():
            vehicle = serializer.save(customer=customer)
            return Response(
                VehicleSerializer(vehicle).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Customer.DoesNotExist:
        return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_vehicle(request, vehicle_id):
    """Update vehicle details"""
    try:
        customer = Customer.objects.get(user=request.user)
        vehicle = Vehicle.objects.get(id=vehicle_id, customer=customer)

        serializer = VehicleCreateSerializer(vehicle, data=request.data, partial=True)
        if serializer.is_valid():
            vehicle = serializer.save()
            return Response(VehicleSerializer(vehicle).data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Vehicle.DoesNotExist:
        return Response({'error': 'Vehicle not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_vehicle(request, vehicle_id):
    """Delete a vehicle"""
    try:
        customer = Customer.objects.get(user=request.user)
        vehicle = Vehicle.objects.get(id=vehicle_id, customer=customer)
        vehicle.delete()
        return Response({'message': 'Vehicle deleted successfully'}, status=status.HTTP_200_OK)
    except Vehicle.DoesNotExist:
        return Response({'error': 'Vehicle not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_default_vehicle(request, vehicle_id):
    """Set a vehicle as default"""
    try:
        customer = Customer.objects.get(user=request.user)
        vehicle = Vehicle.objects.get(id=vehicle_id, customer=customer)

        Vehicle.objects.filter(customer=customer).update(is_default=False)
        vehicle.is_default = True
        vehicle.save()

        return Response(
            VehicleSerializer(vehicle).data,
            status=status.HTTP_200_OK
        )
    except Vehicle.DoesNotExist:
        return Response({'error': 'Vehicle not found'}, status=status.HTTP_404_NOT_FOUND)


# ==================== CHARGING STATION ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_charging_stations(request):
    """Get all active charging stations"""
    stations = ChargingStation.objects.filter(is_active=True)
    serializer = ChargingStationListSerializer(stations, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_station_detail(request, station_id):
    """Get charging station details with all chargers"""
    try:
        station = ChargingStation.objects.get(id=station_id, is_active=True)
        serializer = ChargingStationDetailSerializer(station)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except ChargingStation.DoesNotExist:
        return Response({'error': 'Station not found'}, status=status.HTTP_404_NOT_FOUND)


# ==================== LIVE AVAILABILITY ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_live_station_availability(request):
    """
    Returns live availability for all active stations.
    Called by Flutter every 30 seconds.
    """
    try:
        stations = ChargingStation.objects.filter(is_active=True)
        data = []

        for station in stations:
            chargers = station.chargers.all()
            total = chargers.count()
            available = chargers.filter(
                is_available=True,
                status='available'
            ).count()
            occupied = chargers.filter(status='occupied').count()
            maintenance = chargers.filter(status='maintenance').count()

            charger_list = []
            for charger in chargers:
                charger_list.append({
                    'id': str(charger.id),
                    'charger_name': charger.charger_name,
                    'charger_type': charger.charger_type,
                    'status': charger.status,
                    'is_available': charger.is_available,
                    'power_output': str(charger.power_output),
                    'price_per_kwh': str(charger.price_per_kwh),
                })

            data.append({
                'station_id': str(station.id),
                'station_name': station.name,
                'total_chargers': total,
                'available_chargers': available,
                'occupied_chargers': occupied,
                'maintenance_chargers': maintenance,
                'chargers': charger_list,
            })

        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


# ==================== CHARGER & TIME SLOTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_chargers(request, station_id):
    """Get available chargers at a station"""
    try:
        charger_type = request.query_params.get('type', None)

        chargers = Charger.objects.filter(
            station_id=station_id,
            is_available=True,
            status='available'
        )

        if charger_type:
            chargers = chargers.filter(charger_type=charger_type)

        serializer = ChargerSerializer(chargers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_time_slots(request, charger_id):
    """Get time slots for a charger on a specific date"""
    try:
        date_str = request.query_params.get('date')
        if not date_str:
            return Response(
                {'error': 'Date parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        today = datetime.now().date()
        now_time = datetime.now().time()

        # Don't allow booking in past dates
        if booking_date < today:
            return Response(
                {'error': 'Cannot book slots in the past'},
                status=status.HTTP_400_BAD_REQUEST
            )

        charger = Charger.objects.get(id=charger_id)

        # Generate slots if they don't exist yet for this date
        existing_slots = TimeSlot.objects.filter(
            charger=charger,
            date=booking_date
        )
        if not existing_slots.exists():
            _generate_time_slots(charger, booking_date)

        # ── Lock slots that have active bookings ───────────────────
        # Only pending, confirmed, in_progress lock the slot
        # Completed and cancelled FREE the slot
        active_bookings = ChargingBooking.objects.filter(
            charger=charger,
            booking_date=booking_date,
            status__in=['pending', 'confirmed', 'in_progress']
        )
        for booking in active_bookings:
            TimeSlot.objects.filter(
                id=booking.time_slot.id
            ).update(is_available=False)

        # Free slots for completed/cancelled bookings
        inactive_bookings = ChargingBooking.objects.filter(
            charger=charger,
            booking_date=booking_date,
            status__in=['completed', 'cancelled']
        )
        for booking in inactive_bookings:
            # Only free if no other active booking on same slot
            other_active = ChargingBooking.objects.filter(
                time_slot=booking.time_slot,
                status__in=['pending', 'confirmed', 'in_progress']
            ).exclude(id=booking.id)
            if not other_active.exists():
                TimeSlot.objects.filter(
                    id=booking.time_slot.id
                ).update(is_available=True)

        # Get all slots for this date ordered by time
        all_slots = TimeSlot.objects.filter(
            charger=charger,
            date=booking_date,
        ).order_by('start_time')

        # ── Filter out past time slots if booking is today ─────────
        if booking_date == today:
            # Add 30 min buffer so customer has time to travel
            buffer_time = (
                datetime.combine(today, now_time) +
                timedelta(minutes=30)
            ).time()

            all_slots = all_slots.filter(
                start_time__gt=buffer_time
            )

        serializer = TimeSlotSerializer(all_slots, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Charger.DoesNotExist:
        return Response({'error': 'Charger not found'}, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD'},
            status=status.HTTP_400_BAD_REQUEST
        )


def _generate_time_slots(charger, date):
    """Generate time slots using get_or_create to avoid duplicates"""
    slots = []
    start_hour = 6   # 6 AM
    end_hour = 22    # 10 PM
    slot_duration = 2  # 2 hours per slot

    for hour in range(start_hour, end_hour, slot_duration):
        start_time = time(hour, 0)
        end_time = time(hour + slot_duration, 0) \
            if hour + slot_duration < 24 else time(23, 59)

        slot, created = TimeSlot.objects.get_or_create(
            charger=charger,
            date=date,
            start_time=start_time,
            defaults={
                'end_time': end_time,
                'is_available': True,
            }
        )
        slots.append(slot)

    return slots


# ==================== BOOKING MANAGEMENT ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_booking(request):
    """Create a new charging booking"""
    try:
        customer = Customer.objects.get(user=request.user)
        if not Vehicle.objects.filter(customer=customer).exists():
            return Response(
                {'error': 'Please add a vehicle before booking'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ChargingBookingCreateSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            booking = serializer.save()
            return Response(
                ChargingBookingSerializer(booking).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Customer.DoesNotExist:
        return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_bookings(request):
    """Get all bookings for logged-in customer"""
    try:
        customer = Customer.objects.get(user=request.user)
        bookings = ChargingBooking.objects.filter(customer=customer)
        serializer = ChargingBookingSerializer(bookings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Customer.DoesNotExist:
        return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_booking_detail(request, booking_id):
    """Get booking details"""
    try:
        customer = Customer.objects.get(user=request.user)
        booking = ChargingBooking.objects.get(id=booking_id, customer=customer)
        serializer = ChargingBookingSerializer(booking)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except ChargingBooking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_booking(request, booking_id):
    """Customer cancels their booking"""
    try:
        customer = Customer.objects.get(user=request.user)
        booking = ChargingBooking.objects.get(
            id=booking_id,
            customer=customer
        )

        if booking.status in ['completed', 'cancelled']:
            return Response(
                {'error': 'Cannot cancel this booking'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = booking.status
        booking.status = 'cancelled'
        booking.save()

        # ── Free up time slot ──────────────────────────────────────
        # Check no other active booking on same slot
        other_active = ChargingBooking.objects.filter(
            time_slot=booking.time_slot,
            status__in=['pending', 'confirmed', 'in_progress']
        ).exclude(id=booking_id)

        if not other_active.exists():
            booking.time_slot.is_available = True
            booking.time_slot.save()

        # ── Free up charger ONLY if it was in_progress ─────────────
        if old_status == 'in_progress':
            charger = booking.charger
            other_in_progress = ChargingBooking.objects.filter(
                charger=charger,
                status='in_progress'
            ).exclude(id=booking_id)

            if not other_in_progress.exists():
                charger.status = 'available'
                charger.is_available = True
                charger.save()

        return Response(
            {'message': 'Booking cancelled successfully'},
            status=status.HTTP_200_OK
        )

    except ChargingBooking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)


# ==================== STAFF ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_bookings_for_staff(request):
    """Get all bookings for staff to manage"""
    try:
        if request.user.user_type != 'staff':
            return Response(
                {'error': 'Only staff can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )

        status_filter = request.query_params.get('status', None)
        bookings = ChargingBooking.objects.all()

        if status_filter:
            bookings = bookings.filter(status=status_filter)

        serializer = ChargingBookingSerializer(bookings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_booking_status(request, booking_id):
    """Staff updates booking status with correct charger availability"""
    try:
        if request.user.user_type != 'staff':
            return Response(
                {'error': 'Only staff can update booking status'},
                status=status.HTTP_403_FORBIDDEN
            )

        booking = ChargingBooking.objects.get(id=booking_id)
        new_status = request.data.get('status')

        if not new_status:
            return Response(
                {'error': 'Status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_statuses = [
            'pending', 'confirmed',
            'in_progress', 'completed', 'cancelled'
        ]
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = booking.status
        booking.status = new_status
        booking.save()

        charger = booking.charger

        # ── Status transition logic ────────────────────────────────

        if new_status == 'confirmed':
            # Staff accepted — lock the time slot
            # Charger stays physically available (customer not arrived yet)
            booking.time_slot.is_available = False
            booking.time_slot.save()

            charger.status = 'available'
            charger.is_available = True
            charger.save()

        elif new_status == 'in_progress':
            # Customer arrived — charger is now physically occupied
            charger.status = 'occupied'
            charger.is_available = False
            charger.save()

        elif new_status == 'completed':
            # Charging done — free up time slot
            other_active = ChargingBooking.objects.filter(
                time_slot=booking.time_slot,
                status__in=['pending', 'confirmed', 'in_progress']
            ).exclude(id=booking_id)

            if not other_active.exists():
                booking.time_slot.is_available = True
                booking.time_slot.save()

            # Free charger if no other in_progress bookings
            other_in_progress = ChargingBooking.objects.filter(
                charger=charger,
                status='in_progress'
            ).exclude(id=booking_id)

            if not other_in_progress.exists():
                charger.status = 'available'
                charger.is_available = True
                charger.save()

        elif new_status == 'cancelled':
            # Staff rejected — free time slot
            other_active = ChargingBooking.objects.filter(
                time_slot=booking.time_slot,
                status__in=['pending', 'confirmed', 'in_progress']
            ).exclude(id=booking_id)

            if not other_active.exists():
                booking.time_slot.is_available = True
                booking.time_slot.save()

            # Only free charger if it was physically in use
            if old_status == 'in_progress':
                other_in_progress = ChargingBooking.objects.filter(
                    charger=charger,
                    status='in_progress'
                ).exclude(id=booking_id)

                if not other_in_progress.exists():
                    charger.status = 'available'
                    charger.is_available = True
                    charger.save()

        return Response(
            ChargingBookingSerializer(booking).data,
            status=status.HTTP_200_OK
        )

    except ChargingBooking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_booking_statistics(request):
    """Get booking statistics for staff dashboard"""
    try:
        if request.user.user_type != 'staff':
            return Response(
                {'error': 'Only staff can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )

        total_bookings = ChargingBooking.objects.count()
        pending_bookings = ChargingBooking.objects.filter(status='pending').count()
        confirmed_bookings = ChargingBooking.objects.filter(status='confirmed').count()
        in_progress_bookings = ChargingBooking.objects.filter(status='in_progress').count()
        completed_bookings = ChargingBooking.objects.filter(status='completed').count()
        cancelled_bookings = ChargingBooking.objects.filter(status='cancelled').count()

        today = timezone.now().date()
        today_bookings = ChargingBooking.objects.filter(booking_date=today).count()

        return Response({
            'total_bookings': total_bookings,
            'pending_bookings': pending_bookings,
            'confirmed_bookings': confirmed_bookings,
            'in_progress_bookings': in_progress_bookings,
            'completed_bookings': completed_bookings,
            'cancelled_bookings': cancelled_bookings,
            'today_bookings': today_bookings,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)