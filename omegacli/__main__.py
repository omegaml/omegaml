import argparse

import requests
import yaml

from omegacommon.auth import OmegaRestApiAuth
from omegaml import settings
from omegacommon.userconf import get_user_config_from_api, save_userconfig_from_apikey

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
        defaults = settings()
        save_userconfig_from_apikey(defaults.OMEGA_CONFIG_FILE, args.userid,
                                    args.apikey)

