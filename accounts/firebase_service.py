# accounts/firebase_service.py
import firebase_admin
from firebase_admin import credentials, messaging
import os
import logging

logger = logging.getLogger(__name__)

# ── Initialize Firebase Admin SDK ──────────────────────────────
_firebase_initialized = False

def _init_firebase():
    global _firebase_initialized
    if not _firebase_initialized and not firebase_admin._apps:
        try:
            service_account_path = os.path.join(
                os.path.dirname(__file__),
                'firebase-service-account.json'
            )
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info('✅ Firebase Admin SDK initialized')
        except Exception as e:
            logger.error(f'❌ Firebase init error: {e}')


def send_push_notification(token: str, title: str, body: str,
                           data: dict = None) -> bool:
    """Send a push notification to a single FCM token."""
    _init_firebase()
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    channel_id='car_buddies_channel',
                ),
            ),
        )
        response = messaging.send(message)
        logger.info(f'✅ Notification sent: {response}')
        return True
    except Exception as e:
        logger.error(f'❌ FCM send error: {e}')
        return False


def send_notification_to_user(user, title: str, body: str,
                               notification_type: str,
                               data: dict = None):
    """
    Save notification to DB and send push to all user devices.
    Works for both Customer and Staff users.
    """
    from .models import Notification, FCMToken

    # ── Save to database ───────────────────────────────────────
    Notification.objects.create(
        user=user,
        title=title,
        body=body,
        notification_type=notification_type,
    )

    # ── Send push to all FCM tokens for this user ──────────────
    tokens = FCMToken.objects.filter(user=user).values_list(
        'token', flat=True)

    for token in tokens:
        success = send_push_notification(token, title, body, data)
        if not success:
            # Remove invalid token
            FCMToken.objects.filter(
                user=user, token=token).delete()


def notify_staff_new_booking(booking):
    """Notify all staff when a customer makes a new booking."""
    from .models import Staff
    from django.contrib.auth import get_user_model
    User = get_user_model()

    title = '🔔 New Booking Request'
    body = (
        f'{booking.customer.full_name} booked '
        f'{booking.service.name} on '
        f'{booking.booking_date.strftime("%b %d")}'
    )

    staff_users = User.objects.filter(
        user_type='staff',
        is_active=True
    )
    for user in staff_users:
        # Skip mechanics
        try:
            if hasattr(user.staff, 'mechanic_profile'):
                continue
        except Exception:
            continue
        send_notification_to_user(
            user=user,
            title=title,
            body=body,
            notification_type='booking_request',
        )


def notify_staff_new_charging_booking(booking):
    """Notify all staff when a customer makes a charging booking."""
    from .models import Staff
    from django.contrib.auth import get_user_model
    User = get_user_model()

    title = '⚡ New Charging Booking'
    body = (
        f'{booking.customer.full_name} booked '
        f'{booking.charger.charger_type} charger at '
        f'{booking.charger.station.name} on '
        f'{booking.booking_date.strftime("%b %d")}'
    )

    staff_users = User.objects.filter(
        user_type='staff',
        is_active=True
    )
    for user in staff_users:
        try:
            if hasattr(user.staff, 'mechanic_profile'):
                continue
        except Exception:
            continue
        send_notification_to_user(
            user=user,
            title=title,
            body=body,
            notification_type='booking_request',
        )


def notify_customer_booking_update(booking, new_status):
    """Notify customer when their service booking status changes."""
    status_messages = {
        'confirmed': (
            '✅ Booking Confirmed',
            f'Your {booking.service.name} booking on '
            f'{booking.booking_date.strftime("%b %d")} '
            f'has been confirmed.'
        ),
        'completed': (
            '🎉 Service Completed',
            f'Your {booking.service.name} has been completed '
            f'successfully. Thank you!'
        ),
        'cancelled': (
            '❌ Booking Auto-Cancelled',
            f'Your {booking.service.name} booking was '
            f'automatically cancelled as it was not confirmed '
            f'within 30 minutes.'
        ),
        'rejected': (
            '❌ Booking Rejected',
            f'Your {booking.service.name} booking on '
            f'{booking.booking_date.strftime("%b %d")} '
            f'has been rejected by staff.'
        ),
    }

    if new_status not in status_messages:
        return

    title, body = status_messages[new_status]
    notification_type = (
        'booking_confirmed' if new_status == 'confirmed'
        else 'booking_completed' if new_status == 'completed'
        else 'booking_cancelled' if new_status == 'cancelled'
        else 'booking_rejected'
    )

    send_notification_to_user(
        user=booking.customer.user,
        title=title,
        body=body,
        notification_type=notification_type,
    )


def notify_customer_charging_update(booking, new_status):
    """Notify customer when their charging booking status changes."""
    status_messages = {
        'confirmed': (
            '✅ Charging Booking Confirmed',
            f'Your {booking.charger.charger_type} charging slot at '
            f'{booking.charger.station.name} on '
            f'{booking.booking_date.strftime("%b %d")} '
            f'has been confirmed.'
        ),
        'completed': (
            '🎉 Charging Completed',
            f'Your charging session at '
            f'{booking.charger.station.name} '
            f'has been completed successfully.'
        ),
        'cancelled': (
            '❌ Charging Booking Auto-Cancelled',
            f'Your charging booking at '
            f'{booking.charger.station.name} was '
            f'automatically cancelled as it was not confirmed '
            f'within 30 minutes.'
        ),
        'rejected': (
            '❌ Charging Booking Rejected',
            f'Your charging booking on '
            f'{booking.booking_date.strftime("%b %d")} '
            f'has been rejected by staff.'
        ),
    }

    if new_status not in status_messages:
        return

    title, body = status_messages[new_status]
    notification_type = (
        'booking_confirmed' if new_status == 'confirmed'
        else 'booking_completed' if new_status == 'completed'
        else 'booking_cancelled' if new_status == 'cancelled'
        else 'booking_rejected'
    )

    send_notification_to_user(
        user=booking.customer.user,
        title=title,
        body=body,
        notification_type=notification_type,
    )


def notify_all_customers_new_service(service):
    """Notify all customers when admin adds a new service."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    title = '🆕 New Service Available'
    body = (
        f'{service.name} is now available! '
        f'Price: NPR {service.price}. Book now.'
    )

    customer_users = User.objects.filter(
        user_type='customer',
        is_active=True
    )
    for user in customer_users:
        send_notification_to_user(
            user=user,
            title=title,
            body=body,
            notification_type='new_service',
        )