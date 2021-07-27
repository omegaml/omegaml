import argparse
import omegaml as om
import os
import re
import subprocess
import yaml
from omegaml.client import cli

parser = argparse.ArgumentParser(description='omegaml scripted deploy')
parser.add_argument('--file', dest='deployfile', default='deploy.yml',
                    help='/path/to/deploy.yml')
parser.add_argument('--dry', default=False, action='store_true')
parser.add_argument('--action', default='apply')
parser.add_argument('--select', default='',
                    help='subset of assets to apply')

DIRECT_COMMANDS = ['kubectl', 'shell']
COMMAND_ORDER = 'cloud,kubectl,datasets,scripts,runtime,appingress'

SPECS_CLI_MAP = {
    'scripts': 'scripts {action} {local} {name} {options}',
    'datasets': 'datasets {action} {local} {name} {options}',
    'models': 'models {action} {local} {name} {options}',
    'jobs': 'jobs {action} {local} {name} {options}',
    'runtime': 'runtime {action} {kind} {name} {options}',
    'cloud': 'cloud {action} {kind} --specs "{specs}" {options}',
    'kubectl': 'kubectl {command}'
}

ACTION_MAP = {
    'apply': {
        '_default_': 'put',
        'runtime': 'restart',
        'cloud': 'update',
    },
    'add': {
        '_default_': 'put',
        'runtime': 'restart',
        'cloud': 'install',
    },
    'remove': {
        '_default_': 'drop',
        'runtime': 'status',
        'cloud': 'remove',
    },
}

METADATA_TYPES = ('scripts', 'datasets', 'jobs', 'models')
DEFAULT_VARS = {
    'om-baseapp': "git+https://github.com/omegaml/apps.git#subdirectory=helloworld&egg=helloworld",
}


def process(specs_file, action='plan', dry=False, select=None):
    order = COMMAND_ORDER
    commands = []
    vars = {**os.environ, **DEFAULT_VARS}
    selected = (select or '').split(',')

    def render_vars(d, _doublepass=True, **vars):
        for k, v in d.items():
            if isinstance(v, dict):
                render_vars(v, **vars)
            elif isinstance(v, str):
                d[k] = v.format(**vars)
        if _doublepass:
            render_vars(d, **vars, _doublepass=False)

    def prepare(cmd, item):
        if 'specs' in item:
            item['specs'] = ','.join(f'{k}={v}'
                                     for k, v in item['specs'].items())
        default_action = ACTION_MAP[action].get(cmd, ACTION_MAP[action].get('_default_'))
        item.setdefault('action', default_action)
        item.setdefault('options', '')
        item.setdefault('local', '')
        clicmd = SPECS_CLI_MAP[cmd]
        command = {
            'cmd': cmd,
            'clicmd': clicmd,
            'item': item,
            'depends': item.get('depends'),
            'sequence': item.get('sequence', (len(commands) + 1) * 10),
            'metadata': item.get('metadata'),
        }
        try:
            render_vars(command, **item, **vars)
        except KeyError as e:
            print(f"Variable {e} must be set in {cmd} {item}")
            exit(1)
        commands.append(command)

    def apply_meta(cmd):
        meta = cmd.get('metadata')
        if meta and cmd['cmd'] in METADATA_TYPES:
            if dry:
                print('DRY: metadata update', meta)
            else:
                store = getattr(om, cmd['cmd'])
                s_meta = store.metadata(cmd['item']['name'])
                s_meta.attributes.update(meta)
                s_meta.save()

    def apply():
        sequenced = sorted(commands, key=lambda v: (len(commands) + 1)* 10 if v.get('depends') else v.get('sequence'))
        for cmd in sequenced:
            kind_or_name = cmd['item'].get('name') or cmd['item'].get('kind')
            lookup = '.'.join([v for v in (cmd.get('cmd'), kind_or_name) if v])
            if selected and not any(re.match(s, lookup) for s in selected):
                print(f"ignoring {lookup} because not in {selected}")
                continue
            if cmd['cmd'] not in DIRECT_COMMANDS:
                # om cli
                if dry:
                    print("DRY: om", cmd['clicmd'])
                else:
                    print("INFO: om", cmd['clicmd'])
                    argv = [v for v in cmd['clicmd'].split(' ') if v]
                    cli.main(argv=argv)
                apply_meta(cmd)
            else:
                # shell
                shellcmd = cmd['clicmd']
                if dry:
                    print("DRY: ", shellcmd)
                else:
                    print("INFO: ", shellcmd)
                    subprocess.run(shellcmd, shell=True)

    def load():
        with open(specs_file) as fin:
            deploy_specs = yaml.safe_load(fin)
            try:
                vars_update = {k: v.format(**vars)
                               for k, v in deploy_specs.get('vars', {}).items()}
            except KeyError as e:
                print(f"Variable {e} must be set in vars section")
                exit(1)
            vars.update(vars_update)
            for cmd in order.split(','):
                for item in deploy_specs.get(cmd, []):
                    prepare(cmd, item)

    load()
    apply()


if __name__ == '__main__':
    args = parser.parse_args()
    process(args.deployfile, dry=args.dry, action=args.action, select=args.select)
