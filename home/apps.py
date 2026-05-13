from django.apps import AppConfig
import os

class HomeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "home"

    def ready(self):
        # RUN_MAIN=true chỉ có trong actual server process, không có trong reloader watcher
        if os.environ.get('RUN_MAIN') == 'true':
            from models.processing import _get_model
            _get_model()