from django.urls import path
from . import charging_views

urlpatterns = [
    # Vehicle Management
    path('vehicles/', charging_views.get_customer_vehicles, name='get_vehicles'),
    path('vehicles/add/', charging_views.add_vehicle, name='add_vehicle'),
    path('vehicles/<uuid:vehicle_id>/update/', charging_views.update_vehicle, name='update_vehicle'),
    path('vehicles/<uuid:vehicle_id>/delete/', charging_views.delete_vehicle, name='delete_vehicle'),
    path('vehicles/<uuid:vehicle_id>/set-default/', charging_views.set_default_vehicle, name='set_default_vehicle'),
    
    # Charging Stations
    path('stations/', charging_views.get_charging_stations, name='get_stations'),
    path('stations/<uuid:station_id>/', charging_views.get_station_detail, name='station_detail'),
    
    # Chargers & Time Slots
    path('stations/<uuid:station_id>/chargers/', charging_views.get_available_chargers, name='available_chargers'),
    path('chargers/<uuid:charger_id>/time-slots/', charging_views.get_available_time_slots, name='time_slots'),
    
    # Customer Bookings
    path('bookings/create/', charging_views.create_booking, name='create_booking'),
    path('bookings/', charging_views.get_customer_bookings, name='my_bookings'),
    path('bookings/<uuid:booking_id>/', charging_views.get_booking_detail, name='booking_detail'),
    path('bookings/<uuid:booking_id>/cancel/', charging_views.cancel_booking, name='cancel_booking'),
    
    # Staff Endpoints
    path('bookings/all/', charging_views.get_all_bookings_for_staff, name='all_bookings_staff'),
    path('bookings/<uuid:booking_id>/update-status/', charging_views.update_booking_status, name='update_booking_status'),
    path('statistics/', charging_views.get_booking_statistics, name='booking_statistics'),
]