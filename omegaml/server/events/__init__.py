import logging

from flask import Flask

from .ssechat import bp as bp_ssechat


def create_app():
    app = Flask(__name__)
    # disable dump of watchdog DEBUG messages on startup with debug=True
    watchdog_logger = logging.getLogger('watchdog')
    watchdog_logger.setLevel(logging.INFO)
    # register sse endpoints
    app.register_blueprint(bp_ssechat)
    return app
