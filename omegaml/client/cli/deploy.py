""" omega-ml bulk deployment utility
(c) 2020 one2seven GmbH, Switzerland

Enables deployment of datasets, models, scripts, jobs as well as cloud
resources from a single configuration file. This is currently a separate
utility that will be integrated into the omega-ml cli.

Usage:
    To deploy a complete application, create the deploy.yml as per below
    and run:

    # initial deployment
    $ om runtime deploy --action add

    # subsequent deployments
    $ om runtime deploy

    # select specific parts to deploy
    $ python omdeploy.py --select scripts.apps/helloworld

    # dry run, show commands, do not exeucte
    $ python omdeploy.py --dry

    # deploy.yml (example showing most options, specify required parts only)
      # -- syntax is the equivalent of the om cli, where each command is
      #    a map of <arg>=<value> to specify the command parameters, and where
      #    the command is applied according to the omdeploy --action value
      # -- for example, the datasets entry corresponds to
      #    om datasets put data/mydata.csv mydata
      # -- additional commands include kubectl and shell, which both take
      #    a command: <cmd> entry
      # -- each command can also specify a dependency or a sequence which
      #    denotes the execution sequence
      #    ... depends: scripts => execute only when all scripts have been deployed
      #    ... sequence:
      # -- env variables can be specified as {VARIABLE} in any leaf value
      #    in-file variables can be centralized in a vars: section on top and
      #    referenced the same way, e.g. {var}. Convention: env vars in uppercase,
      #    in-file vars in lowercase
      vars:
         - foo=bar
      datasets:
         - name: mydata
           local: data/mydata.csv
      models:
         - name: mymodel
           local: package.mymodel
      scripts:
         - name: apps/helloworld
           local: ./helloworld
         - name: apps/myservice
           local: {om-baseapp} # om-baseapp is a placeholder for a dummy app
           metadata:
              appdef:
                 image: myimage
                 command: '"/bin/bash", "-c", "start.sh"'
      runtime:
         - action: models
           kind: fit
           name: mymodel
           options: mydata[^y] mydata[y]
         - action: restart
           kind: app
           name: helloworld
         - action: restart
           kind: app
           name: myservice
      cloud:
         # cloud is available in commercial edition only
         - kind: appingress
           specs:
             appname: helloworld
             hostname: www.mydomain.com
           depends: scripts
      kubectl:
          - command: apply -f configmap.yml
      shell:
          - command: curl -v https://www.mydomain.com
            sequence: 9999

"""
import logging

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
parser.add_argument('--action', default='update',
                    help='add, update, remove')
parser.add_argument('--select', default='',
                    help='subset of assets to apply')
parser.add_argument('--specs', default='',
                    help='comma separated list of <var>=<value>[,...]')

