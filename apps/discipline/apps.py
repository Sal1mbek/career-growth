from django.apps import AppConfig


class DisciplineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.discipline'
    verbose_name = 'Поощрения/Взыскания'

    def ready(self):
        from . import signals # noqa
