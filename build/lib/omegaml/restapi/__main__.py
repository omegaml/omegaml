from omegaml.restapi import PingResource, ModelResource
from omegaml.restapi.app import app, api

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)