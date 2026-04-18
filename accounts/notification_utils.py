"""
notification_utils.py
─────────────────────
Reusable utilities to:
  1. Create in-app Notification records for staff or a specific customer
  2. Send FCM push notifications to staff devices

SUPPORTED notification_type values (used by Flutter to pick icon/colour):

  Staff-side (StaffNotificationsScreen):
    'charging_booking'    → green  EV station icon
    'carwash_booking'     → blue   car wash icon
    'ev_checkup_booking'  → teal   health shield icon
    'bluebook_submission' → purple document icon
    'booking_cancelled'   → red    cancel icon  ← customer cancelled

  Customer-side (NotificationsScreen):
    'booking_confirmed'   → green  check circle
    'booking_completed'   → teal   task_alt
    'booking_cancelled'   → orange cancel   (staff cancelled)
    'booking_rejected'    → red    block
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def notify_customer(user, notification_type: str, title: str, body: str) -> None:
    """
    Creates a single in-app Notification record for a specific customer user.

    Usage:
        from .notification_utils import notify_customer

        notify_customer(
            user=booking.customer.user,
            notification_type='booking_cancelled',
            title='❌ Booking Cancelled by Staff',
            body='Your booking on 06 Apr has been cancelled by our staff.',
        )
    """
    from .models import Notification

    Notification.objects.create(
        user=user,
        title=title,
        body=body,
        notification_type=notification_type,
        is_read=False,
    )
    logger.info(
        f'notify_customer: created "{notification_type}" notification '
        f'for user {user.email}.'
    )


def notify_staff(notification_type: str, title: str, body: str,
                 extra_data: dict | None = None) -> None:
    """
    Creates Notification DB records for ALL staff users and sends
    FCM push notifications to every registered staff device.

    Safe to call even if FCM is not configured — DB notifications
    still get created, only the push is skipped with a warning log.
    """
    # Import here to avoid circular imports
    from .models import FCMToken, Notification
    from django.contrib.auth import get_user_model

    User = get_user_model()

    # ── 1. Fetch all staff users ─────────────────────────────────────────
    staff_users = list(User.objects.filter(
    user_type__in=['staff', 'admin'], is_active=True
))

    if not staff_users:
        logger.info('notify_staff: no active staff users found, skipping.')
        return

    # ── 2. Create in-app Notification for each staff user ────────────────
    notifications_to_create = [
        Notification(
            user=user,
            title=title,
            body=body,
            notification_type=notification_type,
            is_read=False,
        )
        for user in staff_users
    ]
    Notification.objects.bulk_create(notifications_to_create)
    logger.info(
        f'notify_staff: created {len(notifications_to_create)} notifications '
        f'of type "{notification_type}".'
    )

    # ── 3. Send FCM push to all staff devices ────────────────────────────
    fcm_tokens = FCMToken.objects.filter(
        user__in=staff_users
    ).values_list('token', flat=True)

    if not fcm_tokens:
        logger.info('notify_staff: no FCM tokens registered for staff users.')
        return

    _send_fcm_multicast(
        tokens=list(fcm_tokens),
        title=title,
        body=body,
        data={
            'notification_type': notification_type,
            **(extra_data or {}),
        },
    )


# ── FCM HTTP v1 sender ───────────────────────────────────────────────────
def _send_fcm_multicast(tokens: list[str], title: str, body: str,
                        data: dict) -> None:
    """
    Sends a multicast FCM push using the Firebase Admin SDK.

    SETUP REQUIRED:
        pip install firebase-admin

        In settings.py add:
            FIREBASE_CREDENTIALS_PATH = '/path/to/serviceAccountKey.json'

        Download serviceAccountKey.json from:
            Firebase Console → Project Settings → Service Accounts
            → Generate new private key
    """
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        # Initialise Firebase app once
        if not firebase_admin._apps:
            cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
            if not cred_path:
                logger.warning(
                    'notify_staff: FIREBASE_CREDENTIALS_PATH not set in '
                    'settings.py — FCM push skipped. In-app notifications '
                    'were still saved to DB.'
                )
                return
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        # Build multicast message (batch up to 500 tokens at a time)
        # Convert all data values to strings (FCM requirement)
        str_data = {k: str(v) for k, v in data.items()}

        for i in range(0, len(tokens), 500):
            batch = tokens[i:i + 500]
            message = messaging.MulticastMessage(
                tokens=batch,
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=str_data,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        channel_id='staff_notifications',
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound='default'),
                    ),
                ),
            )
            response = messaging.send_each_for_multicast(message)
            logger.info(
                f'FCM multicast: {response.success_count} sent, '
                f'{response.failure_count} failed (batch {i // 500 + 1}).'
            )

    except ImportError:
        logger.error(
            'firebase-admin is not installed. Run: pip install firebase-admin'
        )
    except Exception as e:
        logger.error(f'FCM send error: {e}')