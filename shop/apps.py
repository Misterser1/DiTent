from django.apps import AppConfig


class ShopConfig(AppConfig):
    verbose_name = 'DiTent'
    name = 'shop'

    def ready(self):
        from . import checks  # noqa: F401
