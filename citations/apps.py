from django.apps import AppConfig

class CitationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'citations'

    def ready(self):
        from citations import signals as signals
