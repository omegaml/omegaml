from omegaml.client.docoptparser import CommandBase
from omegaml.client.userconf import save_userconfig_from_apikey
from omegaml.client.util import get_omega
from omegaml.defaults import update_from_config


class CloudCommandBase(CommandBase):
    """
    Usage:
      om cloud login [<userid>] [<apikey>] [options]
      om cloud config [options]

    Options:
      --userid=USERID  the userid at hub.omegaml.io (see account profile)
      --apikey=APIKEY  the apikey at hub.omegaml.io (see account profile)
      --apiurl=URL     the cloud URL [default: https://hub.omegaml.io]
    """
    command = 'cloud'

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
        om = get_omega(self.args)
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





        