DIRECT_COMMANDS = ['kubectl', 'shell']
COMMAND_ORDER = 'cloud,shell,kubectl,datasets,scripts,runtime,appingress'
SEQUENCE_SPACING = 10
SPECS_CLI_MAP = {
    'scripts': 'scripts {action} {local} {name} {options}',
    'datasets': 'datasets {action} {local} {name} {options}',
    'models': 'models {action} {local} {name} {options}',
    'jobs': 'jobs {action} {local} {name} {options}',
    'runtime': 'runtime {kind} {action} {name} {options}',
    'cloud': 'cloud {action} {kind} --specs {specs} {options}',
    'kubectl': 'kubectl {command}',
    'shell': '{command}'
}
ACTION_MAP = {
    'update': {
        '_default_': 'put',
        'runtime': 'restart',
        'cloud': 'update',
    },
    'add': {
        '_default_': 'put',
        'runtime': 'restart',
        'cloud': 'add',
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

module_logger = logging.getLogger(__name__)


def process(specs_file, action='plan', dry=False, select=None, specs=None, cli_logger=None):
    logger = cli_logger or module_logger
    order = COMMAND_ORDER
    commands = []
    vars = dict(action=action, dry=dry, select=select)
    vars.update({**os.environ, **DEFAULT_VARS})
    selected = (select or '').split(',')
    specs = dict([pair.strip().split('=', 1) for pair in specs.split(',')]) if specs else {}

    def render_vars(d, _doublepass=True, **vars):
        for k, v in d.items():
            if isinstance(v, dict):
                render_vars(v, **vars)
            elif isinstance(v, str):
                # remove new lines because cli commands never contain new lines
                d[k] = v.format(**vars).replace('\n', '')
        if _doublepass:
            render_vars(d, **vars, _doublepass=False)

    def prepare(cmd, item):
        if 'specs' in item:
            item['specs'] = ','.join(f'{k}={v}'
                                     for k, v in item['specs'].items())
        if action in ACTION_MAP:
            default_action = ACTION_MAP[action].get(cmd, ACTION_MAP[action].get('_default_'))
        else:
            default_action = action
        item.setdefault('action', default_action)
        item.setdefault('options', '')
        item.setdefault('local', '')
        item.setdefault('kind', '')
        clicmd = SPECS_CLI_MAP[cmd]
        command = {
            'cmd': cmd,
            'clicmd': clicmd,
            'item': item,
            'depends': item.get('depends'),
            'sequence': item.get('sequence', (len(commands) + 1) * SEQUENCE_SPACING),
            'metadata': item.get('metadata'),
        }
        try:
            action_override = {'action': item['action']} if not str(item.get('action')).startswith('{') else {}
            render_vars(command, **{**item, **vars, **specs, **action_override})
        except KeyError as e:
            logger.error(f"Variable {e} must be set in {cmd} {item}")
            exit(1)
        commands.append(command)

    def apply_meta(cmd):
        meta = cmd.get('metadata')
        if meta and cmd['cmd'] in METADATA_TYPES:
            if dry:
                logger.info(f'DRY: metadata update {meta}')
            else:
                store = getattr(om, cmd['cmd'])
                s_meta = store.metadata(cmd['item']['name'])
                s_meta.attributes.update(meta)
                s_meta.save()

    def is_selected(cmd):
        # find items to process
        # -- if selected is specified
        # -- get values for id, name, or kind in each cmd item
        # -- match against selected items (each is a string or re)
        # -- example:
        #    selected=['kubectl.def']
        #    select_keys = ['def', 'xyz'] # id: def, name: xyz
        #    lookup = 'kuebctl.abc', 'kubectl.def', 'kubectl.xyz']
        #    re.match('kubectl.def', 'kubectl.def') => True
        select_from_keys = ['id', 'name', 'kind']
        select_keys = [v for v in [cmd['item'].get(k) for k in select_from_keys] if v]
        select_key = select_keys[0] if select_keys else '*'
        lookup = '.'.join([v for v in (cmd.get('cmd'), select_key) if v])
        return lookup, selected and any(re.match(s, lookup) for s in selected)

    def apply():
        sequenced = sorted(commands,
                           key=lambda v: (len(commands) + 1) * SEQUENCE_SPACING if v.get('depends') else v.get(
                               'sequence'))
        for cmd in sequenced:
            lookup, should_process = is_selected(cmd)
            if not should_process:
                logger.info(f"ignoring {lookup} because not in {selected}")
                continue
            if cmd['cmd'] not in DIRECT_COMMANDS:
                # om cli
                if dry:
                    logger.info(f"DRY: om {cmd['clicmd']}")
                else:
                    logger.info(f"om {cmd['clicmd']}")
                    argv = [v for v in cmd['clicmd'].split(' ') if v]
                    cli.main(argv=argv, logger=logger)
                apply_meta(cmd)
            else:
                # shell
                shellcmd = cmd['clicmd']
                if dry:
                    logger.info(f"DRY: {shellcmd} ")
                else:
                    logger.info(f'{shellcmd}')
                    result = subprocess.run(shellcmd, shell=True, capture_output=True)
                    logger.info(result.stdout)

    def load():
        with open(specs_file) as fin:
            deploy_specs = yaml.safe_load(fin)
            try:
                vars_update = {k: v.format(**vars)
                               for k, v in deploy_specs.get('vars', {}).items()}
            except KeyError as e:
                logger.info(f"Variable {e} must be set in vars section")
                exit(1)
            vars.update(vars_update)
            for cmd in order.split(','):
                for item in deploy_specs.get(cmd, []):
                    prepare(cmd, item)

    load()
    apply()


if __name__ == '__main__':
    args = parser.parse_args()
    process(args.deployfile, dry=args.dry, action=args.action, select=args.select, specs=args.specs)
