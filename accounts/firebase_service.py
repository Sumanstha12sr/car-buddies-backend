# accounts/firebase_service.py
"""
firebase_service.py
───────────────────
RULE: This file is responsible for FCM PUSH ONLY.
      All Notification DB record creation must go through notification_utils.py.
      Never call Notification.objects.create() or send_notification_to_user()
      from the scheduler or views — use the helpers at the bottom of this file
      (notify_customer_booking_update / notify_customer_charging_update) which
      call notification_utils.notify_customer() for the DB write and then
      separately fire the FCM push. This prevents duplicates.
"""
import firebase_admin
from firebase_admin import credentials, messaging
import os
import logging

logger = logging.getLogger(__name__)

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


# ── Low-level FCM push (no DB write) ─────────────────────────────────────────

def send_push_notification(token: str, title: str, body: str,
                           data: dict = None) -> bool:
    """Send FCM push to a single token. Does NOT write to DB."""
    _init_firebase()
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
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
        logger.info(f'✅ FCM push sent: {response}')
        return True
    except Exception as e:
        logger.error(f'❌ FCM send error: {e}')
        return False


def send_fcm_push_to_user(user, title: str, body: str, data: dict = None):
    """
    Send FCM push to ALL devices of a user. Does NOT write to DB.
    Call this AFTER notification_utils.notify_customer() has saved the DB record.
    """
    from .models import FCMToken
    tokens = FCMToken.objects.filter(user=user).values_list('token', flat=True)
    for token in tokens:
        success = send_push_notification(token, title, body, data)
        if not success:
            FCMToken.objects.filter(user=user, token=token).delete()


# ── DEPRECATED — kept only so old call sites don't crash immediately ─────────
# Do NOT call this from new code. It writes to DB AND sends FCM which causes
# duplicates when the caller also calls notify_customer() from notification_utils.
def send_notification_to_user(user, title: str, body: str,
                               notification_type: str, data: dict = None):
    """
    DEPRECATED: writes to DB + sends FCM.
    Replace all callers with:
      notify_customer(user, notification_type, title, body)   ← DB only
      send_fcm_push_to_user(user, title, body)                ← FCM only
    Left here temporarily to avoid import errors during migration.
    """
    logger.warning(
        'send_notification_to_user() is deprecated — use notify_customer() '
        '+ send_fcm_push_to_user() separately to avoid duplicate notifications.'
    )
    from .notification_utils import notify_customer
    notify_customer(user=user, notification_type=notification_type,
                    title=title, body=body)
    send_fcm_push_to_user(user, title, body, data)


# ── Staff new-booking notifiers ───────────────────────────────────────────────
# These are ONLY called from places that do NOT also call notify_staff().
# If you already call notify_staff() from notification_utils, do NOT also
# call these — pick one and stick to it. The views.py already uses
# notify_staff() from notification_utils, so these are here only for
# any legacy call sites.

def notify_staff_new_booking(booking):
    """
    LEGACY — views.py already calls notify_staff() from notification_utils.
    Only use this if the caller does NOT call notify_staff() itself.
    """
    from django.contrib.auth import get_user_model
    from .notification_utils import notify_staff
    User = get_user_model()

    notify_staff(
        notification_type='carwash_booking',
        title='🔔 New Booking Request',
        body=(
            f'{booking.customer.full_name} booked '
            f'{booking.service.name} on '
            f'{booking.booking_date.strftime("%b %d")}'
        ),
        extra_data={'booking_id': str(booking.id)},
    )


def notify_staff_new_charging_booking(booking):
    """
    LEGACY — views.py already calls notify_staff() from notification_utils.
    Only use this if the caller does NOT call notify_staff() itself.
    """
    from .notification_utils import notify_staff

    notify_staff(
        notification_type='charging_booking',
        title='⚡ New Charging Booking',
        body=(
            f'{booking.customer.full_name} booked '
            f'{booking.charger.charger_type} charger at '
            f'{booking.charger.station.name} on '
            f'{booking.booking_date.strftime("%b %d")}'
        ),
        extra_data={'booking_id': str(booking.id)},
    )


