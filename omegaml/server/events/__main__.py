from omegaml.server.events import create_app

if __name__ == '__main__':
    app = create_app()
    app.run(port=5001, threaded=True, debug=True)
