import pandas as pd
import requests
import subprocess
from datetime import datetime, timedelta
from tabulate import tabulate
from time import sleep

from omegaml import mongoshim
from omegaml.client.auth import AuthenticationEnv
from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class CloudCommandBase(CommandBase):
    """
    Usage:
      om cloud login [<userid>] [<apikey>] [<qualifier>] [options]
      om cloud config [show] [--services] [options]
      om cloud (add|update|remove) <kind> [--specs <specs>] [options]
      om cloud status [runtime|pods|nodes|storage] [options]
      om cloud log <pod> [--since <time>] [options]
      om cloud database [backup|restore] [--archive <file>] [--mongo-args <args>] [--dry] [options]
      om cloud metrics [<metric_name>] [--since <time>] [--start <start>] [--end <end>] [--step <step>] [--plot] [options]

    Options:
      --userid=USERID     the userid at hub.omegaml.io (see account profile)
      --apikey=APIKEY     the apikey at hub.omegaml.io (see account profile)
      --apiurl=URL        the cloud URL [default: https://hub.omegaml.io]
      --qualifier=VALUE   the account qualifier [default: default]
      --count=NUMBER      how many instances to set up [default: 1]
      --node-type=TYPE    the type of node [default: small]
      --specs=SPECS       the service specifications as "key=value[,...]"
      --since=TIME        recent log time, defaults to 5m (5 minutes)
      --start=DATETIME    start datetime of range query
      --end=DATETIME      end datetime of range query
      --step=UNIT         step in seconds or duration unit (s=seconds, m=minutes)
      --plot              if specified use plotext library to plot (preliminary)
      --provider=VALUE    the cloud provider, exo/azu/aws
      --archive=VALUE     name of mongodb archive file
      --mongo-args=VALUE  mongodump/mongorestore options
      --dry               print mongodump/mongorestore commands, do not execute
      --services          print services URIs

    Description:
      om cloud is available for the omega|ml managed service at https://hub.omegaml.io

      Logging in
      ----------

      $ om cloud login <userid> <apikey>

      Showing the configuration
      -------------------------

      $ om cloud config

      Building a cluster
      ------------------

      Set up a cluster

      $ om cloud add nodepool --specs "node-type=<node-type>,role=worker,size=1"
      $ om cloud add runtime --specs "role=worker,label=worker,size=1"

      Switch nodes on and off

      $ om cloud update worker --specs "node-name=<name>,scale=0" # off
      $ om cloud update worker --specs "node-name=<name>,scale=1" # on

      Using Metrics
      -------------

      The following metrics are available

      * node-cpu-usage      node cpu usage in percent
      * node-memory-usage   node memory usage in percent
      * node-disk-uage      node disk usage in percent
      * pod-cpu-usage       pod cpu usage in percent
      * pod-memory-usage    pod memory usage in bytes

      Get the specific metrics as follows, e.g.

      $ om cloud metrics node-cpu-usage
      $ om cloud metrics pod-cpu-usage --since 30m
      $ om cloud metrics pod-memory-usage --start 20dec2020T0100 --end20dec2020T0800
    """
    command = 'cloud'

    @property
    def om(self):
        if not hasattr(self, '_om'):
            without_config = ('config', 'login')
            require_config = not any(self.args.get(k) for k in without_config)
            self._om = get_omega(self.args, require_config=require_config)
        return self._om

    def login(self):
        userid = self.args.get('<userid>') or self.args.get('--userid')
        apikey = self.args.get('<apikey>') or self.args.get('--apikey')
        qualifier = self.args.get('<qualifier>') or 'default'
        api_url = self.args.get('--apiurl')
        configfile = self.args.get('--config') or 'config.yml'
        if not userid:
            userid = self.ask('Userid:')
        if not apikey:
            apikey = self.ask('Apikey:')
        auth_env = AuthenticationEnv().secure()
        auth_env.save_userconfig_from_apikey(configfile, userid, apikey, qualifier=qualifier,
                                             api_url=api_url)

    def config(self):
        om = self.om
        config_file = om.defaults.OMEGA_CONFIG_FILE
        if config_file is None:
            config_file = print("No configuration file identified, assuming defaults")
        # print config
        services = self.args.get('--services')
        restapi_url = getattr(om.defaults, 'OMEGA_RESTAPI_URL', 'not configured')
        runtime_url = om.runtime.celeryapp.conf['BROKER_URL']
        mongo_url = mongoshim.mongo_url(om)
        userid = getattr(om.defaults, 'OMEGA_USERID', '(missing)')
        qualifier = getattr(om.defaults, 'OMEGA_QUALIFIER', 'default')
        self.logger.info('Config file: {config_file}'.format(**locals()))
        self.logger.info('Qualifier: {qualifier}'.format(**locals()))
        self.logger.info('User id: {userid}'.format(**locals()))
        self.logger.info(f'REST API URL: {restapi_url}')
        if services:
            self.logger.info('Services:')
            self.logger.info(f'  Runtime broker: {runtime_url}')
            self.logger.info(f'  MongoDB: {mongo_url}')

    def add(self):
        command_url = self._issue_command('install')

    def update(self):
        self._issue_command('update')

    def remove(self):
        self._issue_command('uninstall')

    def _issue_command(self, phase):
        om = self.om
        offering = self.args.get('<kind>')
        size = self.args.get('--count')
        node_type = self.args.get('--node-type')
        specs = self.args.get('--specs')
        user = getattr(om.defaults, 'OMEGA_USERID')
        default_specs = f"size={size},node-type={node_type},provider={self._provider}"
        params = specs or default_specs
        if 'provider=' not in params:
            params = f'provider={self._provider},{params}'
        data = {
            'offering': offering,
            'user': user,
            'phase': phase,
            'params': params,
        }
        command = self._request_service_api(om, 'post', service='command', data=data)
        self._wait_service_command(om, command)

    def _request_service_api(self, om, method, service=None, data=None, uri=None):
        """
        call a service API for a given omega instance

        Args:
            om (Omega): the omega instance, must be authenticated to the cloud
            method (str): the method verb (CREATE, GET, POST, UPDATE, DELETE)
            service (str): the name of the service endpoint as in /api/service/<name>
            data (dict): the data to send

        Returns:
            The response json
        """
        restapi_url = getattr(om.defaults, 'OMEGA_RESTAPI_URL', 'not configured')
        uri = uri or '/admin/api/v2/service/{service}'.format(**locals())
        service_url = '{restapi_url}{uri}'.format(**locals())
        auth = self._restapi_auth()
        method = getattr(requests, method)
        resp = method(service_url, json=data, auth=auth)
        resp.raise_for_status()
        if resp.status_code == requests.codes.created:
            # always request the actual object
            url = resp.headers['Location']
            if not url.startswith(restapi_url):
                url = f'{restapi_url}{url}'
            resp = requests.get(url, auth=auth)
            resp.raise_for_status()
        return resp.json()

    def _wait_service_command(self, om, command):
        """
        wait until the service command status is completed or failed

        Args:
            command (dict): the command object as returned by the service api

        Returns:

        """
        import tqdm
        with tqdm.tqdm(unit='s', total=30) as progress:
            while True:
                progress.update(1)
                uri = command.get('resource_uri')
                data = self._request_service_api(om, 'get', uri=uri)
                status = data.get('status')
                if int(status) > 1:
                    break
                sleep(1)
        if status == '5':
            self.logger.info("Ok, done.")
        else:
            msg = "Error {status} occurred on {uri}".format(**locals())
            self.logger.error(msg)

    def status(self):
        # self.status_nodes()
        kinds = ('runtime', 'pods', 'nodes', 'storage')
        om = self.om
        auth = self._restapi_auth()
        for kind in (filter(lambda k: self.args.get(k), kinds)):
            status_meth = getattr(self, f'status_{kind}')
            status_meth(kind, auth)
            break
        else:
            print(f"status is available for {kinds}")

    def metrics(self):
        # available metrics
        metrics = ('node_cpu_usage', 'node_memory_usage', 'node_disk_usage',
                   'pod_memory_usage', 'pod_cpu_usage')
        # column in prom2df dataframe for given metric group
        metric_group_column = {
            'node': 'node',
            'pod': 'pod_name',
        }
        metric_name = (self.args.get('<metric_name>') or '').replace('-', '_')
        since = self.args.get('--since') or None
        start = self.args.get('--start') or None
        end = self.args.get('--end') or None
        step = self.args.get('--step') or None
        should_plot = self.args.get('--plot')
        # check if we have a valid metric
        if metric_name in metrics:
            # get default range, if any
            if since:
                if any(since.endswith(v) for v in 'hms'):
                    # a relative time spec
                    unit = dict(h='hours', m='minutes', s='seconds').get(since[-1])
                    delta = int(since[0:-1])
                    start = datetime.utcnow() - timedelta(**{unit: delta})
                else:
                    # absolute time
                    start = pd.to_datetime(since, utc=True)
            if start:
                start = pd.to_datetime(start, utc=True)
            if end:
                end = pd.to_datetime(end, utc=True)
            if start and not end:
                end = datetime.utcnow()
            if end and not start:
                start = (end - timedelta(minutes=10)).isoformat()
            if (start or end) and not step:
                step = '5m'
            # query
            om = self.om
            auth = self._restapi_auth()
            data = self._get_metric(metric_name, auth, start=start, end=end, step=step)
            try:
                df = prom2df(data['objects'], metric_name)
            except:
                print("No data could be found. Check the time range.")
                return
            if should_plot:
                import plotext as plx
                # as returned by plx.get_colors
                colors = 'red', 'green', 'yellow', 'organge', 'blue', 'violet', 'cyan'
                metric_group = metric_group_column[metric_name.split('_', 1)[0]]
                for i, (g, gdf) in enumerate(df.groupby(metric_group)):
                    x = range(0, len(gdf))
                    y = gdf['value'].values
                    plx.plot(x, y, line_color=colors[i])
                plx.show()
            else:
                print(tabulate(df, headers='keys'))
        else:
            print("Available metrics:", metrics)

    @property
    def _provider(self):
        return self.args.get('--provider') or ''

    def _get_metric(self, name, auth, **query):
        url = f'https://hub.omegaml.io/apps/omops/dashboard/api/v1/metrics/{name}?provider={self._provider}'
        resp = requests.get(url, auth=auth, params=query)
        data = resp.json()
        return data

    def _get_status(self, kind, auth):
        url = f'https://hub.omegaml.io/apps/omops/dashboard/api/v1/status/{kind}?provider={self._provider}'
        resp = requests.get(url, auth=auth)
        data = resp.json()
        return data

    def _get_logs(self, podname, since, auth):
        url = f'https://hub.omegaml.io/apps/omops/dashboard/api/v1/logs/{podname}?since={since}&provider={self._provider}'
        resp = requests.get(url, auth=auth)
        data = resp.json()
        return data

    def status_runtime(self, kind, auth):
        data = self._get_status(kind, auth)
        active_tasks = data['objects'][0].get('active') or {}
        queues = data['objects'][0]['queues']
        workers = [{'worker': k,
                    'tasks': len(v),
                    'labels': ','.join(q['name']
                                       for q in queues.get(k, [])
                                       # filter amq internal queues
                                       if not q['name'].startswith('amq.')),
                    } for k, v in active_tasks.items()]
        if workers:
            print(tabulate(workers, headers='keys', showindex=False))
        else:
            print("No runtime workers found.")

    def status_pods(self, kind, auth):
        data = self._get_status(kind, auth)
        pods = data.get('objects')
        df = pd.DataFrame.from_dict(pods)
        print(tabulate(df, headers='keys', showindex=False))

    def status_nodes(self, kind, auth):
        data = self._get_status(kind, auth)
        nodes = data.get('objects')
        df = pd.DataFrame.from_dict(nodes)

        def convert_units(v, to_unit='Mi'):
            # convert a value like '452456Ki' to '452Mi'
            # https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
            CONVERSION = {
                'Ki': 1024,
                'Mi': 1024 ** 2,
            }
            if v[-2:] in CONVERSION:
                value, unit = int(v[0:-2]), v[-2:]
                value = int(value * CONVERSION[unit] * 1 / CONVERSION[to_unit])
            else:
                # assume bytes
                value = int(v) * 1
                to_unit = ''
            return f'{value}{to_unit}'

        def node_summary(row):
            capacity = {k: convert_units(v) for k, v in row['capacity'].items()}
            status = row['status']
            row['cpu'] = capacity['cpu']
            row['memory'] = f"{capacity['memory']}"
            row['disk'] = f"{capacity['ephemeral-storage']}"
            row['status'] = 'running' if status['Ready'] == 'True' else 'not ready'
            return row

        df = df.apply(node_summary, axis=1)
        cols = 'name,status,role,cpu,memory,disk'.split(',')
        print(tabulate(df[cols], headers='keys', showindex=False))

    def status_storage(self, kind, auth):
        data = self._get_status('dbsize', auth)
        dbsize = data.get('objects')
        df = pd.DataFrame([dbsize])
        cols = ['kind', 'size', 'status']
        print(tabulate(df[cols], headers='keys', showindex=False))

    def log(self):
        om = self.om
        podname = self.args.get('<pod>') or 'missing'
        since = self.args.get('--since') or '5m'
        auth = self._restapi_auth()
        data = self._get_logs(podname, since, auth)
        entries = data.get('entries')
        print(entries)

    def database(self):
        om = self.om
        userid = getattr(om.defaults, 'OMEGA_USERID', 'omegaml')
        restore = self.args.get('restore')
        backup = self.args.get('backup')
        archive = self.args.get('--archive')
        options = self.args.get('--mongo-args') or ''
        dry = self.args.get('--dry')
        nowdt = datetime.utcnow().isoformat()
        mongo_url = mongoshim.mongo_url(om)
        path = archive or f'{userid}-{nowdt}.mongodump.archive'
        dump_cmd = f'mongodump --uri {mongo_url} --gzip --archive={path} {options}'
        restore_cmd = f'mongorestore --uri {mongo_url} --gzip --archive={path} --drop {options}'
        cmd = dump_cmd if backup else restore_cmd
        if restore:
            answer = self.ask(f"Are you sure to restore to {mongo_url} from {path}?", options="Yes,No")
            if not answer.lower().startswith('y'):
                print("*** aborted")
                return
        print(f"Running {cmd}")
        if not dry:
            result = subprocess.run(cmd.strip().split(' '))
            print(result)

    def _restapi_auth(self):
        return AuthenticationEnv.active().get_restapi_auth(om=self.om)


def prom2df(data, metric_name):
    """ convert prom response to pandas dataframe
    """
    import pandas as pd
    def parse_vector(metrics):
        for item in metrics:
            data = item['metric']
            values = [item.get('value')] if 'value' in item else item.get('values')
            for ts, value in values:
                entry = dict(**data, ts=ts, value=float(value))
                yield entry

    metrics = data['data']['result']
    df = pd.DataFrame(parse_vector(metrics))
    df['ts'] = pd.to_datetime(df['ts'], unit='s')
    df['metric_name'] = metric_name
    base_cols = ['metric_name', 'ts']
    cols = base_cols + [c for c in df.columns if c not in base_cols]
    return df[cols]
