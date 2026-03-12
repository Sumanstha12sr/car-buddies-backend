from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'admin')
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = (
        ('customer', 'Customer'),
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    def __str__(self):
        return self.email

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return self.full_name

class Staff(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    employee_id = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return f"{self.full_name} - {self.employee_id}"

# Vehicle Model
class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = (
        ('electric', 'Electric Vehicle'),
        ('hybrid', 'Hybrid Vehicle'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='vehicles')
    vehicle_name = models.CharField(max_length=100)  # e.g., "Tesla Model 3"
    vehicle_number = models.CharField(max_length=20, unique=True)  # e.g., "BA-1-PA-1234"
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES)
    battery_capacity = models.DecimalField(max_digits=5, decimal_places=2, help_text="In kWh")  # e.g., 75.00 kWh
    charging_port_type = models.CharField(max_length=50)  # e.g., "Type 2", "CCS"
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        return f"{self.vehicle_name} - {self.vehicle_number}"
    
    def save(self, *args, **kwargs):
        # If this vehicle is set as default, remove default from other vehicles
        if self.is_default:
            Vehicle.objects.filter(customer=self.customer, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


# Charging Station Model
class ChargingStation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    description = models.TextField(blank=True)
    amenities = models.TextField(blank=True, help_text="Comma-separated amenities: WiFi, Restroom, Cafe")
    operating_hours = models.CharField(max_length=100, default="24/7")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    @property
    def total_chargers(self):
        return self.chargers.count()
    
    @property
    def available_chargers(self):
        return self.chargers.filter(is_available=True).count()


# Charger Model
class Charger(models.Model):
    CHARGER_TYPE_CHOICES = (
        ('AC', 'AC Charger'),
        ('DC', 'DC Fast Charger'),
    )
    
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Under Maintenance'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    station = models.ForeignKey(ChargingStation, on_delete=models.CASCADE, related_name='chargers')
    charger_name = models.CharField(max_length=100)  # e.g., "Charger A1"
    charger_type = models.CharField(max_length=2, choices=CHARGER_TYPE_CHOICES)
    power_output = models.DecimalField(max_digits=5, decimal_places=2, help_text="In kW")  # e.g., 22.00 kW (AC), 150.00 kW (DC)
    connector_types = models.CharField(max_length=200, help_text="Comma-separated: Type 2, CCS, CHAdeMO")
    price_per_kwh = models.DecimalField(max_digits=6, decimal_places=2, help_text="Price in NPR")  # e.g., 15.50
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['charger_type', 'charger_name']
    
    def __str__(self):
        return f"{self.station.name} - {self.charger_name} ({self.charger_type})"


# Time Slot Model
class TimeSlot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    charger = models.ForeignKey(Charger, on_delete=models.CASCADE, related_name='time_slots')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['charger', 'date', 'start_time']
        ordering = ['date', 'start_time']
    
    def __str__(self):
        return f"{self.charger.charger_name} - {self.date} {self.start_time}-{self.end_time}"


# Charging Booking Model
class ChargingBooking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='charging_bookings')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='bookings')
    charger = models.ForeignKey(Charger, on_delete=models.CASCADE, related_name='bookings')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='bookings')
    booking_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    estimated_energy = models.DecimalField(max_digits=5, decimal_places=2, help_text="Estimated kWh", null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=8, decimal_places=2, help_text="Estimated cost in NPR", null=True, blank=True)
    actual_energy = models.DecimalField(max_digits=5, decimal_places=2, help_text="Actual kWh used", null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=8, decimal_places=2, help_text="Actual cost in NPR", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Booking {self.id} - {self.customer.full_name} - {self.booking_date}"
    
    def save(self, *args, **kwargs):
        # Mark time slot as unavailable when booking is confirmed
        if self.status == 'confirmed' and self.time_slot.is_available:
            self.time_slot.is_available = False
            self.time_slot.save()
        
        # Calculate estimated cost if not set
        if not self.estimated_cost and self.estimated_energy:
            self.estimated_cost = self.estimated_energy * self.charger.price_per_kwh
        
        super().save(*args, **kwargs)

# Other Services
class ServiceCategory(models.Model):
    """Car Wash or EV Check — top level category"""
    CATEGORY_CHOICES = (
        ('car_wash', 'Car Wash'),
        ('ev_check', 'EV Check'),
    )
    name = models.CharField(max_length=20, choices=CATEGORY_CHOICES, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.get_name_display()

    class Meta:
        verbose_name_plural = 'Service Categories'


class Service(models.Model):
    """
    Individual services under each category.
    Admin adds/updates these from Django admin panel.

    Examples:
      Car Wash  → Full Wash, Interior Wash, Exterior Wash, Dry Wash
      EV Check  → Quick Checkup, Normal Checkup, Full Diagnostic
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name='services'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, help_text='Price in NPR')
    duration_minutes = models.IntegerField(help_text='Estimated duration in minutes')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.category} — {self.name} (NPR {self.price})'

    class Meta:
        ordering = ['category', 'name']


class Mechanic(models.Model):
    """
    Mechanics for EV Check service.
    Each mechanic is linked to a Staff member.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.OneToOneField(
        Staff,
        on_delete=models.CASCADE,
        related_name='mechanic_profile'
    )
    specialization = models.CharField(
        max_length=200,
        help_text='e.g. Battery, Motor, General EV'
    )
    experience_years = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.staff.full_name} — {self.specialization}'


class ServiceBooking(models.Model):
    """
    A booking for Car Wash or EV Check service.
    Single model handles both service types.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='service_bookings'
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='service_bookings'
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    # Mechanic is only assigned for EV Check bookings
    assigned_mechanic = models.ForeignKey(
        Mechanic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_bookings'
    )
    booking_date = models.DateField()
    preferred_time = models.TimeField(help_text='Customer preferred time')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    notes = models.TextField(blank=True, help_text='Customer notes')
    staff_notes = models.TextField(blank=True, help_text='Internal staff notes')
    estimated_cost = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.service.name} — {self.customer.full_name} — {self.booking_date}'

    def save(self, *args, **kwargs):
        # Auto set estimated cost from service price
        if not self.estimated_cost:
            self.estimated_cost = self.service.price
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']


class ServiceReport(models.Model):
    """
    Report created by staff after EV Check completion.
    Customer can view this to know vehicle health.
    """
    CONDITION_CHOICES = (
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('critical', 'Critical'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        ServiceBooking,
        on_delete=models.CASCADE,
        related_name='report'
    )
    issues_found = models.TextField(
        blank=True,
        help_text='List of issues found during check'
    )
    recommendations = models.TextField(
        blank=True,
        help_text='Recommended actions'
    )
    overall_condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default='good'
    )
    battery_health = models.IntegerField(
        null=True,
        blank=True,
        help_text='Battery health percentage 0-100'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Report — {self.booking} — {self.overall_condition}'


class CustomerFeedback(models.Model):
    """
    Customer feedback after service completion.
    Staff notifies customer to give feedback.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        ServiceBooking,
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    rating = models.IntegerField(
        help_text='Rating from 1 to 5',
        default=5
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Feedback — {self.booking.customer.full_name} — {self.rating}/5'