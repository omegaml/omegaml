import logging
import os

from flask import Flask
from flask_session import Session

from .ssechat import bp as bp_ssechat
from ..config import CONFIG_MAP
from ..logutil import configure_logging, logutil_flask


def create_app():
    app = Flask(__name__)
    should_debug = os.getenv('DEBUG', '0')[0].lower() in ('1', 'y', 't')
    config = CONFIG_MAP['dev'] if should_debug else CONFIG_MAP['live']
    app.config.from_object(config)
    configure_logging(settings=app.config)
    logutil_flask(app)
    Session(app)
    # disable dump of watchdog DEBUG messages on startup with debug=True
    watchdog_logger = logging.getLogger('watchdog')
    watchdog_logger.setLevel(logging.INFO)
    # register sse endpoints
    app.register_blueprint(bp_ssechat)
    return app
