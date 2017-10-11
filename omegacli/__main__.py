import argparse
from omegaml import defaults
import yaml

parser = argparse.ArgumentParser(description='omegaml cli')
subparsers = parser.add_subparsers(help='commands')

init_parser = subparsers.add_parser('init', help='initialize')
init_parser.set_defaults(command='init')
init_parser.add_argument('--userid', help='omegaml userid')
init_parser.add_argument('--apikey', help='omegaml apikey')

args = parser.parse_args()

if __name__ == '__main__':
    if args.command == 'init':
        with open(defaults.config_file, 'w') as fconfig:
            # TODO get this config from the server using userid/apikey
            default_config = {
                "OMEGA_CELERY_CONFIG": {
                    "CELERY_MONGODB_BACKEND_SETTINGS": {
                        "taskmeta_collection": "omegaml_taskmeta",
                        "database": "mongodb://localhost:27017/omega"
                    },
                    "CELERY_ACCEPT_CONTENT": [
                        "pickle",
                        "json",
                        "msgpack",
                        "yaml"
                    ]
                },
                "OMEGA_MONGO_URL": "mongodb://localhost:27017/omega",
                "OMEGA_RESULT_BACKEND": "mongodb://localhost:27017/omega",
                "OMEGA_NOTEBOOK_COLLECTION": "ipynb",
                "OMEGA_TMP": "/tmp",
                "OMEGA_MONGO_COLLECTION": "omegaml",
                "OMEGA_BROKER": "amqp://guest@127.0.0.1:5672//"
            }
            yaml.dump(default_config, fconfig, default_flow_style=False)
