

from django.urls import path
from . import service_views

urlpatterns = [

    # Customer: Browse Services 
    path('categories/',
         service_views.get_service_categories,
         name='service-categories'),

    path('category/<str:category_name>/',
         service_views.get_services_by_category,
         name='services-by-category'),

    # Customer: Bookings
   
    path('bookings/create/',
         service_views.create_service_booking,
         name='create-service-booking'),

    path('bookings/',
         service_views.get_customer_service_bookings,
         name='customer-service-bookings'),

    path('bookings/<uuid:booking_id>/',
         service_views.get_service_booking_detail,
         name='service-booking-detail'),

    path('bookings/<uuid:booking_id>/cancel/',
         service_views.cancel_service_booking,
         name='cancel-service-booking'),

   

    path('bookings/<uuid:booking_id>/report/',
         service_views.get_service_report,
         name='service-report'),

     path('vehicle/<uuid:vehicle_id>/booked-slots/',
     service_views.get_vehicle_booked_slots,
     name='vehicle-booked-slots'),

     path('customer/analytics/',
     service_views.get_customer_analytics,
     name='customer-analytics'),

    #  Staff Bookings 
    path('staff/bookings/',
         service_views.staff_get_all_service_bookings,
         name='staff-service-bookings'),

    path('staff/bookings/<uuid:booking_id>/update-status/',
         service_views.staff_update_service_booking_status,
         name='staff-update-service-status'),

    path('staff/bookings/<uuid:booking_id>/assign-mechanic/',
         service_views.staff_assign_mechanic,
         name='staff-assign-mechanic'),

    path('staff/bookings/<uuid:booking_id>/report/',
         service_views.staff_create_service_report,
         name='staff-create-report'),

    path('staff/mechanics/',
         service_views.staff_get_available_mechanics,
         name='staff-mechanics'),

    path('staff/statistics/',
         service_views.staff_get_service_statistics,
         name='staff-service-statistics'),

     # Blue Book Renewal
path('blue-book/create/',
     service_views.create_blue_book_renewal,
     name='create-blue-book'),

path('blue-book/',
     service_views.get_customer_blue_book_renewals,
     name='customer-blue-book'),

path('staff/blue-book/',
     service_views.staff_get_all_blue_book_renewals,
     name='staff-blue-book'),


     # Staff Mechanics
     
     path('staff/mechanics/all/',
     service_views.staff_get_all_mechanics,
     name='staff-mechanics-all'),
]