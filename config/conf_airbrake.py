import os

from stackable import StackableSettings


def setup_logger(settings):
    settings['LOGGING']['handlers']['airbrake'] = {
        'level': 'ERROR',
        'class': 'pybrake.LoggingHandler',
    }
    settings['LOGGING']['loggers']['app'] = {
        'handlers': ['airbrake'],
        'level': 'ERROR',
        'propagate': True,
    }


class Config_Airbrake:
    # https://github.com/airbrake/pybrake
    _ab_idkey = os.environ.get('AIRBRAKE_IDKEY', '0:invalid')
    _ab_project_id, _ab_project_key = _ab_idkey.split(':', 1)
    AIRBRAKE = dict(
        project_id=int(_ab_project_id),
        project_key=_ab_project_key,
    )

    StackableSettings.patch_middleware('pybrake.django.AirbrakeMiddleware')
    StackableSettings.patch_func(setup_logger, tuple())
