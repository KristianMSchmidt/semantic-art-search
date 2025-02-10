from django.apps import AppConfig


class ArtsearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'artsearch'

    def ready(self):
        pass
