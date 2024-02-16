import os

from omegaml.server.app import create_app

if __name__ == '__main__':
    port = os.environ.get('PORT')
    app = create_app()
    app.run(host='0.0.0.0', port=port, debug=True)
