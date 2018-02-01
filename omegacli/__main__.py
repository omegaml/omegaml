import argparse

import requests
import yaml

from omegacommon.auth import OmegaRestApiAuth
from omegaml import defaults
from omegacommon.userconf import get_user_config_from_api
parser = argparse.ArgumentParser(description='omegaml cli')
subparsers = parser.add_subparsers(help='commands')

init_parser = subparsers.add_parser('init', help='initialize')
init_parser.set_defaults(command='init')
init_parser.add_argument('--userid', help='omegaml userid')
init_parser.add_argument('--apikey', help='omegaml apikey')
init_parser.add_argument('--url', help='omegaml URL', default=None)

args = parser.parse_args()

if __name__ == '__main__':
    if not hasattr(args, 'command'):
        parser.print_help()
        exit(1)
    if args.command == 'init':
        with open(defaults.config_file, 'w') as fconfig:
            auth = OmegaRestApiAuth(args.userid, args.apikey)
            api_url = args.url
            configs = get_user_config_from_api(auth, api_url=api_url)
            config = configs['objects'][0]['data']
            config['OMEGA_USERID'] = args.userid
            config['OMEGA_APIKEY'] = args.apikey
            yaml.safe_dump(config, fconfig, default_flow_style=False)
            print("Config is in {defaults.config_file}".format(**locals()))
