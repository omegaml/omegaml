import os

from stackable import StackableSettings


class Config_Anymail:
    # mail gun email settings
    # see https://app.mailgun.com/app/domains/mg.omegaml.io
    ANYMAIL = {
        # (exact settings here depend on your ESP...)
        "MAILGUN_API_KEY": os.environ.get('MAILGUN_API_KEY'),
        "MAILGUN_SENDER_DOMAIN": os.environ.get('MAILGUND_SENDER_DOMAIN')
    }
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"  # or sendgrid.EmailBackend, or...
    # if you don't already have this in settings
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', "admin@omegaml.io")
    _addl_apps = ('anymail',)
    StackableSettings.patch_apps(_addl_apps)
