from time import sleep

import requests

from omegaml.client.auth import OmegaRestApiAuth
from omegaml.client.docoptparser import CommandBase
from omegaml.client.userconf import save_userconfig_from_apikey
from omegaml.client.util import get_omega
from omegaml.defaults import update_from_config


class CloudCommandBase(CommandBase):
    """
    Usage:
      om cloud login [<userid>] [<apikey>] [options]
      om cloud config [options]
      om cloud (add|update|remove) <kind> [--node-type <type>] [--count <n>] [--specs <specs>] [options]

    Options:
      --userid=USERID   the userid at hub.omegaml.io (see account profile)
      --apikey=APIKEY   the apikey at hub.omegaml.io (see account profile)
      --apiurl=URL      the cloud URL [default: https://hub.omegaml.io]
      --count=NUMBER    how many instances to set up [default: 1]
      --node-type=TYPE  the type of node [default: small]
      --specs=SPECS     the service specifications as "key=value[,...]"
    """
    command = 'cloud'

    @property
    def om(self):
        return get_omega(self.args)

    def login(self):
        userid = self.args.get('<userid>') or self.args.get('--userid')
        apikey = self.args.get('<apikey>') or self.args.get('--apikey')
        api_url = self.args.get('--apiurl')
        configfile = self.args.get('--config') or 'config.yml'
        if not userid:
            userid = self.ask('Userid:')
        if not apikey:
            apikey = self.ask('Apikey:')
        save_userconfig_from_apikey(configfile, userid, apikey, api_url=api_url)

    def config(self):
        om = self.om
        config_file = om.defaults.OMEGA_CONFIG_FILE
        if config_file is None:
            config_file = print("No configuration file identified, assuming defaults")
        # print config
        restapi_url = getattr(om.defaults, 'OMEGA_RESTAPI_URL', 'not configured')
        runtime_url = om.runtime.celeryapp.conf['BROKER_URL']
        userid = getattr(om.defaults, 'OMEGA_USERID', 'not configured')
        self.logger.info('Config file: {config_file}'.format(**locals()))
        self.logger.info('User id: {userid}'.format(**locals()))
        self.logger.info('REST API URL: {restapi_url}'.format(**locals()))
        self.logger.info('Runtime broker: {runtime_url}'.format(**locals()))

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
        default_specs = "size={size},node-type={node_type}".format(**locals())
        params = specs or default_specs
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
        auth = OmegaRestApiAuth.make_from(om)
        restapi_url = getattr(om.defaults, 'OMEGA_RESTAPI_URL', 'not configured')
        uri = uri or '/admin/api/v2/service/{service}'.format(**locals())
        service_url = '{restapi_url}{uri}'.format(**locals())
        method = getattr(requests, method)
        resp = method(service_url, json=data, auth=auth)
        resp.raise_for_status()
        if resp.status_code == requests.codes.created:
            # always request the actual object
            url = resp.headers['Location']
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