# ── Customer status-change notifiers (DB + FCM, single source of truth) ──────
# These are the ONLY functions that should notify customers about booking
# status changes. The scheduler and views must call ONLY these — never call
# notify_customer() separately afterwards.

def notify_customer_booking_update(booking, new_status):
    """
    Notify customer of service booking (car wash / EV check-up) status change.
    Writes ONE DB record via notify_customer() then sends FCM push.
    Do NOT call notify_customer() again after calling this.
    """
    from .notification_utils import notify_customer

    status_messages = {
        'confirmed': (
            'booking_confirmed',
            '✅ Booking Confirmed',
            f'Your {booking.service.name} booking on '
            f'{booking.booking_date.strftime("%b %d")} has been confirmed.',
        ),
        'completed': (
            'booking_completed',
            '🎉 Service Completed',
            f'Your {booking.service.name} has been completed successfully. Thank you!',
        ),
        'cancelled': (
            'booking_cancelled',
            '❌ Booking Auto-Cancelled',
            f'Your {booking.service.name} booking was automatically cancelled '
            f'as it was not confirmed within 30 minutes.',
        ),
        'rejected': (
            'booking_rejected',
            '❌ Booking Rejected',
            f'Your {booking.service.name} booking on '
            f'{booking.booking_date.strftime("%b %d")} has been rejected by staff.',
        ),
    }

    if new_status not in status_messages:
        return

    notification_type, title, body = status_messages[new_status]

    # ── Single DB write ───────────────────────────────────────
    notify_customer(
        user=booking.customer.user,
        notification_type=notification_type,
        title=title,
        body=body,
    )
    # ── Single FCM push ───────────────────────────────────────
    send_fcm_push_to_user(
        user=booking.customer.user,
        title=title,
        body=body,
        data={'notification_type': notification_type,
              'booking_id': str(booking.id)},
    )


def notify_customer_charging_update(booking, new_status):
    """
    Notify customer of charging booking status change.
    Writes ONE DB record via notify_customer() then sends FCM push.
    Do NOT call notify_customer() again after calling this.
    """
    from .notification_utils import notify_customer

    status_messages = {
        'confirmed': (
            'booking_confirmed',
            '✅ Charging Booking Confirmed',
            f'Your {booking.charger.charger_type} charging slot at '
            f'{booking.charger.station.name} on '
            f'{booking.booking_date.strftime("%b %d")} has been confirmed.',
        ),
        'completed': (
            'booking_completed',
            '🎉 Charging Completed',
            f'Your charging session at {booking.charger.station.name} '
            f'has been completed successfully.',
        ),
        'cancelled': (
            'booking_cancelled',
            '❌ Charging Booking Auto-Cancelled',
            f'Your charging booking at {booking.charger.station.name} was '
            f'automatically cancelled as it was not confirmed within 30 minutes.',
        ),
        'rejected': (
            'booking_rejected',
            '❌ Charging Booking Rejected',
            f'Your charging booking on '
            f'{booking.booking_date.strftime("%b %d")} has been rejected by staff.',
        ),
    }

    if new_status not in status_messages:
        return

    notification_type, title, body = status_messages[new_status]

    # ── Single DB write ───────────────────────────────────────
    notify_customer(
        user=booking.customer.user,
        notification_type=notification_type,
        title=title,
        body=body,
    )
    # ── Single FCM push ───────────────────────────────────────
    send_fcm_push_to_user(
        user=booking.customer.user,
        title=title,
        body=body,
        data={'notification_type': notification_type,
              'booking_id': str(booking.id)},
    )


def notify_all_customers_new_service(service):
    """Notify all customers when a new service is added."""
    from django.contrib.auth import get_user_model
    from .notification_utils import notify_customer
    User = get_user_model()

    title = '🆕 New Service Available'
    body = (
        f'{service.name} is now available! '
        f'Price: NPR {service.price}. Book now.'
    )

    for user in User.objects.filter(user_type='customer', is_active=True):
        notify_customer(user=user, notification_type='new_service',
                        title=title, body=body)
        send_fcm_push_to_user(user, title, body)