import os

from omegaml.defaults import truefalse
from omegaml.server.events import create_app

if __name__ == '__main__':
    app = create_app()
    debug = truefalse(os.environ.get('DEBUG', '0'))
    app.run(port=5001, threaded=True, debug=debug)
