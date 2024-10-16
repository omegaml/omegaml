import os

import omegaml as om
from omegaml.server.app import create_app

if __name__ == '__main__':
    port = os.environ.get('PORT') or 8000
    host = os.environ.get('HOST') or 'localhost'
    print(f"[INFO] starting omega-ml server at http://{host}:{port}/")
    om.status(wait=True)
    app = create_app()
    app.run(host=host, port=port, debug=True)
