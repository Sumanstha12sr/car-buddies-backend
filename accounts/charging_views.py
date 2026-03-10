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
        
        # Remove default from all other vehicles
        Vehicle.objects.filter(customer=customer).update(is_default=False)
        
        # Set this vehicle as default
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
    """Get charging station details with chargers"""
    try:
        station = ChargingStation.objects.get(id=station_id, is_active=True)
        serializer = ChargingStationDetailSerializer(station)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except ChargingStation.DoesNotExist:
        return Response({'error': 'Station not found'}, status=status.HTTP_404_NOT_FOUND)


# ==================== CHARGER & TIME SLOTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_chargers(request, station_id):
    """Get available chargers at a station"""
    try:
        charger_type = request.query_params.get('type', None)  # 'AC' or 'DC'
        
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
    """Get available time slots for a charger on a specific date"""
    try:
        date_str = request.query_params.get('date')
        if not date_str:
            return Response(
                {'error': 'Date parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get or create time slots for the date
        charger = Charger.objects.get(id=charger_id)
        time_slots = TimeSlot.objects.filter(
            charger=charger,
            date=booking_date,
            is_available=True
        )
        
        # If no slots exist for this date, create them
        if not time_slots.exists():
            time_slots = _generate_time_slots(charger, booking_date)
        
        serializer = TimeSlotSerializer(time_slots, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    except Charger.DoesNotExist:
        return Response({'error': 'Charger not found'}, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD'},
            status=status.HTTP_400_BAD_REQUEST
        )


def _generate_time_slots(charger, date):
    """Generate time slots for a charger on a specific date"""
    slots = []
    start_hour = 6  # 6 AM
    end_hour = 22   # 10 PM
    slot_duration = 2  # 2 hours per slot
    
    for hour in range(start_hour, end_hour, slot_duration):
        start_time = time(hour, 0)
        end_time = time(hour + slot_duration, 0) if hour + slot_duration < 24 else time(23, 59)
        
        slot = TimeSlot.objects.create(
            charger=charger,
            date=date,
            start_time=start_time,
            end_time=end_time,
            is_available=True
        )
        slots.append(slot)
    
    return slots


# ==================== BOOKING MANAGEMENT ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_booking(request):
    """Create a new charging booking"""
    try:
        # Check if customer has vehicles
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
    """Cancel a booking"""
    try:
        customer = Customer.objects.get(user=request.user)
        booking = ChargingBooking.objects.get(id=booking_id, customer=customer)
        
        if booking.status in ['completed', 'cancelled']:
            return Response(
                {'error': 'Cannot cancel this booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'cancelled'
        booking.save()
        
        # Make time slot available again
        booking.time_slot.is_available = True
        booking.time_slot.save()
        
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
        # Check if user is staff
        if request.user.user_type != 'staff':
            return Response(
                {'error': 'Only staff can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get filter parameters
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
    """Staff can update booking status (confirm, complete, etc.)"""
    try:
        # Check if user is staff
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
        
        # Validate status
        valid_statuses = ['pending', 'confirmed', 'in_progress', 'completed', 'cancelled']
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update booking status
        booking.status = new_status
        booking.save()
        
        # If confirmed, mark time slot as unavailable
        if new_status == 'confirmed':
            booking.time_slot.is_available = False
            booking.time_slot.save()
        
        # If cancelled or completed, make time slot available again
        if new_status in ['cancelled', 'completed']:
            booking.time_slot.is_available = True
            booking.time_slot.save()
        
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
        
        # Get today's bookings
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