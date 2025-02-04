from django.apps import AppConfig


class ArtsearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'artsearch'

    def ready(self):
        from artsearch.src.global_services import initialize_services

        initialize_services()
