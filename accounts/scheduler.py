# accounts/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta, timezone as dt_timezone
import logging

logger = logging.getLogger(__name__)


def auto_cancel_pending_bookings():
    """
    Runs every 5 minutes.
    Cancels any booking (charging, car wash, EV check)
    that has been pending for more than 30 minutes.
    """
    from .models import ChargingBooking, ServiceBooking

    # Use UTC datetime directly — avoids Django timezone issues in threads
    now = datetime.now(dt_timezone.utc)
    cutoff_time = now - timedelta(minutes=30)

    logger.info(f'[Auto-Cancel] Running job at {now.strftime("%Y-%m-%d %H:%M:%S")} UTC')
    logger.info(f'[Auto-Cancel] Cancelling bookings created before {cutoff_time.strftime("%Y-%m-%d %H:%M:%S")} UTC')

    try:
        # ── Auto-cancel pending charging bookings ────────────────
        expired_charging = ChargingBooking.objects.filter(
            status='pending',
            created_at__lte=cutoff_time
        )

        cancelled_charging_count = 0
        for booking in expired_charging:
            try:
                booking.status = 'cancelled'
                booking.save()

                # Free up the time slot
                other_active = ChargingBooking.objects.filter(
                    time_slot=booking.time_slot,
                    status__in=['pending', 'confirmed', 'in_progress']
                ).exclude(id=booking.id)

                if not other_active.exists():
                    booking.time_slot.is_available = True
                    booking.time_slot.save()

                cancelled_charging_count += 1
                logger.info(f'[Auto-Cancel] Cancelled charging booking {booking.id}')

            except Exception as e:
                logger.error(f'[Auto-Cancel] Error cancelling charging booking {booking.id}: {e}')

        # ── Auto-cancel pending service bookings ─────────────────
        expired_services = ServiceBooking.objects.filter(
            status='pending',
            created_at__lte=cutoff_time
        )

        cancelled_service_count = 0
        for booking in expired_services:
            try:
                booking.status = 'cancelled'
                booking.save()
                cancelled_service_count += 1
                logger.info(f'[Auto-Cancel] Cancelled service booking {booking.id}')
            except Exception as e:
                logger.error(f'[Auto-Cancel] Error cancelling service booking {booking.id}: {e}')

        # ── Summary ──────────────────────────────────────────────
        total = cancelled_charging_count + cancelled_service_count
        if total > 0:
            logger.info(
                f'[Auto-Cancel] Done — cancelled {cancelled_charging_count} charging '
                f'+ {cancelled_service_count} service bookings'
            )
        else:
            logger.info('[Auto-Cancel] Done — no expired pending bookings found')

    except Exception as e:
        logger.error(f'[Auto-Cancel] Job failed with error: {e}')


# ── Scheduler instance ───────────────────────────────────────────
_scheduler = None


def start():
    """Start the background scheduler"""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone='UTC')

    _scheduler.add_job(
        auto_cancel_pending_bookings,
        trigger=IntervalTrigger(minutes=5),
        id='auto_cancel_bookings',
        name='Auto-cancel pending bookings after 30 mins',
        replace_existing=True,
        misfire_grace_time=60,
    )

    _scheduler.start()
    logger.info('[Scheduler] Auto-cancel scheduler started — runs every 5 minutes')


def stop():
    """Stop the scheduler gracefully"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info('[Scheduler] Scheduler stopped')
