from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Customer, Staff, Vehicle, ChargingStation, Charger, TimeSlot, ChargingBooking

User = get_user_model()


# ==================== AUTH SERIALIZERS ====================

class CustomerRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'Passwords do not match'}
            )
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError(
                {'email': 'Email already registered'}
            )
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        phone = validated_data.pop('phone_number', '')
        full_name = validated_data.pop('full_name')

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            user_type='customer',
            is_active=True,
        )

        Customer.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
        )

        return user


class LoginSerializer(serializers.Serializer):
    """Used by both customer_login and staff_login views"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class CustomerSerializer(serializers.ModelSerializer):
    """Returns customer profile data after login"""
    email = serializers.EmailField(source='user.email', read_only=True)
    user_type = serializers.CharField(source='user.user_type', read_only=True)

    class Meta:
        model = Customer
        fields = [
            'email', 'full_name', 'user_type', 'phone',
        ]


class StaffSerializer(serializers.ModelSerializer):
    """Returns staff profile data after login"""
    email = serializers.EmailField(source='user.email', read_only=True)
    user_type = serializers.CharField(source='user.user_type', read_only=True)

    class Meta:
        model = Staff
        fields = [
            'email', 'full_name', 'user_type',
            'employee_id', 'phone',
        ]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'user_type']


# ==================== VEHICLE SERIALIZERS ====================

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            'id', 'vehicle_name', 'vehicle_number',
            'vehicle_type', 'battery_capacity',
            'charging_port_type', 'is_default', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class VehicleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            'vehicle_name', 'vehicle_number',
            'vehicle_type', 'battery_capacity',
            'charging_port_type', 'is_default',
        ]

    def create(self, validated_data):
        customer = validated_data.get('customer')
        if validated_data.get('is_default', False) and customer:
            Vehicle.objects.filter(
                customer=customer
            ).update(is_default=False)
        return super().create(validated_data)


# ==================== STATION SERIALIZERS ====================

class ChargerSerializer(serializers.ModelSerializer):
    connector_types_list = serializers.SerializerMethodField()

    class Meta:
        model = Charger
        fields = [
            'id', 'charger_name', 'charger_type',
            'power_output', 'connector_types',
            'connector_types_list', 'price_per_kwh',
            'status', 'is_available',
        ]

    def get_connector_types_list(self, obj):
        if obj.connector_types:
            return [c.strip() for c in obj.connector_types.split(',')]
        return []


class ChargingStationListSerializer(serializers.ModelSerializer):
    total_chargers = serializers.SerializerMethodField()
    available_chargers = serializers.SerializerMethodField()
    amenities_list = serializers.SerializerMethodField()

    class Meta:
        model = ChargingStation
        fields = [
            'id', 'name', 'address', 'latitude', 'longitude',
            'operating_hours', 'amenities', 'amenities_list',
            'total_chargers', 'available_chargers', 'is_active',
        ]

    def get_total_chargers(self, obj):
        return obj.chargers.count()

    def get_available_chargers(self, obj):
        return obj.chargers.filter(
            is_available=True,
            status='available'
        ).count()

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
            'operating_hours', 'amenities', 'amenities_list',
            'chargers', 'is_active',
        ]

    def get_amenities_list(self, obj):
        if obj.amenities:
            return [a.strip() for a in obj.amenities.split(',')]
        return []


# ==================== TIME SLOT SERIALIZERS ====================

class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = [
            'id', 'date', 'start_time',
            'end_time', 'is_available',
        ]


# ==================== BOOKING SERIALIZERS ====================

class ChargingBookingSerializer(serializers.ModelSerializer):
    station_name = serializers.SerializerMethodField()
    charger_name = serializers.SerializerMethodField()
    charger_type = serializers.SerializerMethodField()
    vehicle_name = serializers.SerializerMethodField()
    vehicle_number = serializers.SerializerMethodField()
    time_slot_start = serializers.SerializerMethodField()
    time_slot_end = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()

    class Meta:
        model = ChargingBooking
        fields = [
            'id', 'status', 'booking_date',
            'start_time', 'end_time',
            'estimated_energy', 'estimated_cost',
            'actual_energy', 'actual_cost',
            'notes', 'created_at',
            # Related fields
            'station_name',
            'charger_name', 'charger_type',
            'vehicle_name', 'vehicle_number',
            'time_slot_start', 'time_slot_end',
            'customer_name', 'customer_email', 'customer_phone',
        ]

    def get_station_name(self, obj):
        return obj.charger.station.name if obj.charger else None

    def get_charger_name(self, obj):
        return obj.charger.charger_name if obj.charger else None

    def get_charger_type(self, obj):
        return obj.charger.charger_type if obj.charger else None

    def get_vehicle_name(self, obj):
        return obj.vehicle.vehicle_name if obj.vehicle else None

    def get_vehicle_number(self, obj):
        return obj.vehicle.vehicle_number if obj.vehicle else None

    def get_time_slot_start(self, obj):
        return str(obj.time_slot.start_time) if obj.time_slot else None

    def get_time_slot_end(self, obj):
        return str(obj.time_slot.end_time) if obj.time_slot else None

    def get_customer_name(self, obj):
        return obj.customer.full_name if obj.customer else None

    def get_customer_email(self, obj):
        return obj.customer.user.email if obj.customer else None

    def get_customer_phone(self, obj):
        return obj.customer.phone if obj.customer else None


class ChargingBookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChargingBooking
        fields = [
            'charger', 'vehicle', 'time_slot',
            'booking_date', 'estimated_energy', 'notes',
        ]

    def validate(self, data):
        charger = data.get('charger')
        time_slot = data.get('time_slot')
        booking_date = data.get('booking_date')

        if not charger.station.is_active:
            raise serializers.ValidationError(
                {'charger': 'This charging station is not active'}
            )

        if not time_slot.is_available:
            raise serializers.ValidationError(
                {'time_slot': 'This time slot is no longer available'}
            )

        # Prevent double booking
        existing = ChargingBooking.objects.filter(
            charger=charger,
            time_slot=time_slot,
            booking_date=booking_date,
            status__in=['pending', 'confirmed', 'in_progress']
        )
        if existing.exists():
            raise serializers.ValidationError(
                {'time_slot': 'This slot has already been booked'}
            )

        # Check vehicle belongs to this customer
        customer = self.context['request'].user.customer
        if data['vehicle'].customer != customer:
            raise serializers.ValidationError(
                {'vehicle': 'This vehicle does not belong to you'}
            )

        return data

    def create(self, validated_data):
        if validated_data.get('estimated_energy'):
            charger = validated_data['charger']
            validated_data['estimated_cost'] = (
                validated_data['estimated_energy'] * charger.price_per_kwh
            )

        # Get start/end time from time slot
        time_slot = validated_data['time_slot']
        validated_data['start_time'] = time_slot.start_time
        validated_data['end_time'] = time_slot.end_time

        validated_data['customer'] = self.context['request'].user.customer
        validated_data['status'] = 'pending'

        booking = super().create(validated_data)

        # Lock time slot immediately
        time_slot.is_available = False
        time_slot.save()

        return booking