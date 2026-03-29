from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        """
        Called once when Django starts.
        Starts the background scheduler for auto-cancellation.
        """
        import os

        # Only start scheduler in the main process
        # Prevents double-start when Django uses auto-reloader
        if os.environ.get('RUN_MAIN') != 'true':
            return

        from . import scheduler
        scheduler.start()