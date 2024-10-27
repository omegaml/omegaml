import os
from flask import Flask

import omegaml as om
from omegaml.server.app import create_app

SHOULD_STATUS_CHECK = os.environ.get('OMEGA_STATUS_CHECK', '1').lower() in ('true', '1')

if __name__ == '__main__':
    port = os.environ.get('PORT') or 8000
    host = os.environ.get('HOST') or 'localhost'
    print(f"[INFO] starting omega-ml server at http://{host}:{port}/")
    print(f"[INFO] status check is {'enabled' if SHOULD_STATUS_CHECK else 'disabled'}")
    om.status(wait=True) if SHOULD_STATUS_CHECK else None
    app = Flask(__name__)
    app = create_app(server=app, url_prefix='/apps/dashboard')
    app.run(host=host, port=port, debug=True)
