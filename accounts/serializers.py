from rest_framework import serializers
from .models import User, Customer, Staff
from .models import Vehicle, ChargingStation, Charger, TimeSlot, ChargingBooking
from datetime import datetime, timedelta

class CustomerRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    full_name = serializers.CharField(required=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ['email', 'password', 'password_confirm', 'full_name', 'phone']
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords do not match")
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        full_name = validated_data.pop('full_name')
        phone = validated_data.pop('phone', '')
        
        # Create user - NOW ACTIVE BY DEFAULT
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            user_type='customer',
            is_active=True  # CHANGED: Was False, now True
        )
        
        # Create customer profile
        customer = Customer.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
        )
        
        return user

class CustomerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Customer
        fields = ['email', 'full_name', 'phone']

class StaffSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Staff
        fields = ['email', 'full_name', 'phone', 'employee_id']

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


# Vehicle Serializers
class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            'id', 'vehicle_name', 'vehicle_number', 'vehicle_type',
            'battery_capacity', 'charging_port_type', 'is_default',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class VehicleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            'vehicle_name', 'vehicle_number', 'vehicle_type',
            'battery_capacity', 'charging_port_type', 'is_default'
        ]
    
    def validate_vehicle_number(self, value):
        # Validate vehicle number format (Nepal format)
        value = value.upper().strip()
        if not value:
            raise serializers.ValidationError("Vehicle number is required")
        return value


# Charger Serializers
class ChargerSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    connector_types_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Charger
        fields = [
            'id', 'station_name', 'charger_name', 'charger_type',
            'power_output', 'connector_types', 'connector_types_list',
            'price_per_kwh', 'status', 'is_available'
        ]
    
    def get_connector_types_list(self, obj):
        return [c.strip() for c in obj.connector_types.split(',')]


# Time Slot Serializers
class TimeSlotSerializer(serializers.ModelSerializer):
    charger_name = serializers.CharField(source='charger.charger_name', read_only=True)
    charger_type = serializers.CharField(source='charger.charger_type', read_only=True)
    
    class Meta:
        model = TimeSlot
        fields = [
            'id', 'charger', 'charger_name', 'charger_type',
            'date', 'start_time', 'end_time', 'is_available'
        ]


# Charging Station Serializers
class ChargingStationListSerializer(serializers.ModelSerializer):
    total_chargers = serializers.IntegerField(read_only=True)
    available_chargers = serializers.IntegerField(read_only=True)
    ac_chargers_count = serializers.SerializerMethodField()
    dc_chargers_count = serializers.SerializerMethodField()
    amenities_list = serializers.SerializerMethodField()
    
    class Meta:
        model = ChargingStation
        fields = [
            'id', 'name', 'address', 'latitude', 'longitude',
            'description', 'amenities_list', 'operating_hours',
            'total_chargers', 'available_chargers',
            'ac_chargers_count', 'dc_chargers_count', 'is_active'
        ]
    
    def get_ac_chargers_count(self, obj):
        return obj.chargers.filter(charger_type='AC', is_available=True).count()
    
    def get_dc_chargers_count(self, obj):
        return obj.chargers.filter(charger_type='DC', is_available=True).count()
    
    def get_amenities_list(self, obj):
        if obj.amenities:
            return [a.strip() for a in obj.amenities.split(',')]
        return []


class ChargingStationDetailSerializer(serializers.ModelSerializer):
    chargers = ChargerSerializer(many=True, read_only=True)
    amenities_list = serializers.SerializerMethodField()
    
    class Meta:
        model = ChargingStation
        fields = [
            'id', 'name', 'address', 'latitude', 'longitude',
            'description', 'amenities_list', 'operating_hours',
            'chargers', 'is_active'
        ]
    
    def get_amenities_list(self, obj):
        if obj.amenities:
            return [a.strip() for a in obj.amenities.split(',')]
        return []


# Charging Booking Serializers
class ChargingBookingSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    vehicle_number = serializers.CharField(source='vehicle.vehicle_number', read_only=True)
    vehicle_name = serializers.CharField(source='vehicle.vehicle_name', read_only=True)
    station_name = serializers.CharField(source='charger.station.name', read_only=True)
    charger_name = serializers.CharField(source='charger.charger_name', read_only=True)
    charger_type = serializers.CharField(source='charger.charger_type', read_only=True)
    
    class Meta:
        model = ChargingBooking
        fields = [
            'id', 'customer_name', 'vehicle', 'vehicle_number', 'vehicle_name',
            'charger', 'station_name', 'charger_name', 'charger_type',
            'time_slot', 'booking_date', 'start_time', 'end_time',
            'estimated_energy', 'estimated_cost', 'actual_energy', 'actual_cost',
            'status', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChargingBookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChargingBooking
        fields = [
            'vehicle', 'charger', 'time_slot', 'booking_date',
            'start_time', 'end_time', 'estimated_energy', 'notes'
        ]
    
    def validate(self, data):
        # Check if vehicle belongs to the customer
        customer = self.context['request'].user.customer
        if data['vehicle'].customer != customer:
            raise serializers.ValidationError("This vehicle does not belong to you")
        
        # Check if time slot is available
        if not data['time_slot'].is_available:
            raise serializers.ValidationError("This time slot is not available")
        
        # Check if time slot matches the charger
        if data['time_slot'].charger != data['charger']:
            raise serializers.ValidationError("Time slot does not match the selected charger")
        
        # Check if booking date matches time slot date
        if data['booking_date'] != data['time_slot'].date:
            raise serializers.ValidationError("Booking date does not match time slot date")
        
        return data
    
    def create(self, validated_data):
        # Set customer from request
        validated_data['customer'] = self.context['request'].user.customer
        
        # Calculate estimated cost
        if validated_data.get('estimated_energy'):
            charger = validated_data['charger']
            validated_data['estimated_cost'] = validated_data['estimated_energy'] * charger.price_per_kwh
        
        # Create booking with pending status
        validated_data['status'] = 'pending'
        
        return super().create(validated_data)