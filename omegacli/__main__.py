import argparse

import requests
import yaml

from omegacli.auth import TastypieApiKeyAuth
from omegaml import defaults
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
            auth = TastypieApiKeyAuth(args.userid,
                                      args.apikey)
            url = 'http://omegaml.dokku.me/api/v1/config/'
            #url = 'http://localhost:8000/api/v1/config/'
            resp = requests.get(url, auth=auth)
            fail_msg = ("Not authenticated using --userid {args.userid}"
                        " --apikey {args.apikey}, error was {resp.status_code}, {resp.content}")
            assert resp.status_code == 200, fail_msg.format(**locals())
            configs = resp.json()
            config = configs['objects'][0]['data']
            yaml.safe_dump(config, fconfig, default_flow_style=False)
            print("Config is in {defaults.config_file}".format(**locals()))
