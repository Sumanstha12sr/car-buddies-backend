from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Customer, Staff, Vehicle, ChargingStation, Charger,TimeSlot,ChargingBooking,ServiceCategory,Service,Mechanic,ServiceBooking,ServiceReport,CustomerFeedback

class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'user_type', 'is_active', 'is_staff']
    list_filter = ['user_type', 'is_active']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Info', {'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'user_type', 'password1', 'password2', 'is_active')}
        ),
    )
    search_fields = ['email']
    ordering = ['email']

admin.site.register(User, UserAdmin)
admin.site.register(Customer)
admin.site.register(Staff)
admin.site.register(ServiceCategory)
admin.site.register(Service)
admin.site.register(Mechanic)
admin.site.register(ServiceBooking)
admin.site.register(ServiceReport)
admin.site.register(CustomerFeedback)

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['vehicle_name', 'vehicle_number', 'customer', 'vehicle_type', 'is_default']
    list_filter = ['vehicle_type', 'is_default']
    search_fields = ['vehicle_name', 'vehicle_number', 'customer__full_name']

@admin.register(ChargingStation)
class ChargingStationAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'total_chargers', 'available_chargers', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'address']

@admin.register(Charger)
class ChargerAdmin(admin.ModelAdmin):
    list_display = ['charger_name', 'station', 'charger_type', 'power_output', 'status', 'is_available']
    list_filter = ['charger_type', 'status', 'is_available']
    search_fields = ['charger_name', 'station__name']

@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['charger', 'date', 'start_time', 'end_time', 'is_available']
    list_filter = ['date', 'is_available']
    date_hierarchy = 'date'

@admin.register(ChargingBooking)
class ChargingBookingAdmin(admin.ModelAdmin):
    list_display = ['customer', 'vehicle', 'charger', 'booking_date', 'status', 'estimated_cost']
    list_filter = ['status', 'booking_date']
    search_fields = ['customer__full_name', 'vehicle__vehicle_number']
    date_hierarchy = 'booking_date'
    
    actions = ['confirm_bookings', 'complete_bookings', 'cancel_bookings']
    
    def confirm_bookings(self, request, queryset):
        queryset.update(status='confirmed')
    confirm_bookings.short_description = "Confirm selected bookings"
    
    def complete_bookings(self, request, queryset):
        queryset.update(status='completed')
    complete_bookings.short_description = "Mark as completed"
    
    def cancel_bookings(self, request, queryset):
        queryset.update(status='cancelled')
    cancel_bookings.short_description = "Cancel selected bookings"