import os

from omegaml.restapi.app import create_app

if __name__ == '__main__':
    port = os.environ.get('OMEGA_WEB_PORT')
    app = create_app()
    app.run(host='0.0.0.0', port=port, debug=True)
