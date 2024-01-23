from django.apps.config import AppConfig


class OmegaWebApp(AppConfig):
    name = 'omegaweb'
    verbose_name = 'omega|ml web'

    def ready(self):
        # connect signals only when app is ready otherwise we get a
        # ton of deprecation warnings on missing app_label in other apps
        # https://stackoverflow.com/a/29703136
        import omegaweb.handlers # noqa
